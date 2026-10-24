"""Pruebas del ciclo de vida del pedido."""
from datetime import date

from django.test import TestCase

from nucleo.models import Lote, Pedido, Usuario
from nucleo.services.pedidos import (
    EstadoInvalido, RecepcionInvalida, aprobar_pedido, despachar_pedido, cancelar_pedido, generar_pedido_sugerido, recibir_pedido,
)
from nucleo.tests.utils import crear_producto, crear_tienda, crear_usuario


class CicloPedidoTests(TestCase):
    def setUp(self):
        self.tienda = crear_tienda()
        self.user = crear_usuario(self.tienda, Usuario.Rol.GERENTE)
        self.p1 = crear_producto()
        self.p2 = crear_producto()
        self.pedido = generar_pedido_sugerido(self.tienda, self.user, [
            {'producto': self.p1, 'cant_sugerida': 10, 'cant_ajustada': None},
            {'producto': self.p2, 'cant_sugerida': 5, 'cant_ajustada': 8},
        ])
        self.cedi = crear_usuario(None, Usuario.Rol.CEDI)

    def listo_para_recibir(self):
        """Lleva el pedido por el flujo completo: gerente aprueba y CEDI despacha todo."""
        aprobar_pedido(self.pedido)
        despachar_pedido(self.pedido, self.cedi, {}, {})

    def test_generar_crea_pedido_pendiente_con_sus_lineas(self):
        self.assertEqual(self.pedido.estatus, Pedido.Estado.PENDIENTE)
        self.assertEqual(self.pedido.detalles.count(), 2)

    def test_generar_sin_items_no_crea_pedido(self):
        self.assertIsNone(generar_pedido_sugerido(self.tienda, self.user, []))

    def test_aprobar_registra_estado_y_fecha(self):
        aprobar_pedido(self.pedido)
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.estatus, Pedido.Estado.APROBADO)
        self.assertIsNotNone(self.pedido.fecha_aprobacion)

    def test_no_se_aprueba_dos_veces(self):
        aprobar_pedido(self.pedido)
        with self.assertRaises(EstadoInvalido):
            aprobar_pedido(self.pedido)

    def test_no_se_recibe_un_pedido_que_el_cedi_no_despacho(self):
        aprobar_pedido(self.pedido)
        with self.assertRaises(EstadoInvalido):
            recibir_pedido(self.pedido, {}, {})

    def test_no_se_recibe_un_pedido_pendiente(self):
        with self.assertRaises(EstadoInvalido):
            recibir_pedido(self.pedido, {}, {})

    def test_recibir_guarda_cantidades_y_crea_lotes(self):
        self.listo_para_recibir()
        d1, d2 = list(self.pedido.detalles.order_by('pk'))
        _, lotes = recibir_pedido(
            self.pedido,
            {d1.pk: 9},
            {d1.pk: [
                {'cantidad': 5, 'fecha_vencimiento': date(2026, 12, 1)},
                {'cantidad': 4, 'fecha_vencimiento': date(2026, 12, 15)},
            ]},
        )
        self.pedido.refresh_from_db()
        d1.refresh_from_db()
        d2.refresh_from_db()
        self.assertEqual(self.pedido.estatus, Pedido.Estado.RECIBIDO)
        self.assertEqual(lotes, 2)
        self.assertEqual(d1.cant_recibida, 9)
        self.assertEqual(d2.cant_recibida, 8)   # sin dato: toma la ajustada
        self.assertEqual(Lote.todos.filter(pedido_origen=self.pedido).count(), 2)

    def test_lotes_sin_fecha_o_sin_cantidad_se_ignoran(self):
        self.listo_para_recibir()
        d1 = self.pedido.detalles.order_by('pk').first()
        _, lotes = recibir_pedido(self.pedido, {}, {d1.pk: [
            {'cantidad': 0, 'fecha_vencimiento': date(2026, 12, 1)},
            {'cantidad': 3, 'fecha_vencimiento': None},
        ]})
        self.assertEqual(lotes, 0)

    def test_cantidad_negativa_se_guarda_como_cero(self):
        self.listo_para_recibir()
        d1 = self.pedido.detalles.order_by('pk').first()
        recibir_pedido(self.pedido, {d1.pk: -4}, {})
        d1.refresh_from_db()
        self.assertEqual(d1.cant_recibida, 0)

    def test_cancelar_pendiente(self):
        cancelar_pedido(self.pedido)
        self.assertEqual(self.pedido.estatus, Pedido.Estado.CANCELADO)

    def test_no_se_cancela_un_pedido_recibido(self):
        self.listo_para_recibir()
        recibir_pedido(self.pedido, {}, {})
        with self.assertRaises(EstadoInvalido):
            cancelar_pedido(self.pedido)

    def test_no_se_cancela_dos_veces(self):
        cancelar_pedido(self.pedido)
        with self.assertRaises(EstadoInvalido):
            cancelar_pedido(self.pedido)

    def test_lotes_que_no_cuadran_se_rechazan_sin_guardar_nada(self):
        self.listo_para_recibir()
        d1 = self.pedido.detalles.order_by('pk').first()
        with self.assertRaises(RecepcionInvalida):
            recibir_pedido(self.pedido, {d1.pk: 9}, {d1.pk: [
                {'cantidad': 5, 'fecha_vencimiento': date(2026, 12, 1)},
            ]})
        self.pedido.refresh_from_db()
        d1.refresh_from_db()
        self.assertEqual(self.pedido.estatus, Pedido.Estado.DESPACHADO)
        self.assertIsNone(d1.cant_recibida)
        self.assertEqual(Lote.todos.count(), 0)

    def test_sin_lotes_se_acepta_cualquier_cantidad(self):
        self.listo_para_recibir()
        d1 = self.pedido.detalles.order_by('pk').first()
        recibir_pedido(self.pedido, {d1.pk: 7}, {})
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.estatus, Pedido.Estado.RECIBIDO)
