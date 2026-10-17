from django.core.management.base import BaseCommand

from nucleo.models import Tienda
from nucleo.services.prediccion_productos import predecir_top_productos


class Command(BaseCommand):
    help = "Pronostica las ventas de los 20 productos más vendidos de cada tienda."

    def add_arguments(self, parser):
        parser.add_argument('--tienda', type=int, default=None)
        parser.add_argument('--dias', type=int, default=14, help='Días a pronosticar (por defecto 14).')

    def handle(self, *args, **options):
        tiendas = Tienda.objects.all()
        if options['tienda']:
            tiendas = tiendas.filter(pk=options['tienda'])

        for tienda in tiendas:
            data = predecir_top_productos(tienda, horizonte=options['dias'], usar_cache=False)
            if not data['ok']:
                self.stdout.write(self.style.WARNING(f"[{tienda}] {data['error']}"))
                continue
            self.stdout.write(self.style.SUCCESS(
                f"\n[{tienda}] Top {len(data['items'])} productos · corte {data['fecha_corte']} · "
                f"{data['productos_en_riesgo']} en riesgo de quiebre"
            ))
            for i in data['items']:
                alerta = '  ⚠ quiebre' if i['riesgo_quiebre'] else ''
                precision = f"{i['precision']:.0%}" if i['precision'] is not None else 'n/d'
                self.stdout.write(
                    f"  {i['posicion']:>2}. {i['sku']} {i['nombre'][:30]:<30} "
                    f"7d: {i['total_7_dias']:>7.1f}  {options['dias']}d: {i['total_horizonte']:>7.1f}  "
                    f"{i['metodo']:<12} precisión {precision}{alerta}"
                )
