import logging
from datetime import date, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from nucleo.models import Tienda
from nucleo.services.ventas.api import APIError, descargar_ventas, ruta_json_crudo
from nucleo.services.ventas.carga import cargar_ventas
from nucleo.services.ventas.limpieza import (
    LimpiezaError,
    cargar_json_limpio,
    guardar_json_limpio,
    limpiar_ventas,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Sincroniza ventas: descarga de API → limpia → carga en BD."

    def add_arguments(self, parser):
        parser.add_argument(
            '--fecha', type=str, default=None,
            help='Fecha a sincronizar (YYYY-MM-DD). Default: ayer.'
        )
        parser.add_argument(
            '--sucursal', type=str, default=None,
            help='Código de sucursal del POS. Default: settings.VENTAS_SUCURSAL_DEFAULT'
        )
        parser.add_argument(
            '--tienda', type=int, default=None,
            help='ID de tienda destino en BD. Default: settings.VENTAS_TIENDA_DEFAULT'
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='No guarda en BD, solo reporta.'
        )
        parser.add_argument(
            '--saltar-descarga', action='store_true',
            help='Usa el JSON crudo ya existente sin llamar a la API.'
        )
        parser.add_argument(
            '--saltar-carga', action='store_true',
            help='Solo descarga y limpia, no carga a BD.'
        )

    def handle(self, *args, **options):
        fecha = self._parse_fecha(options['fecha'])
        sucursal = options['sucursal'] or settings.VENTAS_SUCURSAL_DEFAULT
        tienda_id = options['tienda'] or settings.VENTAS_TIENDA_DEFAULT

        self.stdout.write(self.style.HTTP_INFO(
            f"\n=== Sincronización de ventas ==="
            f"\nFecha: {fecha}"
            f"\nSucursal: {sucursal}"
            f"\nTienda destino: {tienda_id}"
            f"\nDry-run: {options['dry_run']}\n"
        ))

        try:
            tienda = Tienda.objects.get(pk=tienda_id)
        except Tienda.DoesNotExist:
            raise CommandError(f"Tienda ID {tienda_id} no existe")

        # ---- ETAPA 1: DESCARGA ----
        data_crudo = self._descargar(fecha, sucursal, options['saltar_descarga'])

        # ---- ETAPA 2: LIMPIEZA ----
        ventas_limpias = self._limpiar(data_crudo, fecha)

        if options['saltar_carga']:
            self.stdout.write(self.style.SUCCESS(
                f"\n✅ Descarga y limpieza completadas. "
                f"{len(ventas_limpias)} filas listas para cargar."
            ))
            return

        # ---- ETAPA 3: CARGA ----
        resumen = cargar_ventas(ventas_limpias, tienda, dry_run=options['dry_run'])

        self._reportar(resumen)

    def _parse_fecha(self, fecha_str):
        if fecha_str:
            try:
                return date.fromisoformat(fecha_str)
            except ValueError:
                raise CommandError(f"Fecha inválida: {fecha_str}. Usa YYYY-MM-DD.")
        return date.today() - timedelta(days=1)

    def _descargar(self, fecha, sucursal, saltar):
        if saltar:
            ruta = ruta_json_crudo(fecha)
            if not ruta.exists():
                raise CommandError(f"--saltar-descarga pero no existe {ruta}")
            import json
            with open(ruta, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.stdout.write(f"  ⏭️  Descarga saltada. Usando {ruta}")
            return data

        try:
            data = descargar_ventas(fecha, sucursal=sucursal)
        except APIError as e:
            raise CommandError(f"❌ Fallo en descarga: {e}")

        # Guardar crudo para auditoría
        import json
        ruta = ruta_json_crudo(fecha)
        with open(ruta, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        self.stdout.write(self.style.SUCCESS(
            f"  ✅ Descarga OK: {len(data.get('ventas', []))} ventas → {ruta}"
        ))
        return data

    def _limpiar(self, data_crudo, fecha):
        try:
            ventas = limpiar_ventas(data_crudo)
        except LimpiezaError as e:
            raise CommandError(f"❌ Fallo en limpieza: {e}")

        guardar_json_limpio(ventas, fecha)
        self.stdout.write(self.style.SUCCESS(
            f"  ✅ Limpieza OK: {len(ventas)} filas válidas"
        ))
        return ventas

    def _reportar(self, resumen):
        self.stdout.write(self.style.SUCCESS(
            f"\n{'[DRY-RUN] ' if resumen.get('dry_run') else ''}"
            f"✅ Creadas: {resumen['creadas']} | "
            f"Duplicadas: {resumen['duplicadas']} | "
            f"Errores: {resumen['errores']}"
        ))

        if resumen['detalles_errores']:
            self.stdout.write(self.style.WARNING(
                f"\n⚠️  {len(resumen['detalles_errores'])} errores (primeros 20):"
            ))
            for err in resumen['detalles_errores'][:20]:
                self.stdout.write(f"  {err}")