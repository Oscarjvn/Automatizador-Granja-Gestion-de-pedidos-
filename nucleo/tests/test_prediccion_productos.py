"""Pruebas de la predicción de ventas del top 20 de productos."""
from datetime import date, time, timedelta
from decimal import Decimal

import pandas as pd
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from nucleo.models import Usuario, Ventas
from nucleo.services.prediccion_productos import (
    precision_validacion, predecir_top_productos, pronosticar_serie,
)
from nucleo.tests.utils import crear_inventario, crear_producto, crear_tienda, crear_usuario

CORTE = date(2026, 9, 30)


def vender(tienda, producto, fecha, unidades, factura=None):
    Ventas.todos.create(
        numero_factura=factura or f'F-{producto.pk}-{fecha.isoformat()}',
        fecha=fecha, hora=time(12, 0), codigo_producto=producto,
        cantidad_vendida=unidades, precio_usd=Decimal('1.00'), tienda=tienda,
    )


def patron_semanal(tienda, producto, semanas=8, base=10, sabado=30):
    """Vende `base` unidades de lunes a viernes y más los sábados; domingo cerrado."""
    for d in range(semanas * 7):
        fecha = CORTE - timedelta(days=d)
        if fecha.weekday() == 6:
            continue
        vender(tienda, producto, fecha, sabado if fecha.weekday() == 5 else base)


class PronosticoSerieTests(TestCase):
    def test_holt_winters_capta_la_estacionalidad_semanal(self):
        indice = pd.date_range(end='2026-09-30', periods=56, freq='D')
        valores = [30 if f.weekday() == 5 else (0 if f.weekday() == 6 else 10) for f in indice]
        serie = pd.Series(valores, index=indice, dtype=float)
        pronostico, metodo = pronosticar_serie(serie, 7)
        self.assertEqual(metodo, 'Holt-Winters')
        futuros = pd.date_range('2026-10-01', periods=7, freq='D')
        sabado = pronostico[[f.weekday() for f in futuros].index(5)]
        lunes = pronostico[[f.weekday() for f in futuros].index(0)]
        self.assertGreater(sabado, lunes * 2)

    def test_precision_alta_con_patron_regular(self):
        indice = pd.date_range(end='2026-09-30', periods=56, freq='D')
        serie = pd.Series([20 if f.weekday() == 5 else 10 for f in indice], index=indice, dtype=float)
        self.assertGreater(precision_validacion(serie), 0.9)

    def test_historial_corto_usa_promedio(self):
        serie = pd.Series([4.0, 6.0, 5.0, 5.0], index=pd.date_range('2026-09-27', periods=4))
        pronostico, metodo = pronosticar_serie(serie, 3)
        self.assertEqual(metodo, 'Promedio')
        self.assertEqual(pronostico, [5.0, 5.0, 5.0])
        self.assertIsNone(precision_validacion(serie))

    def test_historial_intermedio_usa_holt(self):
        serie = pd.Series([5.0 + i for i in range(12)], index=pd.date_range('2026-09-19', periods=12))
        _, metodo = pronosticar_serie(serie, 7)
        self.assertEqual(metodo, 'Holt')

    def test_el_pronostico_nunca_es_negativo(self):
        serie = pd.Series([50.0 - 2 * i for i in range(25)], index=pd.date_range('2026-09-06', periods=25))
        pronostico, _ = pronosticar_serie(serie, 30)
        self.assertTrue(all(v >= 0 for v in pronostico))


class TopProductosTests(TestCase):
    def setUp(self):
        cache.clear()
        self.tienda = crear_tienda()

    def test_sin_ventas_devuelve_mensaje(self):
        data = predecir_top_productos(self.tienda, usar_cache=False)
        self.assertFalse(data['ok'])
        self.assertIn('No hay ventas', data['error'])

    def test_toma_solo_los_20_mas_vendidos_en_orden(self):
        productos = [crear_producto() for _ in range(22)]
        for i, p in enumerate(productos):
            vender(self.tienda, p, CORTE, 100 - i)  # el primero vende más
        data = predecir_top_productos(self.tienda, usar_cache=False)
        self.assertEqual(len(data['items']), 20)
        self.assertEqual([i['sku'] for i in data['items']], [p.sku for p in productos[:20]])
        self.assertEqual(data['items'][0]['posicion'], 1)

    def test_rellena_con_cero_los_dias_sin_ventas(self):
        p = crear_producto()
        for d in range(0, 30, 2):   # vende un día sí y otro no
            vender(self.tienda, p, CORTE - timedelta(days=d), 6)
        item = predecir_top_productos(self.tienda, usar_cache=False)['items'][0]
        self.assertEqual(item['dias_historial'], 29)
        self.assertAlmostEqual(item['promedio_historico'], 6 * 14 / 28, places=1)

    def test_pronostico_semanal_y_alerta_de_quiebre(self):
        p = crear_producto()
        patron_semanal(self.tienda, p)
        crear_inventario(self.tienda, p, stock=20)   # una semana vende ~80 unidades
        item = predecir_top_productos(self.tienda, horizonte=14, usar_cache=False)['items'][0]
        self.assertEqual(item['metodo'], 'Holt-Winters')
        self.assertEqual(len(item['pronostico']), 14)
        self.assertEqual(item['pronostico'][0]['fecha'], '2026-10-01')
        self.assertAlmostEqual(item['total_7_dias'], 80, delta=8)
        self.assertTrue(item['riesgo_quiebre'])
        self.assertLess(item['dias_cobertura'], 3)

    def test_stock_suficiente_no_alerta(self):
        p = crear_producto()
        patron_semanal(self.tienda, p)
        crear_inventario(self.tienda, p, stock=500)
        item = predecir_top_productos(self.tienda, usar_cache=False)['items'][0]
        self.assertFalse(item['riesgo_quiebre'])

    def test_ignora_ventas_de_otra_tienda(self):
        otra = crear_tienda('Otra')
        vender(otra, crear_producto(), CORTE, 999)
        p = crear_producto()
        vender(self.tienda, p, CORTE, 5)
        data = predecir_top_productos(self.tienda, usar_cache=False)
        self.assertEqual([i['sku'] for i in data['items']], [p.sku])

    def test_resultado_se_guarda_en_cache(self):
        p = crear_producto()
        vender(self.tienda, p, CORTE, 5)
        primero = predecir_top_productos(self.tienda)
        vender(self.tienda, crear_producto(), CORTE, 50, factura='nueva')
        self.assertEqual(predecir_top_productos(self.tienda), primero)


class VistaPrediccionProductosTests(TestCase):
    def setUp(self):
        cache.clear()
        self.tienda = crear_tienda()
        p = crear_producto()
        patron_semanal(self.tienda, p, semanas=4)

    def test_supervisor_no_tiene_acceso(self):
        self.client.force_login(crear_usuario(self.tienda, Usuario.Rol.SUPERVISOR))
        r = self.client.get(reverse('reportes_prediccion_productos'))
        self.assertEqual(r.status_code, 403)

    def test_gerente_ve_la_prediccion(self):
        self.client.force_login(crear_usuario(self.tienda, Usuario.Rol.GERENTE))
        r = self.client.get(reverse('reportes_prediccion_productos'), {'dias': 7})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context['dias_prediccion'], 7)
        self.assertEqual(len(r.context['series']), 1)
        self.assertContains(r, 'Top 20 productos')

    def test_horizonte_invalido_vuelve_a_14(self):
        self.client.force_login(crear_usuario(self.tienda, Usuario.Rol.SUBGERENTE))
        r = self.client.get(reverse('reportes_prediccion_productos'), {'dias': 999})
        self.assertEqual(r.context['dias_prediccion'], 14)
