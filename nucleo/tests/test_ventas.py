"""Pruebas de la limpieza y carga de ventas del POS."""
from django.test import TestCase

from nucleo.models import Ventas
from nucleo.services.ventas.carga import cargar_ventas, normalizar_sku
from nucleo.services.ventas.limpieza import LimpiezaError, limpiar_ventas
from nucleo.tests.utils import crear_producto, crear_tienda


def venta_cruda(factura='F-1', sku='005357', cantidad=2, precio=1.25):
    return {
        'numero_factura': factura,
        'fecha': '2026-08-28T00:00:00.000Z',
        'hora': '1970-01-01T20:58:36.939Z',
        'producto': {'codigo_producto': sku},
        'cantidad': {'cantidad_vendida': cantidad},
        'financiero': {'precio_unitario_usd': precio},
    }


class LimpiezaTests(TestCase):
    def test_sin_clave_ventas_lanza_error(self):
        with self.assertRaises(LimpiezaError):
            limpiar_ventas({})

    def test_omite_filas_con_campos_faltantes(self):
        incompleta = venta_cruda()
        del incompleta['financiero']
        limpias = limpiar_ventas({'ventas': [venta_cruda(), incompleta]})
        self.assertEqual(len(limpias), 1)
        self.assertEqual(limpias[0]['producto.codigo_producto'], '005357')


class CargaTests(TestCase):
    def setUp(self):
        self.tienda = crear_tienda()
        self.producto = crear_producto(sku='5357')
        self.limpias = limpiar_ventas({'ventas': [venta_cruda()]})

    def test_normalizar_sku_quita_ceros_a_la_izquierda(self):
        self.assertEqual(normalizar_sku('005357'), '5357')
        self.assertEqual(normalizar_sku('000'), '0')

    def test_carga_una_venta(self):
        r = cargar_ventas(self.limpias, self.tienda)
        self.assertEqual(r['creadas'], 1)
        venta = Ventas.todos.get()
        self.assertEqual(venta.cantidad_vendida, 2)
        self.assertEqual(str(venta.fecha), '2026-08-28')

    def test_segunda_carga_reporta_duplicados(self):
        cargar_ventas(self.limpias, self.tienda)
        r = cargar_ventas(self.limpias, self.tienda)
        self.assertEqual(r['creadas'], 0)
        self.assertEqual(r['duplicadas'], 1)
        self.assertEqual(Ventas.todos.count(), 1)

    def test_sku_inexistente_se_registra_como_error(self):
        limpias = limpiar_ventas({'ventas': [venta_cruda(sku='999999'), venta_cruda(factura='F-2')]})
        r = cargar_ventas(limpias, self.tienda)
        self.assertEqual(r['errores'], 1)
        self.assertEqual(r['creadas'], 1)

    def test_dry_run_no_guarda(self):
        r = cargar_ventas(self.limpias, self.tienda, dry_run=True)
        self.assertEqual(r['creadas'], 1)
        self.assertEqual(Ventas.todos.count(), 0)


class DuplicadosPorTiendaTests(TestCase):
    def setUp(self):
        self.a = crear_tienda('A')
        self.b = crear_tienda('B')
        crear_producto(sku='5357')

    def test_misma_factura_en_dos_tiendas_se_guarda_en_ambas(self):
        limpias = limpiar_ventas({'ventas': [venta_cruda()]})
        self.assertEqual(cargar_ventas(limpias, self.a)['creadas'], 1)
        self.assertEqual(cargar_ventas(limpias, self.b)['creadas'], 1)
        self.assertEqual(Ventas.todos.count(), 2)

    def test_dos_lineas_del_mismo_producto_en_una_factura(self):
        limpias = limpiar_ventas({'ventas': [venta_cruda(cantidad=2), venta_cruda(cantidad=3)]})
        r = cargar_ventas(limpias, self.a)
        self.assertEqual(r['creadas'], 2)
        # Re-sincronizar el mismo día no duplica ninguna de las dos
        r2 = cargar_ventas(limpias, self.a)
        self.assertEqual(r2['duplicadas'], 2)
        self.assertEqual(sum(Ventas.todos.values_list('cantidad_vendida', flat=True)), 5)
