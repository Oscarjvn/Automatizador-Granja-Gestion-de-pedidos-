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

    Retorna: dict con resumen {creadas, duplicadas, errores, detalles_errores}
    """
    creadas = 0
    duplicadas = 0
    errores = 0
    detalles = [] 

    for idx, row in enumerate(ventas_limpias):
        try:
            numero_factura = row['numero_factura']
            fecha = _parse_fecha(row['fecha'])
            hora = _parse_hora(row['hora'])
            sku_norm = normalizar_sku(row['producto.codigo_producto'])
            cantidad = int(row['cantidad.cantidad_vendida'])
            precio = Decimal(str(row['financiero.precio_unitario_usd']))

            try:
                producto = Producto.objects.get(sku=sku_norm)
            except Producto.DoesNotExist:
                errores += 1
                detalles.append(f"[{idx}] Producto sku={sku_norm} no existe")
                continue

            if dry_run:
                creadas += 1
                continue

            existe = Ventas.todos.filter(
                numero_factura=numero_factura,
                codigo_producto=producto,
                fecha=fecha,
            ).exists()

            if existe:
                duplicadas += 1
                continue

            Ventas.todos.create(
                numero_factura=numero_factura,
                fecha=fecha,
                hora=hora,
                codigo_producto=producto,
                cantidad_vendida=cantidad,
                precio_usd=precio,
                tienda=tienda,
            )
            creadas += 1

        except (KeyError, ValueError, InvalidOperation) as e:
            errores += 1
            detalles.append(f"[{idx}] {type(e).__name__}: {e}")
        except Exception as e:
            errores += 1
            detalles.append(f"[{idx}] Error inesperado: {e}")

    return {
        'creadas': creadas,
        'duplicadas': duplicadas,
        'errores': errores,
        'detalles_errores': detalles,
    }