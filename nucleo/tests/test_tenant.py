"""Pruebas del aislamiento de datos por tienda."""
from django.test import TestCase
from django.urls import reverse

from nucleo.models import Pedido, Usuario
from nucleo.services.pedidos import generar_pedido_sugerido
from nucleo.tenant import limpiar_tienda_actual, set_tienda_actual
from nucleo.tests.utils import crear_producto, crear_tienda, crear_usuario


class TenantManagerTests(TestCase):
    def setUp(self):
        self.a = crear_tienda('A')
        self.b = crear_tienda('B')
        user = crear_usuario(self.a, Usuario.Rol.GERENTE)
        prod = crear_producto()
        for tienda in (self.a, self.b):
            generar_pedido_sugerido(tienda, user, [
                {'producto': prod, 'cant_sugerida': 1, 'cant_ajustada': None},
            ])

    def tearDown(self):
        limpiar_tienda_actual()

    def test_sin_tienda_activa_no_devuelve_nada(self):
        limpiar_tienda_actual()
        self.assertEqual(Pedido.objects.count(), 0)

    def test_con_tienda_activa_solo_devuelve_sus_datos(self):
        set_tienda_actual(self.a)
        self.assertEqual(Pedido.objects.count(), 1)
        self.assertEqual(Pedido.objects.get().tienda, self.a)

    def test_el_gestor_todos_no_filtra(self):
        self.assertEqual(Pedido.todos.count(), 2)


class AislamientoEnVistasTests(TestCase):
    def setUp(self):
        self.a = crear_tienda('A')
        self.b = crear_tienda('B')
        self.gerente_a = crear_usuario(self.a, Usuario.Rol.GERENTE, username='gerente_a')
        gerente_b = crear_usuario(self.b, Usuario.Rol.GERENTE)
        self.pedido_b = generar_pedido_sugerido(self.b, gerente_b, [
            {'producto': crear_producto(), 'cant_sugerida': 3, 'cant_ajustada': None},
        ])
        self.client.force_login(self.gerente_a)

    def test_no_ve_el_detalle_de_un_pedido_de_otra_tienda(self):
        r = self.client.get(reverse('pedido_detalle', args=[self.pedido_b.pk]))
        self.assertEqual(r.status_code, 404)

    def test_no_puede_aprobar_un_pedido_de_otra_tienda(self):
        r = self.client.post(reverse('pedido_aprobar', args=[self.pedido_b.pk]))
        self.assertEqual(r.status_code, 404)
        self.pedido_b.refresh_from_db()
        self.assertEqual(self.pedido_b.estatus, Pedido.Estado.PENDIENTE)

    def test_la_lista_de_pedidos_no_incluye_otras_tiendas(self):
        r = self.client.get(reverse('pedidos'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(list(r.context['pedidos']), [])
