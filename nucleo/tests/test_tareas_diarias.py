"""Pruebas del comando de tareas programadas."""
from io import StringIO
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from nucleo.candado import Candado, CandadoOcupado

MODULO = 'nucleo.management.commands.tareas_diarias.call_command'


class TareasDiariasTests(TestCase):
    def ejecutar(self, *args):
        salida = StringIO()
        call_command('tareas_diarias', *args, stdout=salida)
        return salida.getvalue()

    def test_ejecuta_los_pasos_en_orden(self):
        with mock.patch(MODULO) as falso:
            self.ejecutar()
        llamados = [c.args[0] for c in falso.call_args_list]
        self.assertEqual(llamados, ['sincronizar_ventas', 'recalcular_reposicion',
                                    'productos_a_reponer', 'productos_sobrestock', 'lotes_por_vencer'])

    def test_si_falla_un_paso_sigue_y_termina_con_error(self):
        def falla_sincronizar(nombre, **kw):
            if nombre == 'sincronizar_ventas':
                raise CommandError('POS no responde')
        with mock.patch(MODULO, side_effect=falla_sincronizar) as falso:
            with self.assertRaises(CommandError) as ctx:
                self.ejecutar()
        self.assertIn('Sincronizar ventas', str(ctx.exception))
        self.assertIn('recalcular_reposicion', [c.args[0] for c in falso.call_args_list])

    def test_puede_omitir_la_sincronizacion(self):
        with mock.patch(MODULO) as falso:
            self.ejecutar('--sin-sincronizar')
        self.assertNotIn('sincronizar_ventas', [c.args[0] for c in falso.call_args_list])

    def test_no_permite_dos_ejecuciones_a_la_vez(self):
        ruta = Path(settings.BASE_DIR) / 'logs' / 'tareas_diarias.lock'
        ruta.parent.mkdir(exist_ok=True)
        with Candado(ruta):                       # simula una ejecución en curso
            with mock.patch(MODULO), self.assertRaises(CommandError) as ctx:
                self.ejecutar()
        self.assertIn('en curso', str(ctx.exception))

    def test_los_comandos_de_alerta_funcionan_sin_datos(self):
        salida = self.ejecutar('--sin-sincronizar')
        self.assertIn('Tareas diarias completadas', salida)


class CandadoTests(TestCase):
    def setUp(self):
        self.ruta = Path(settings.BASE_DIR) / 'logs' / 'prueba_candado.lock'
        self.ruta.parent.mkdir(exist_ok=True)

    def test_un_segundo_proceso_no_puede_tomarlo(self):
        with Candado(self.ruta):
            with self.assertRaises(CandadoOcupado):
                with Candado(self.ruta):
                    pass

    def test_se_libera_al_terminar_incluso_con_error(self):
        with self.assertRaises(ValueError):
            with Candado(self.ruta):
                raise ValueError('falla dentro de la tarea')
        with Candado(self.ruta):          # ya está libre
            pass
