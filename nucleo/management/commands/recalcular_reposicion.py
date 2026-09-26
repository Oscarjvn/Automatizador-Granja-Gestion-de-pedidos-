from django.core.management.base import BaseCommand
from django.utils import timezone

from nucleo.models import InventarioProducto, Tienda
from nucleo.services.reposicion import actualizar_analisis
from nucleo.tenant import set_tienda_actual, limpiar_tienda_actual


class Command(BaseCommand):
    help = "Recalcula el AnalisisReposicion para todas las tiendas."

    def add_arguments(self, parser):
        parser.add_argument('--tienda', type=int, default=None)

    def handle(self, *args, **options):
        tiendas = Tienda.objects.all()
        if options['tienda']:
            tiendas = tiendas.filter(pk=options['tienda'])

        inicio = timezone.now()
        creados = actualizados = errores = 0

        try:
            for tienda in tiendas:
                set_tienda_actual(tienda)
                qs = InventarioProducto.todos.filter(tienda=tienda).select_related(
                    'producto', 'tienda'
                )
                self.stdout.write(f"\n[{tienda}] Procesando {qs.count()} inventarios...")

                for inv in qs:
                    try:
                        _, created = actualizar_analisis(inv)
                        if created:
                            creados += 1
                        else:
                            actualizados += 1
                    except Exception as e:
                        errores += 1
                        self.stderr.write(self.style.ERROR(f"[{tienda}] [{inv.pk}] {e}"))
        finally:
            limpiar_tienda_actual()

        duracion = (timezone.now() - inicio).total_seconds()
        self.stdout.write(self.style.SUCCESS(
            f"\n✅ Creados: {creados} | Actualizados: {actualizados} | "
            f"Errores: {errores} | Duración: {duracion:.1f}s"
        ))