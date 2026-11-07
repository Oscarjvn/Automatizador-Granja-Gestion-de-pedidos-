"""Pruebas de la integración con la API de inventario del CEDI."""
from unittest import mock

import requests
from django.test import TestCase, override_settings
from django.urls import reverse

from nucleo.models import DetallePedido, Pedido, Usuario
from nucleo.services.cedi.inventario import (
    InventarioCediNoDisponible, _interpretar_respuesta, consultar_stock_cedi,
)
from nucleo.services.pedidos import (
    DespachoInvalido, aprobar_pedido, despachar_pedido, generar_pedido_sugerido,
)
from nucleo.tests.utils import crear_producto, crear_tienda, crear_usuario

R = Usuario.Rol
M = DetallePedido.MotivoAjuste
POST = 'nucleo.services.cedi.inventario.requests.post'
CONSULTA_VISTA = 'nucleo.views.cedi_view.consultar_stock_cedi'


def respuesta(json_data=None, status=200):
    r = mock.Mock(status_code=status)
    r.json.return_value = json_data
    r.raise_for_status.side_effect = None if status < 400 else requests.exceptions.HTTPError()
    return r


class InterpretarRespuestaTests(TestCase):
    def test_formato_esperado_normaliza_los_sku(self):
        data = {'productos': [{'sku': '005000', 'disponible': 120}, {'sku': '5001', 'disponible': 0}]}
        self.assertEqual(_interpretar_respuesta(data), {'5000': 120, '5001': 0})

    def test_acepta_nombres_de_campo_alternativos(self):
        data = [{'codigo_producto': '0042', 'existencia': '7.0'}]
        self.assertEqual(_interpretar_respuesta(data), {'42': 7})

    def test_ignora_filas_incompletas_y_negativos(self):
        data = {'inventario': [{'sku': '1'}, {'disponible': 3}, {'sku': '2', 'stock': -5}]}
        self.assertEqual(_interpretar_respuesta(data), {'2': 0})

    def test_respuesta_sin_lista_es_un_error(self):
        with self.assertRaises(InventarioCediNoDisponible):
            _interpretar_respuesta({'mensaje': 'ok'})


@override_settings(CEDI_INVENTARIO_URL='http://cedi.local/inventario', CEDI_INVENTARIO_TOKEN='secreto',
                   CEDI_INVENTARIO_SIMULADO=False)
class ConsultarStockTests(TestCase):
    def test_una_sola_llamada_con_los_sku_y_el_token(self):
        with mock.patch(POST, return_value=respuesta({'productos': [{'sku': '10', 'disponible': 4}]})) as post:
            stock = consultar_stock_cedi(['0010', '10', '11'])
        self.assertEqual(stock, {'10': 4})
        post.assert_called_once()
        self.assertEqual(post.call_args.kwargs['json'], {'skus': ['10', '11']})
        self.assertEqual(post.call_args.kwargs['headers']['Authorization'], 'Bearer secreto')

    def test_tiempo_agotado(self):
        with mock.patch(POST, side_effect=requests.exceptions.Timeout()):
            with self.assertRaisesMessage(InventarioCediNoDisponible, 'no respondió'):
                consultar_stock_cedi(['1'])

    def test_sin_conexion(self):
        with mock.patch(POST, side_effect=requests.exceptions.ConnectionError()):
            with self.assertRaisesMessage(InventarioCediNoDisponible, 'No hay conexión'):
                consultar_stock_cedi(['1'])

    def test_error_http(self):
        with mock.patch(POST, return_value=respuesta(status=500)):
            with self.assertRaisesMessage(InventarioCediNoDisponible, 'error 500'):
                consultar_stock_cedi(['1'])

    def test_json_invalido(self):
        r = respuesta()
        r.json.side_effect = ValueError('no es JSON')
        with mock.patch(POST, return_value=r):
            with self.assertRaises(InventarioCediNoDisponible):
                consultar_stock_cedi(['1'])

    def test_sin_productos_no_llama_a_la_api(self):
        with mock.patch(POST) as post:
            self.assertEqual(consultar_stock_cedi([]), {})
        post.assert_not_called()


class ConfiguracionTests(TestCase):
    @override_settings(CEDI_INVENTARIO_URL='', CEDI_INVENTARIO_SIMULADO=False)
    def test_sin_url_configurada(self):
        with self.assertRaisesMessage(InventarioCediNoDisponible, 'no está configurada'):
            consultar_stock_cedi(['1'])

    @override_settings(CEDI_INVENTARIO_SIMULADO=True)
    def test_modo_simulado_es_estable_y_no_llama_a_la_api(self):
        with mock.patch(POST) as post:
            a = consultar_stock_cedi(['5000', '5001'])
            b = consultar_stock_cedi(['5001', '5000'])
        self.assertEqual(a, b)
        post.assert_not_called()


class DespachoConStockTests(TestCase):
    def setUp(self):
        tienda = crear_tienda()
        self.cedi = crear_usuario(None, R.CEDI)
        gerente = crear_usuario(tienda, R.GERENTE)
        self.harina = crear_producto(sku='5000')
        self.arroz = crear_producto(sku='5001')
        self.pedido = generar_pedido_sugerido(tienda, gerente, [
            {'producto': self.harina, 'cant_sugerida': 10, 'cant_ajustada': None},
            {'producto': self.arroz, 'cant_sugerida': 8, 'cant_ajustada': None},
        ])
        aprobar_pedido(self.pedido)
        self.dh = self.pedido.detalles.get(producto=self.harina)
        self.da = self.pedido.detalles.get(producto=self.arroz)

    def test_propone_lo_disponible_y_deduce_el_motivo(self):
        despachar_pedido(self.pedido, self.cedi, {}, {}, stock_cedi={'5000': 6, '5001': 0})
        self.dh.refresh_from_db(); self.da.refresh_from_db()
        self.assertEqual((self.dh.cant_despachada, self.dh.motivo_ajuste, self.dh.stock_cedi_al_despachar),
                         (6, M.STOCK_PARCIAL, 6))
        self.assertEqual((self.da.cant_despachada, self.da.motivo_ajuste), (0, M.SIN_STOCK))

    def test_no_se_despacha_mas_de_lo_disponible(self):
        with self.assertRaisesMessage(DespachoInvalido, 'solo tiene 6'):
            despachar_pedido(self.pedido, self.cedi, {self.dh.pk: 9}, {}, stock_cedi={'5000': 6, '5001': 50})
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.estatus, Pedido.Estado.APROBADO)

    def test_enviar_menos_de_lo_disponible_exige_motivo(self):
        with self.assertRaisesMessage(DespachoInvalido, 'indique el motivo'):
            despachar_pedido(self.pedido, self.cedi, {self.dh.pk: 3}, {}, stock_cedi={'5000': 50, '5001': 50})
        despachar_pedido(self.pedido, self.cedi, {self.dh.pk: 3}, {self.dh.pk: M.DESCONTINUADO},
                         stock_cedi={'5000': 50, '5001': 50})
        self.dh.refresh_from_db()
        self.assertEqual(self.dh.motivo_ajuste, M.DESCONTINUADO)

    def test_sku_que_la_api_no_devuelve_cuenta_como_cero(self):
        despachar_pedido(self.pedido, self.cedi, {}, {}, stock_cedi={'5000': 100})
        self.da.refresh_from_db()
        self.assertEqual((self.da.cant_despachada, self.da.motivo_ajuste, self.da.stock_cedi_al_despachar),
                         (0, M.SIN_STOCK, 0))

    def test_sin_stock_de_ningun_producto_rechaza_el_pedido(self):
        despachar_pedido(self.pedido, self.cedi, {}, {}, stock_cedi={})
        self.assertEqual(self.pedido.estatus, Pedido.Estado.RECHAZADO)

    def test_sin_verificar_queda_constancia(self):
        despachar_pedido(self.pedido, self.cedi, {}, {}, stock_cedi=None)
        self.dh.refresh_from_db()
        self.assertIsNone(self.dh.stock_cedi_al_despachar)
        self.assertEqual(self.dh.cant_despachada, 10)


class VistaDespachoConInventarioTests(DespachoConStockTests):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.cedi)
        self.url = reverse('cedi_pedido', args=[self.pedido.pk])

    def test_la_pantalla_muestra_el_disponible_y_propone_cantidades(self):
        with mock.patch(CONSULTA_VISTA, return_value={'5000': 6, '5001': 40}):
            r = self.client.get(self.url)
        detalles = {d.producto.sku: d for d in r.context['detalles']}
        self.assertEqual((detalles['5000'].disponible, detalles['5000'].propuesta), (6, 6))
        self.assertEqual(detalles['5001'].propuesta, 8)
        self.assertEqual(r.context['unidades_sin_stock'], 4)
        self.assertTrue(r.context['puede_despachar'])

    def test_al_confirmar_se_vuelve_a_consultar_el_stock(self):
        # Al abrir había 6; al confirmar ya solo quedan 2 (otro pedido se los llevó)
        with mock.patch(CONSULTA_VISTA, return_value={'5000': 2, '5001': 40}) as consulta:
            r = self.client.post(self.url, {f'despachada_{self.dh.pk}': '6', f'despachada_{self.da.pk}': '8'})
            consulta.assert_called_once()          # la confirmación consulta de nuevo
            r = self.client.get(r['Location'])     # la pantalla muestra el motivo del rechazo
        self.assertContains(r, 'solo tiene 2')
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.estatus, Pedido.Estado.APROBADO)

    @override_settings(CEDI_PERMITIR_DESPACHO_SIN_INVENTARIO=False)
    def test_api_caida_bloquea_el_despacho(self):
        falla = InventarioCediNoDisponible('No hay conexión con el inventario del CEDI.')
        with mock.patch(CONSULTA_VISTA, side_effect=falla):
            r = self.client.get(self.url)
            self.assertFalse(r.context['puede_despachar'])
            self.assertContains(r, 'No se pudo consultar el inventario')
            r = self.client.post(self.url, {}, follow=True)
        self.assertContains(r, 'No se despachó')
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.estatus, Pedido.Estado.APROBADO)

    @override_settings(CEDI_PERMITIR_DESPACHO_SIN_INVENTARIO=True)
    def test_api_caida_con_permiso_despacha_sin_verificar(self):
        falla = InventarioCediNoDisponible('No hay conexión con el inventario del CEDI.')
        with mock.patch(CONSULTA_VISTA, side_effect=falla):
            self.client.post(self.url, {})
        self.dh.refresh_from_db()
        self.assertEqual(self.dh.cant_despachada, 10)
        self.assertIsNone(self.dh.stock_cedi_al_despachar)
