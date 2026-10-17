import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.db import transaction

from nucleo.models import Producto, Tienda, Ventas

logger = logging.getLogger(__name__)


def normalizar_sku(sku):
    """'005357' → '5357'."""
    sku = str(sku).strip()
    return sku.lstrip('0') or '0'


def _parse_fecha(valor):
    """'2026-08-28T00:00:00.000Z' → date(2026, 8, 28)."""
    return datetime.fromisoformat(valor.replace('Z', '+00:00')).date()


def _parse_hora(valor):
    """'1970-01-01T20:58:36.939Z' → time(20, 58, 36)."""
    return datetime.fromisoformat(valor.replace('Z', '+00:00')).time()


def cargar_ventas(ventas_limpias, tienda, dry_run=False):
    """
    Carga una lista de ventas limpias en la BD.

    Una venta se considera duplicada si ya existía en la base de datos ANTES
    de esta carga con la misma tienda, número de factura, producto y fecha.
    Así, volver a sincronizar un día no duplica datos, y dos líneas del mismo
    producto dentro de una factura (que el POS envía por separado) se guardan
    ambas. La misma factura en dos tiendas distintas tampoco se confunde.

    Retorna: dict con resumen {creadas, duplicadas, errores, detalles_errores}
    """
    creadas = 0
    duplicadas = 0
    errores = 0
    detalles = []

    # Productos de la carga en una sola consulta
    skus = {
        normalizar_sku(r.get('producto.codigo_producto', ''))
        for r in ventas_limpias
    }
    productos = {p.sku: p for p in Producto.objects.filter(sku__in=skus)}

    # Ventas que ya existían en la tienda para las fechas de esta carga
    fechas = set()
    for r in ventas_limpias:
        try:
            fechas.add(_parse_fecha(r['fecha']))
        except (KeyError, ValueError, AttributeError):
            pass
    existentes = set(
        Ventas.todos
        .filter(tienda=tienda, fecha__in=fechas)
        .values_list('numero_factura', 'codigo_producto_id', 'fecha')
    )

    nuevas = []
    for idx, row in enumerate(ventas_limpias):
        try:
            numero_factura = row['numero_factura']
            fecha = _parse_fecha(row['fecha'])
            hora = _parse_hora(row['hora'])
            sku_norm = normalizar_sku(row['producto.codigo_producto'])
            cantidad = int(row['cantidad.cantidad_vendida'])
            precio = Decimal(str(row['financiero.precio_unitario_usd']))

            producto = productos.get(sku_norm)
            if producto is None:
                errores += 1
                detalles.append(f"[{idx}] Producto sku={sku_norm} no existe")
                continue

            if (numero_factura, producto.sku, fecha) in existentes:
                duplicadas += 1
                continue

            nuevas.append(Ventas(
                numero_factura=numero_factura,
                fecha=fecha,
                hora=hora,
                codigo_producto=producto,
                cantidad_vendida=cantidad,
                precio_usd=precio,
                tienda=tienda,
            ))
            creadas += 1

        except (KeyError, ValueError, InvalidOperation) as e:
            errores += 1
            detalles.append(f"[{idx}] {type(e).__name__}: {e}")
        except Exception as e:
            errores += 1
            detalles.append(f"[{idx}] Error inesperado: {e}")

    if nuevas and not dry_run:
        with transaction.atomic():
            Ventas.todos.bulk_create(nuevas, batch_size=1000)

    return {
        'creadas': creadas,
        'duplicadas': duplicadas,
        'errores': errores,
        'detalles_errores': detalles,
    }
