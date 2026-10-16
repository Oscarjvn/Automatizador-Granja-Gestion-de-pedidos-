from django.core.management.base import BaseCommand

from nucleo.models import Tienda
from nucleo.services.reposicion import productos_con_sobrestock


class Command(BaseCommand):
    help = "Lista productos con sobrestock (stock actual > stock máximo) por tienda."

    def add_arguments(self, parser):
        parser.add_argument('--tienda', type=int, default=None)

    def handle(self, *args, **options):
        tiendas = Tienda.objects.all()
        if options['tienda']:
            tiendas = tiendas.filter(pk=options['tienda'])

        for tienda in tiendas:
            items = productos_con_sobrestock(tienda=tienda)
            if not items:
                self.stdout.write(self.style.SUCCESS(f"[{tienda}] ✅ Sin sobrestock."))
                continue

            self.stdout.write(self.style.WARNING(
                f"\n[{tienda}] 🔵 {len(items)} producto(s) con sobrestock:"
            ))
            for i in items:
                self.stdout.write(
                    f"  {i['producto'].sku} - {i['producto'].nombre}\n"
                    f"     stock: {i['stock_actual']} | máximo: {i['stock_maximo']:.0f} | "
                    f"exceso: +{i['exceso']} | cobertura: {i['dias_cobertura']} días"
                )
