"""Pruebas de la fuente local del inventario del CEDI (datos de prueba)."""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from nucleo.models import InventarioCedi, Pedido, Usuario
from nucleo.services.cedi.inventario import consultar_stock_cedi, registrar_salida_cedi
from nucleo.services.pedidos import (
    DespachoInvalido, aprobar_pedido, despachar_pedido, generar_pedido_sugerido,
)
from nucleo.tests.utils import crear_producto, crear_tienda, crear_usuario

R = Usuario.Rol


@override_settings(CEDI_INVENTARIO_FUENTE='local', CEDI_PERMITIR_DESPACHO_SIN_INVENTARIO=False)
class FuenteLocalTests(TestCase):
    def setUp(self):
        self.tienda = crear_tienda()
        self.gerente = crear_usuario(self.tienda, R.GERENTE)
        self.cedi = crear_usuario(None, R.CEDI)
        self.harina = crear_producto(sku='5000')
        self.arroz = crear_producto(sku='5001')
        InventarioCedi.objects.create(producto=self.harina, disponible=25)
        InventarioCedi.objects.create(producto=self.arroz, disponible=4)

    def nuevo_pedido(self, harina=10, arroz=8):
        pedido = generar_pedido_sugerido(self.tienda, self.gerente, [
            {'producto': self.harina, 'cant_sugerida': harina, 'cant_ajustada': None},
            {'producto': self.arroz, 'cant_sugerida': arroz, 'cant_ajustada': None},
        ])
        aprobar_pedido(pedido)
        return pedido

    def stock(self, producto):
        return InventarioCedi.objects.get(producto=producto).disponible

    def test_consulta_la_tabla_local(self):
        self.assertEqual(consultar_stock_cedi(['005000', '5001', '9999']), {'5000': 25, '5001': 4})

    def test_despachar_descuenta_el_stock(self):
        pedido = self.nuevo_pedido()
        despachar_pedido(pedido, self.cedi, {}, {}, stock_cedi=consultar_stock_cedi(['5000', '5001']))
        registrar_salida_cedi(pedido)
        self.assertEqual(self.stock(self.harina), 15)   # 25 − 10
        self.assertEqual(self.stock(self.arroz), 0)     # tenía 4, despachó 4 de 8

    def test_si_el_stock_cambio_no_descuenta_nada(self):
        pedido = self.nuevo_pedido()
        despachar_pedido(pedido, self.cedi, {}, {}, stock_cedi={'5000': 25, '5001': 4})
        InventarioCedi.objects.filter(producto=self.arroz).update(disponible=1)   # otro despacho se lo llevó
        with self.assertRaises(DespachoInvalido):
            registrar_salida_cedi(pedido)

    @override_settings(CEDI_INVENTARIO_FUENTE='api', CEDI_PERMITIR_DESPACHO_SIN_INVENTARIO=True)
    def test_con_la_api_nunca_se_toca_la_tabla(self):
        pedido = self.nuevo_pedido()
        despachar_pedido(pedido, self.cedi, {}, {}, stock_cedi=None)
        registrar_salida_cedi(pedido)
        self.assertEqual(self.stock(self.harina), 25)

    def test_flujo_completo_desde_la_pantalla(self):
        primero = self.nuevo_pedido(harina=10, arroz=3)
        segundo = self.nuevo_pedido(harina=20, arroz=3)
        self.client.force_login(self.cedi)

        self.client.post(reverse('cedi_pedido', args=[primero.pk]), {})
        self.assertEqual(self.stock(self.harina), 15)
        self.assertEqual(self.stock(self.arroz), 1)

        # El segundo pedido ya ve el stock reducido por el primero
        r = self.client.get(reverse('cedi_pedido', args=[segundo.pk]))
        propuestas = {d.producto.sku: d.propuesta for d in r.context['detalles']}
        self.assertEqual(propuestas, {'5000': 15, '5001': 1})

    def test_si_falla_la_salida_se_deshace_el_despacho(self):
        pedido = self.nuevo_pedido(harina=10, arroz=3)
        self.client.force_login(self.cedi)
        # Simula que entre la consulta y la resta otro despacho consumió la harina
        import nucleo.views.cedi_view as vista
        original = vista.despachar_pedido

        def despachar_y_vaciar(*args, **kwargs):
            resultado = original(*args, **kwargs)
            InventarioCedi.objects.filter(producto=self.harina).update(disponible=0)
            return resultado

        vista.despachar_pedido = despachar_y_vaciar
        try:
            self.client.post(reverse('cedi_pedido', args=[pedido.pk]), {})
        finally:
            vista.despachar_pedido = original
        pedido.refresh_from_db()
        self.assertEqual(pedido.estatus, Pedido.Estado.APROBADO)          # el despacho se deshizo
        self.assertIsNone(pedido.detalles.get(producto=self.harina).cant_despachada)
        self.assertEqual(self.stock(self.arroz), 4)                        # y el arroz no se descontó


class ComandoInventarioPruebaTests(TestCase):
    def setUp(self):
        self.productos = [crear_producto() for _ in range(40)]

    def cargar(self, *args):
        call_command('cargar_inventario_cedi_prueba', *args, stdout=StringIO())
        return dict(InventarioCedi.objects.values_list('producto_id', 'disponible'))

    def test_carga_todos_los_productos_con_mezcla_realista(self):
        datos = self.cargar()
        self.assertEqual(len(datos), 40)
        valores = list(datos.values())
        self.assertTrue(any(v == 0 for v in valores))          # hay agotados
        self.assertTrue(any(1 <= v <= 15 for v in valores))    # hay poco stock
        self.assertTrue(any(v > 120 for v in valores))         # hay stock alto

    def test_misma_semilla_mismos_datos(self):
        self.assertEqual(self.cargar('--semilla', '7'), self.cargar('--semilla', '7'))

    def test_solo_nuevos_respeta_lo_existente(self):
        InventarioCedi.objects.create(producto=self.productos[0], disponible=999)
        datos = self.cargar('--solo-nuevos')
        self.assertEqual(datos[self.productos[0].pk], 999)
        self.assertEqual(len(datos), 40)
