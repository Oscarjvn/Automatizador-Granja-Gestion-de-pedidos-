"""
Tareas nocturnas del sistema, en el orden correcto, con un solo comando.

Pensado para programarse una vez al día (cron, systemd timer o el
programador de tareas del servidor), por ejemplo a las 2:00 a. m.:

    1. sincronizar_ventas       descarga las ventas de ayer del POS
    2. recalcular_reposicion    recalcula DDP, ROP y stock máximo
    3. productos_a_reponer      deja en el log los productos bajo el ROP
    4. productos_sobrestock     deja en el log los productos con exceso
    5. lotes_por_vencer         deja en el log los lotes próximos a vencer

Garantías:
- Si un paso falla, los siguientes igual se ejecutan (recalcular con los datos
  que haya es mejor que no recalcular), pero el comando termina con código 1
  para que el programador de tareas registre la falla.
- Un candado impide que dos ejecuciones corran a la vez (por ejemplo, si la
  de ayer se quedó colgada). Funciona en Linux, macOS y Windows.
"""
import time
from io import StringIO
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from nucleo.candado import Candado, CandadoOcupado

PASOS = [
    ('Sincronizar ventas', 'sincronizar_ventas'),
    ('Recalcular reposición', 'recalcular_reposicion'),
    ('Productos a reponer', 'productos_a_reponer'),
    ('Productos con sobrestock', 'productos_sobrestock'),
    ('Lotes por vencer', 'lotes_por_vencer'),
]


class Command(BaseCommand):
    help = "Ejecuta en orden las tareas diarias: ventas, reposición y alertas."

    def add_arguments(self, parser):
        parser.add_argument('--sin-sincronizar', action='store_true',
                            help='Omite la descarga de ventas (útil si el POS no está disponible).')

    def handle(self, *args, **options):
        carpeta = Path(getattr(settings, 'BASE_DIR', '.')) / 'logs'
        carpeta.mkdir(exist_ok=True)
        try:
            with Candado(carpeta / 'tareas_diarias.lock'):
                self.ejecutar_pasos(options)
        except CandadoOcupado:
            raise CommandError('Ya hay una ejecución de tareas_diarias en curso.')

    def ejecutar_pasos(self, options):
        fallidos = []
        for nombre, comando in PASOS:
            if comando == 'sincronizar_ventas' and options['sin_sincronizar']:
                self.stdout.write(f'· {nombre}: omitido')
                continue
            inicio = time.monotonic()
            salida = StringIO()
            try:
                call_command(comando, stdout=salida, stderr=salida)
                self.stdout.write(self.style.SUCCESS(
                    f'✓ {nombre} ({time.monotonic() - inicio:.1f} s)'))
            except BaseException as e:   # SystemExit incluido: un paso no debe tumbar a los demás
                if isinstance(e, KeyboardInterrupt):
                    raise
                fallidos.append(nombre)
                self.stdout.write(self.style.ERROR(f'✗ {nombre}: {e}'))
            if salida.getvalue().strip():
                self.stdout.write(salida.getvalue().rstrip())

        if fallidos:
            raise CommandError(f"Pasos con error: {', '.join(fallidos)}")
        self.stdout.write(self.style.SUCCESS('Tareas diarias completadas.'))
