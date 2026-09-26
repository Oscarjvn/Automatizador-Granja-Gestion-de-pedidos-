from django.core.management.base import BaseCommand
from django.db.models import F

from nucleo.models import AnalisisReposicion, Tienda
from nucleo.tenant import set_tienda_actual, limpiar_tienda_actual


class Command(BaseCommand):
    help = "Lista productos que necesitan reposición por tienda."

    def add_arguments(self, parser):
        parser.add_argument('--tienda', type=int, default=None)

    def handle(self, *args, **options):
        tiendas = Tienda.objects.all()
        if options['tienda']:
            tiendas = tiendas.filter(pk=options['tienda'])

        try:
            for tienda in tiendas:
                set_tienda_actual(tienda)
                self._procesar_tienda(tienda)
        finally:
            limpiar_tienda_actual()

    def _procesar_tienda(self, tienda):
        qs = (
            AnalisisReposicion.objects
            .select_related('inventario__producto', 'inventario__tienda')
            .filter(inventario__tienda=tienda)
            .filter(inventario__stock_actual__lte=F('reorder_point'))
        )
        items = list(qs)

        if not items:
            self.stdout.write(self.style.SUCCESS(f"[{tienda}] ✅ Nada que reponer."))
            return

        items.sort(key=lambda a: (not a.es_critico, -a.cantidad_sugerida))
        self.stdout.write(self.style.WARNING(
            f"\n[{tienda}] ⚠️  {len(items)} producto(s) a reponer:"
        ))
        for a in items:
            marca = "🔴 CRÍTICO" if a.es_critico else "🟡"
            self.stdout.write(
                f"{marca} {a.inventario.producto.sku}\n"
                f"     stock: {a.inventario.stock_actual} | "
                f"DDP: {a.promedio_venta_diario}/día | "
                f"ROP: {a.reorder_point} | "
                f"→ reponer: {a.cantidad_sugerida}"
            )