"""Pruebas de las pantallas de reportes y predicción con ventas reales."""
from datetime import date, time, timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from nucleo.models import Usuario, Ventas
from nucleo.services.reportes.historico import serie_diaria, serie_mensual, serie_semanal
from nucleo.tests.utils import crear_producto, crear_tienda, crear_usuario


class ReportesConDatosTests(TestCase):
    """Antes estas pantallas solo se probaban vacías y un error de fechas pasó inadvertido."""

    def setUp(self):
        self.tienda = crear_tienda()
        self.gerente = crear_usuario(self.tienda, Usuario.Rol.GERENTE)
        producto = crear_producto()
        hoy = date.today()
        for d in range(1, 45):
            Ventas.todos.create(numero_factura=f'F{d}', fecha=hoy - timedelta(days=d), hora=time(10 + d % 8, 0),
                                codigo_producto=producto, cantidad_vendida=5 + d % 3,
                                precio_usd=Decimal('2.00'), tienda=self.tienda)
        self.client.force_login(self.gerente)

    def test_todas_las_pantallas_de_reportes_responden(self):
        for nombre in ('reportes', 'reportes_historico', 'reportes_rotacion', 'reportes_comparativa',
                       'reportes_prediccion', 'reportes_prediccion_productos'):
            with self.subTest(pantalla=nombre):
                self.assertEqual(self.client.get(reverse(nombre)).status_code, 200)

    def test_la_serie_diaria_conserva_las_fechas(self):
        hoy = date.today()
        serie = serie_diaria(self.tienda, hoy - timedelta(days=10), hoy)
        self.assertEqual(serie[0]['fecha'], (hoy - timedelta(days=10)).isoformat())
        self.assertEqual(len(serie), 10)

    def test_series_semanal_y_mensual_con_datos(self):
        hoy = date.today()
        self.assertTrue(serie_semanal(self.tienda, hoy - timedelta(days=40), hoy))
        self.assertTrue(serie_mensual(self.tienda, hoy - timedelta(days=40), hoy))
