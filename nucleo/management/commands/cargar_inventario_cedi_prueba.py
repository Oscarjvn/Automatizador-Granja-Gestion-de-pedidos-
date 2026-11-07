"""
Llena la tabla inventario_cedi con existencias aleatorias de prueba.

Solo tiene sentido con CEDI_INVENTARIO_FUENTE=local (sin acceso a la API).
La mezcla imita un CEDI real: algunos productos agotados, varios con poco
stock y la mayoría con existencias suficientes. Con la misma semilla se
obtienen siempre los mismos datos, para que una demostración sea repetible.
"""
import random

from django.core.management.base import BaseCommand
from django.db import transaction

from nucleo.models import InventarioCedi, Producto

# (probabilidad, mínimo, máximo)
MEZCLA = [
    (0.15, 0, 0),       # agotado
    (0.25, 1, 15),      # poco stock: provoca despachos parciales
    (0.35, 16, 120),    # stock normal
    (0.25, 121, 600),   # stock alto
]


class Command(BaseCommand):
    help = "Carga existencias aleatorias de prueba en el inventario local del CEDI."

    def add_arguments(self, parser):
        parser.add_argument('--semilla', type=int, default=42, help='Semilla aleatoria (por defecto 42).')
        parser.add_argument('--solo-nuevos', action='store_true',
                            help='No modifica los productos que ya tienen existencias cargadas.')

    def handle(self, *args, **options):
        azar = random.Random(options['semilla'])
        pesos = [m[0] for m in MEZCLA]
        existentes = set(InventarioCedi.objects.values_list('producto_id', flat=True))
        conteo = {'agotados': 0, 'creados': 0, 'actualizados': 0, 'omitidos': 0}

        with transaction.atomic():
            for producto in Producto.objects.order_by('pk'):
                _, minimo, maximo = azar.choices(MEZCLA, weights=pesos)[0]
                cantidad = azar.randint(minimo, maximo)
                if producto.pk in existentes and options['solo_nuevos']:
                    conteo['omitidos'] += 1
                    continue
                _, creado = InventarioCedi.objects.update_or_create(
                    producto=producto, defaults={'disponible': cantidad})
                conteo['creados' if creado else 'actualizados'] += 1
                conteo['agotados'] += cantidad == 0

        self.stdout.write(self.style.SUCCESS(
            f"Inventario de prueba del CEDI: {conteo['creados']} creados, {conteo['actualizados']} "
            f"actualizados, {conteo['omitidos']} sin cambios ({conteo['agotados']} agotados)."
        ))
