from django.core.management.base import BaseCommand

from nucleo.models import Tienda
from nucleo.services.vencimientos import lotes_por_vencer, lotes_vencidos
from nucleo.tenant import limpiar_tienda_actual, set_tienda_actual


class Command(BaseCommand):
    help = "Reporta lotes vencidos y por vencer."

    def add_arguments(self, parser):
        parser.add_argument('--tienda', type=int, default=None)
        parser.add_argument('--dias', type=int, default=7)

    def handle(self, *args, **options):
        tiendas = Tienda.objects.all()
        if options['tienda']:
            tiendas = tiendas.filter(pk=options['tienda'])

        try:
            for tienda in tiendas:
                set_tienda_actual(tienda)
                self._procesar(tienda, options['dias'])
        finally:
            limpiar_tienda_actual()

    def _procesar(self, tienda, dias):
        vencidos = list(lotes_vencidos(tienda=tienda))
        por_vencer = list(lotes_por_vencer(dias=dias, tienda=tienda))

        if not vencidos and not por_vencer:
            self.stdout.write(self.style.SUCCESS(f"[{tienda}] ✅ Sin alertas."))
            return

        if vencidos:
            self.stdout.write(self.style.ERROR(
                f"\n[{tienda}] 🔴 {len(vencidos)} lote(s) VENCIDOS:"
            ))
            for l in vencidos:
                self.stdout.write(
                    f"  {l.producto.sku} | {l.cantidad} uds | venció {l.fecha_vencimiento}"
                )

        if por_vencer:
            self.stdout.write(self.style.WARNING(
                f"\n[{tienda}] 🟡 {len(por_vencer)} por vencer en {dias} días:"
            ))
            for l in por_vencer:
                self.stdout.write(
                    f"  {l.producto.sku} | {l.cantidad} uds | vence {l.fecha_vencimiento}"
                )