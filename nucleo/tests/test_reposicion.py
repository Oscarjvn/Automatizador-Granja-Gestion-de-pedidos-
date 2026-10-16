"""Pruebas del cálculo de reposición y de las alertas de stock."""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from nucleo.services.reposicion import (
    actualizar_analisis, calcular_parametros, listar_cuadrantes,
    productos_a_reponer, productos_con_sobrestock,
)
from nucleo.tests.utils import (
    crear_analisis, crear_inventario, crear_producto, crear_tienda, registrar_ventas,
)

HOY = date(2026, 10, 1)


class CalculoParametrosTests(TestCase):
    def setUp(self):
        self.tienda = crear_tienda()
        self.producto = crear_producto(lead_time=1, seguridad=1, ciclo=3, historial=30)
        self.inv = crear_inventario(self.tienda, self.producto, stock=0)

    def test_producto_sin_ventas_deja_todo_en_cero(self):
        datos = calcular_parametros(self.inv, hoy=HOY)
        self.assertEqual(datos['dias_analizados'], 0)
        self.assertEqual(datos['promedio_venta_diario'], Decimal('0'))
        self.assertEqual(datos['reorder_point'], Decimal('0'))
        self.assertEqual(datos['stock_maximo'], Decimal('0'))

    def test_historial_completo_aplica_las_formulas(self):
        # 10 unidades diarias durante 30 días = 300 unidades
        registrar_ventas(self.tienda, self.producto, 10, 30, hasta=HOY)
        datos = calcular_parametros(self.inv, hoy=HOY)
        self.assertEqual(datos['dias_analizados'], 30)
        self.assertEqual(datos['promedio_venta_diario'], Decimal('10.000'))
        self.assertEqual(datos['stock_seguridad'], Decimal('10.00'))   # 10 × 1
        self.assertEqual(datos['reorder_point'], Decimal('20.00'))     # 10 × 1 + 10
        self.assertEqual(datos['stock_maximo'], Decimal('50.00'))      # 20 + 10 × 3

    def test_producto_nuevo_usa_los_dias_reales_como_divisor(self):
        # 5 días de historial con 10 unidades diarias: divisor 5, no 30
        registrar_ventas(self.tienda, self.producto, 10, 5, hasta=HOY)
        datos = calcular_parametros(self.inv, hoy=HOY)
        self.assertEqual(datos['dias_analizados'], 5)
        self.assertEqual(datos['promedio_venta_diario'], Decimal('10.000'))

    def test_ignora_ventas_de_otra_tienda(self):
        otra = crear_tienda('Otra')
        registrar_ventas(otra, self.producto, 50, 10, hasta=HOY)
        datos = calcular_parametros(self.inv, hoy=HOY)
        self.assertEqual(datos['promedio_venta_diario'], Decimal('0'))

    def test_actualizar_analisis_es_idempotente(self):
        registrar_ventas(self.tienda, self.producto, 10, 30, hasta=HOY)
        _, creado1 = actualizar_analisis(self.inv, hoy=HOY)
        _, creado2 = actualizar_analisis(self.inv, hoy=HOY)
        self.assertTrue(creado1)
        self.assertFalse(creado2)


class PropiedadesAnalisisTests(TestCase):
    def setUp(self):
        self.tienda = crear_tienda()
        self.producto = crear_producto()

    def analisis_con_stock(self, stock, ddp=10, ss=10, rop=20, maximo=50):
        inv = crear_inventario(self.tienda, crear_producto(), stock=stock)
        return crear_analisis(inv, ddp, ss, rop, maximo)

    def test_cantidad_sugerida_completa_hasta_el_maximo(self):
        a = self.analisis_con_stock(12)
        self.assertTrue(a.necesita_reposicion)
        self.assertEqual(a.cantidad_sugerida, 38)   # 50 - 12

    def test_stock_sobre_rop_no_sugiere_nada(self):
        a = self.analisis_con_stock(25)
        self.assertFalse(a.necesita_reposicion)
        self.assertEqual(a.cantidad_sugerida, 0)

    def test_critico_cuando_no_supera_el_stock_de_seguridad(self):
        self.assertTrue(self.analisis_con_stock(8).es_critico)
        self.assertFalse(self.analisis_con_stock(15).es_critico)

    def test_sobrestock_cuando_supera_el_maximo(self):
        a = self.analisis_con_stock(80)
        self.assertTrue(a.tiene_sobrestock)
        self.assertEqual(a.exceso_unidades, 30)
        self.assertEqual(a.dias_cobertura, 8.0)

    def test_sin_sobrestock_en_el_maximo_exacto(self):
        a = self.analisis_con_stock(50)
        self.assertFalse(a.tiene_sobrestock)
        self.assertEqual(a.exceso_unidades, 0)

    def test_producto_sin_ventas_no_cuenta_como_sobrestock(self):
        a = self.analisis_con_stock(100, ddp=0, ss=0, rop=0, maximo=0)
        self.assertFalse(a.tiene_sobrestock)
        self.assertIsNone(a.dias_cobertura)


class ListadosTests(TestCase):
    def setUp(self):
        self.tienda = crear_tienda('A')
        self.otra = crear_tienda('B')

    def nuevo(self, tienda, stock, ddp=10, ss=10, rop=20, maximo=50, cuadrante='A1'):
        inv = crear_inventario(tienda, crear_producto(cuadrante=cuadrante), stock=stock)
        return crear_analisis(inv, ddp, ss, rop, maximo)

    def test_productos_a_reponer_filtra_por_tienda(self):
        self.nuevo(self.tienda, 5)
        self.nuevo(self.otra, 5)
        self.assertEqual(len(productos_a_reponer(tienda=self.tienda)), 1)

    def test_productos_a_reponer_excluye_productos_sin_ventas(self):
        self.nuevo(self.tienda, 0, ddp=0, ss=0, rop=0, maximo=0)
        self.assertEqual(productos_a_reponer(tienda=self.tienda), [])

    def test_productos_a_reponer_pone_primero_los_criticos(self):
        self.nuevo(self.tienda, 18)   # a reponer, no crítico
        self.nuevo(self.tienda, 2)    # crítico
        lista = productos_a_reponer(tienda=self.tienda)
        self.assertTrue(lista[0]['es_critico'])

    def test_productos_con_sobrestock_ordena_por_exceso(self):
        self.nuevo(self.tienda, 60)    # +10
        self.nuevo(self.tienda, 90)    # +40
        self.nuevo(self.tienda, 30)    # normal
        self.nuevo(self.otra, 200)     # otra tienda
        lista = productos_con_sobrestock(tienda=self.tienda)
        self.assertEqual([i['exceso'] for i in lista], [40, 10])

    def test_listar_cuadrantes_cuenta_solo_la_tienda_indicada(self):
        self.nuevo(self.tienda, 5, cuadrante='B2')
        self.nuevo(self.otra, 5, cuadrante='B2')
        self.nuevo(self.otra, 5, cuadrante='B2')
        b2 = next(c for c in listar_cuadrantes(tienda=self.tienda) if c['nombre'] == 'B2')
        self.assertEqual(b2['a_reponer'], 1)
