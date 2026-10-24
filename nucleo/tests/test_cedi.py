"""Pruebas del flujo del centro de distribución (CEDI)."""
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from nucleo.models import DetallePedido, Pedido, Usuario
from nucleo.services.pedidos import (
    DespachoInvalido, EstadoInvalido, aprobar_pedido, cancelar_pedido,
    despachar_pedido, generar_pedido_sugerido, recibir_pedido,
)
from nucleo.tests.utils import crear_producto, crear_tienda, crear_usuario

R = Usuario.Rol
SIN_STOCK = DetallePedido.MotivoAjuste.SIN_STOCK
PARCIAL = DetallePedido.MotivoAjuste.STOCK_PARCIAL


class BaseCedi(TestCase):
    def setUp(self):
        self.tienda = crear_tienda('Los Guayos')
        self.gerente = crear_usuario(self.tienda, R.GERENTE)
        self.cedi = crear_usuario(None, R.CEDI, username='cedi')
        self.harina = crear_producto()
        self.arroz = crear_producto()
        self.pedido = generar_pedido_sugerido(self.tienda, self.gerente, [
            {'producto': self.harina, 'cant_sugerida': 10, 'cant_ajustada': None},
            {'producto': self.arroz, 'cant_sugerida': 5, 'cant_ajustada': 8},
        ])
        self.d_harina = self.pedido.detalles.get(producto=self.harina)
        self.d_arroz = self.pedido.detalles.get(producto=self.arroz)


class DespachoTests(BaseCedi):
    def test_despacho_completo(self):
        aprobar_pedido(self.pedido)
        despachar_pedido(self.pedido, self.cedi, {}, {})
        self.pedido.refresh_from_db()
        self.d_arroz.refresh_from_db()
        self.assertEqual(self.pedido.estatus, Pedido.Estado.DESPACHADO)
        self.assertEqual(self.pedido.despachado_por, self.cedi)
        self.assertIsNotNone(self.pedido.fecha_despacho)
        self.assertEqual(self.d_arroz.cant_despachada, 8)   # despacha lo ajustado, no lo sugerido

    def test_ajuste_parcial_con_motivo(self):
        aprobar_pedido(self.pedido)
        despachar_pedido(self.pedido, self.cedi,
                         {self.d_harina.pk: 6, self.d_arroz.pk: 0},
                         {self.d_harina.pk: PARCIAL, self.d_arroz.pk: SIN_STOCK})
        self.d_harina.refresh_from_db()
        self.d_arroz.refresh_from_db()
        self.assertEqual((self.d_harina.cant_despachada, self.d_harina.motivo_ajuste), (6, PARCIAL))
        self.assertEqual(self.d_harina.diferencia_despacho, 4)
        self.assertEqual((self.d_arroz.cant_despachada, self.d_arroz.motivo_ajuste), (0, SIN_STOCK))

    def test_ajuste_sin_motivo_se_rechaza_sin_guardar(self):
        aprobar_pedido(self.pedido)
        with self.assertRaises(DespachoInvalido):
            despachar_pedido(self.pedido, self.cedi, {self.d_harina.pk: 6}, {})
        self.pedido.refresh_from_db()
        self.d_harina.refresh_from_db()
        self.assertEqual(self.pedido.estatus, Pedido.Estado.APROBADO)
        self.assertIsNone(self.d_harina.cant_despachada)

    def test_no_se_despacha_mas_de_lo_pedido(self):
        aprobar_pedido(self.pedido)
        with self.assertRaises(DespachoInvalido):
            despachar_pedido(self.pedido, self.cedi, {self.d_harina.pk: 11}, {})

    def test_motivo_se_ignora_si_la_linea_va_completa(self):
        aprobar_pedido(self.pedido)
        despachar_pedido(self.pedido, self.cedi, {}, {self.d_harina.pk: SIN_STOCK})
        self.d_harina.refresh_from_db()
        self.assertEqual(self.d_harina.motivo_ajuste, '')

    def test_todo_en_cero_rechaza_el_pedido(self):
        aprobar_pedido(self.pedido)
        despachar_pedido(self.pedido, self.cedi,
                         {self.d_harina.pk: 0, self.d_arroz.pk: 0},
                         {self.d_harina.pk: SIN_STOCK, self.d_arroz.pk: SIN_STOCK})
        self.assertEqual(self.pedido.estatus, Pedido.Estado.RECHAZADO)
        with self.assertRaises(EstadoInvalido):
            recibir_pedido(self.pedido, {}, {})

    def test_solo_se_despachan_pedidos_aprobados(self):
        with self.assertRaises(EstadoInvalido):
            despachar_pedido(self.pedido, self.cedi, {}, {})       # pendiente
        aprobar_pedido(self.pedido)
        despachar_pedido(self.pedido, self.cedi, {}, {})
        with self.assertRaises(EstadoInvalido):
            despachar_pedido(self.pedido, self.cedi, {}, {})       # ya despachado

    def test_no_se_cancela_despues_del_despacho(self):
        aprobar_pedido(self.pedido)
        despachar_pedido(self.pedido, self.cedi, {}, {})
        with self.assertRaises(EstadoInvalido):
            cancelar_pedido(self.pedido)

    def test_la_recepcion_propone_lo_despachado(self):
        aprobar_pedido(self.pedido)
        despachar_pedido(self.pedido, self.cedi, {self.d_harina.pk: 6}, {self.d_harina.pk: PARCIAL})
        recibir_pedido(self.pedido, {}, {})
        self.d_harina.refresh_from_db()
        self.assertEqual(self.d_harina.cant_recibida, 6)
        self.assertEqual(self.d_harina.diferencia_recepcion, 0)

    def test_diferencia_entre_despachado_y_recibido(self):
        aprobar_pedido(self.pedido)
        despachar_pedido(self.pedido, self.cedi, {}, {})
        recibir_pedido(self.pedido, {self.d_harina.pk: 9}, {})
        self.d_harina.refresh_from_db()
        self.assertEqual(self.d_harina.diferencia_recepcion, 1)   # llegó una unidad menos


class PerfilCediTests(TestCase):
    def test_el_cedi_no_lleva_tienda(self):
        perfil = Usuario(rol=R.CEDI, tienda=crear_tienda())
        with self.assertRaises(ValidationError):
            perfil.clean()

    def test_un_usuario_de_tienda_necesita_tienda(self):
        with self.assertRaises(ValidationError):
            Usuario(rol=R.SUPERVISOR, tienda=None).clean()


class VistasCediTests(BaseCedi):
    def setUp(self):
        super().setUp()
        otra = crear_tienda('Naguanagua')
        gerente_otra = crear_usuario(otra, R.GERENTE)
        self.pedido_otra = generar_pedido_sugerido(otra, gerente_otra, [
            {'producto': self.harina, 'cant_sugerida': 3, 'cant_ajustada': None},
        ])
        aprobar_pedido(self.pedido)
        aprobar_pedido(self.pedido_otra)

    def test_el_cedi_ve_los_pedidos_aprobados_de_todas_las_tiendas(self):
        self.client.force_login(self.cedi)
        r = self.client.get(reverse('cedi_panel'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual({p.pk for p in r.context['pedidos']}, {self.pedido.pk, self.pedido_otra.pk})
        self.assertEqual(r.context['kpi']['por_despachar'], 2)

    def test_filtro_por_tienda(self):
        self.client.force_login(self.cedi)
        r = self.client.get(reverse('cedi_panel'), {'tienda': self.tienda.pk})
        self.assertEqual([p.pk for p in r.context['pedidos']], [self.pedido.pk])

    def test_no_ve_pedidos_pendientes(self):
        pendiente = generar_pedido_sugerido(self.tienda, self.gerente, [
            {'producto': self.arroz, 'cant_sugerida': 1, 'cant_ajustada': None},
        ])
        self.client.force_login(self.cedi)
        r = self.client.get(reverse('cedi_panel'), {'estado': 'todos'})
        self.assertNotIn(pendiente.pk, {p.pk for p in r.context['pedidos']})
        self.assertEqual(self.client.get(reverse('cedi_pedido', args=[pendiente.pk])).status_code, 404)

    def test_confirmar_despacho_desde_la_pantalla(self):
        self.client.force_login(self.cedi)
        r = self.client.post(reverse('cedi_pedido', args=[self.pedido.pk]), {
            f'despachada_{self.d_harina.pk}': '4', f'motivo_{self.d_harina.pk}': PARCIAL,
            f'despachada_{self.d_arroz.pk}': '8',
        })
        self.assertRedirects(r, reverse('cedi_panel'))
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.estatus, Pedido.Estado.DESPACHADO)

    def test_error_de_validacion_vuelve_al_pedido_con_mensaje(self):
        self.client.force_login(self.cedi)
        r = self.client.post(reverse('cedi_pedido', args=[self.pedido.pk]),
                             {f'despachada_{self.d_harina.pk}': '4'}, follow=True)
        self.assertContains(r, 'indique el motivo')
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.estatus, Pedido.Estado.APROBADO)

    def test_la_tienda_no_entra_al_panel_del_cedi(self):
        self.client.force_login(self.gerente)
        self.assertEqual(self.client.get(reverse('cedi_panel')).status_code, 403)
        self.assertEqual(self.client.post(reverse('cedi_pedido', args=[self.pedido.pk])).status_code, 403)

    def test_el_cedi_entra_a_su_panel_desde_el_inicio(self):
        self.client.force_login(self.cedi)
        self.assertRedirects(self.client.get(reverse('home')), reverse('cedi_panel'))
        self.assertRedirects(self.client.get(reverse('pedidos')), reverse('cedi_panel'))

    def test_el_cedi_no_puede_aprobar_pedidos_de_tienda(self):
        pendiente = generar_pedido_sugerido(self.tienda, self.gerente, [
            {'producto': self.arroz, 'cant_sugerida': 1, 'cant_ajustada': None},
        ])
        self.client.force_login(self.cedi)
        self.client.post(reverse('pedido_aprobar', args=[pendiente.pk]))
        pendiente.refresh_from_db()
        self.assertEqual(pendiente.estatus, Pedido.Estado.PENDIENTE)

    def test_la_tienda_ve_lo_que_despacho_el_cedi(self):
        despachar_pedido(self.pedido, self.cedi, {self.d_harina.pk: 0}, {self.d_harina.pk: SIN_STOCK})
        self.client.force_login(self.gerente)
        r = self.client.get(reverse('pedido_detalle', args=[self.pedido.pk]))
        self.assertContains(r, 'Sin stock en el CEDI')
        self.assertContains(r, 'Registrar recepción')
