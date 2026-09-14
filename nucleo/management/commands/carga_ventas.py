import json
from datetime import datetime
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from nucleo.models import Producto, Tienda, Ventas


def parse_fecha(valor):
    """Acepta '2026-08-28T00:00:00.000Z' o '2026-08-28'."""
    return datetime.fromisoformat(valor.replace('Z', '+00:00')).date()


def parse_hora(valor):
    """
    El JSON trae '1970-01-01T20:58:36.939Z' que es una fecha dummy
    + hora real. Extraemos solo HH:MM:SS.
    """
    dt = datetime.fromisoformat(valor.replace('Z', '+00:00'))
    return dt.time()


def inferir_tienda_id(numero_factura):
    """
    'C004-99-00032548' -> 4
    'C001-99-00051378' -> 1
    Devuelve None si no se puede inferir.
    """
    try:
        parte = numero_factura.split('-')[0]  # 'C004'
        return int(parte.replace('C', '').lstrip('0') or '0')
    except (ValueError, IndexError):
        return None

def normalizar_sku(sku):
    """
    Quita ceros a la izquierda para que coincida con la BD.
    '005357' -> '5357'
    '003930' -> '3930'
    '0'      -> '0'
    """
    sku = str(sku).strip()
    return sku.lstrip('0') or '0'

class Command(BaseCommand):
    help = "Carga ventas desde un archivo JSON exportado del POS."

    def add_arguments(self, parser):
        parser.add_argument('archivo', type=str, help='Ruta al JSON de ventas')
        parser.add_argument(
            '--tienda', type=int, default=1,
            help='ID de tienda forzado (ignora el prefijo de la factura).'
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='No guarda en BD, solo reporta.'
        )

    def handle(self, *args, **options):
        archivo = options['archivo']
        dry = options['dry_run']
        tienda_forzada = options['tienda']

        try:
            with open(archivo, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except FileNotFoundError:
            raise CommandError(f"No existe el archivo: {archivo}")
        except json.JSONDecodeError as e:
            raise CommandError(f"JSON inválido: {e}")

        if not isinstance(data, list):
            raise CommandError("El JSON debe ser una lista de ventas.")

        creadas = 0
        omitidas = 0
        errores = []

        for idx, row in enumerate(data):
            try:
                numero_factura = row['numero_factura']
                fecha = parse_fecha(row['fecha'])
                hora = parse_hora(row['hora'])
                sku = row['producto.codigo_producto']
                cantidad = int(row['cantidad.cantidad_vendida'])
                precio = Decimal(str(row['financiero.precio_unitario_usd']))

                # Tienda
                if tienda_forzada is not None:
                    tienda_id = tienda_forzada
                else:
                    tienda_id = inferir_tienda_id(numero_factura)

                if tienda_id is None:
                    errores.append(f"[{idx}] No se pudo inferir tienda de {numero_factura}")
                    omitidas += 1
                    continue

                try:
                    tienda = Tienda.objects.get(pk=tienda_id)
                except Tienda.DoesNotExist:
                    errores.append(f"[{idx}] Tienda {tienda_id} no existe ({numero_factura})")
                    omitidas += 1
                    continue

                try:
                    sku_norm= normalizar_sku(sku)
                    producto = Producto.objects.get(sku=sku_norm)
                except Producto.DoesNotExist:
                    errores.append(f"[{idx}] Producto sku={sku} no existe")
                    omitidas += 1
                    continue

                if dry:
                    creadas += 1
                    continue

                existe= Ventas.objects.filter(
                    numero_factura= numero_factura,
                    codigo_producto= producto,
                    fecha= fecha,
                ).exists()

                if existe:
                    omitidas += 1
                    continue

                with transaction.atomic():
                    Ventas.objects.create(
                        numero_factura=numero_factura,
                        fecha=fecha,
                        hora=hora,
                        codigo_producto=producto,
                        cantidad_vendida=cantidad,
                        precio_usd=precio,
                        tienda=tienda,
                    )
                creadas += 1

            except KeyError as e:
                errores.append(f"[{idx}] Campo faltante: {e}")
                omitidas += 1
            except Exception as e:
                errores.append(f"[{idx}] Error: {e}")
                omitidas += 1

        self.stdout.write(self.style.SUCCESS(
            f"\n✅ Creadas: {creadas} | Omitidas: {omitidas}"
        ))

        if errores:
            self.stdout.write(self.style.WARNING(f"\n⚠️  {len(errores)} errores:"))
            for err in errores[:30]:
                self.stdout.write(f"  {err}")
            if len(errores) > 30:
                self.stdout.write(f"  ... y {len(errores) - 30} más")