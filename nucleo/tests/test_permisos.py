"""Pruebas de la seguridad por roles."""
from django.test import TestCase
from django.urls import reverse

from nucleo.models import Pedido, Usuario
from nucleo.permisos import PERMISOS, tiene_permiso
from nucleo.services.pedidos import generar_pedido_sugerido
from nucleo.tests.utils import (
    crear_analisis, crear_inventario, crear_producto, crear_tienda, crear_usuario,
)

R = Usuario.Rol


class MatrizPermisosTests(TestCase):
    def setUp(self):
        self.tienda = crear_tienda()

    def test_matriz_de_permisos(self):
        esperado = {
            R.GERENTE: {'generar_pedido', 'aprobar_pedido', 'cancelar_pedido',
                        'recibir_pedido', 'ver_reportes', 'exportar'},
            R.SUBGERENTE: {'generar_pedido', 'recibir_pedido', 'ver_reportes', 'exportar'},
            R.SUPERVISOR: {'generar_pedido', 'recibir_pedido'},
        }
        for rol, permitidas in esperado.items():
            user = crear_usuario(self.tienda, rol)
            for accion in PERMISOS:
                with self.subTest(rol=rol, accion=accion):
                    self.assertEqual(tiene_permiso(user, accion), accion in permitidas)

    def test_solo_existen_tres_roles(self):
        self.assertEqual(set(R.values), {'GERENTE', 'SUBGERENTE', 'SUPERVISOR'})

    def test_usuario_sin_perfil_no_tiene_permisos(self):
        from django.contrib.auth.models import User
        user = User.objects.create_user('sin_perfil', password='x')
        self.assertFalse(tiene_permiso(user, 'recibir_pedido'))

    def test_accion_desconocida_lanza_error(self):
        user = crear_usuario(self.tienda, R.GERENTE)
        with self.assertRaises(ValueError):
            tiene_permiso(user, 'borrar_todo')


class PermisosEnVistasTests(TestCase):
    def setUp(self):
        self.tienda = crear_tienda()
        self.gerente = crear_usuario(self.tienda, R.GERENTE)
        self.supervisor = crear_usuario(self.tienda, R.SUPERVISOR)
        self.subgerente = crear_usuario(self.tienda, R.SUBGERENTE)
        self.producto = crear_producto(sku='777')
        self.pedido = generar_pedido_sugerido(self.tienda, self.supervisor, [
            {'producto': self.producto, 'cant_sugerida': 4, 'cant_ajustada': None},
        ])

    def test_solo_el_gerente_aprueba(self):
        for user in (self.supervisor, self.subgerente):
            self.client.force_login(user)
            r = self.client.post(reverse('pedido_aprobar', args=[self.pedido.pk]))
            self.assertEqual(r.status_code, 403)
        self.client.force_login(self.gerente)
        r = self.client.post(reverse('pedido_aprobar', args=[self.pedido.pk]))
        self.assertEqual(r.status_code, 302)
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.estatus, Pedido.Estado.APROBADO)

    def test_solo_el_gerente_cancela(self):
        for user in (self.supervisor, self.subgerente):
            self.client.force_login(user)
            r = self.client.post(reverse('pedido_cancelar', args=[self.pedido.pk]))
            self.assertEqual(r.status_code, 403)

    def test_supervisor_recibe_pedidos(self):
        from nucleo.services.pedidos import aprobar_pedido
        aprobar_pedido(self.pedido)
        self.client.force_login(self.supervisor)
        r = self.client.post(reverse('pedido_recibir', args=[self.pedido.pk]))
        self.assertEqual(r.status_code, 302)
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.estatus, Pedido.Estado.RECIBIDO)

    def test_supervisor_genera_pedidos(self):
        self.client.force_login(self.supervisor)
        r = self.client.post(reverse('reposicion'), {'ajustada_777': '6', 'sugerido_777': '5'})
        self.assertEqual(r.status_code, 302)
        nuevo = Pedido.todos.latest('pk')
        self.assertEqual(nuevo.detalles.get().cant_ajustada, 6)

    def test_reportes_solo_para_gerencia(self):
        self.client.force_login(self.supervisor)
        self.assertEqual(self.client.get(reverse('reportes')).status_code, 403)
        self.client.force_login(self.gerente)
        self.assertEqual(self.client.get(reverse('reportes')).status_code, 200)

    def test_supervisor_no_exporta(self):
        self.client.force_login(self.supervisor)
        r = self.client.get(reverse('exportar_pedido', args=[self.pedido.pk]))
        self.assertEqual(r.status_code, 403)

    def test_gerente_exporta_excel(self):
        self.client.force_login(self.gerente)
        r = self.client.get(reverse('exportar_pedido', args=[self.pedido.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertIn('spreadsheetml', r['Content-Type'])

    def test_supervisor_no_ve_el_boton_aprobar(self):
        self.client.force_login(self.supervisor)
        r = self.client.get(reverse('pedido_detalle', args=[self.pedido.pk]))
        self.assertNotContains(r, reverse('pedido_aprobar', args=[self.pedido.pk]))
        self.assertContains(r, 'pendiente de aprobación por el gerente')


class AccesoYSobrestockVistasTests(TestCase):
    def setUp(self):
        self.tienda = crear_tienda()
        self.supervisor = crear_usuario(self.tienda, R.SUPERVISOR)

    def test_sin_sesion_redirige_al_login(self):
        for nombre in ('home', 'pedidos', 'reposicion', 'inventario', 'sobrestock', 'vencimientos'):
            with self.subTest(vista=nombre):
                r = self.client.get(reverse(nombre))
                self.assertEqual(r.status_code, 302)
                self.assertIn('login', r['Location'])

    def test_vista_sobrestock_lista_los_excesos(self):
        inv = crear_inventario(self.tienda, crear_producto(), stock=90)
        crear_analisis(inv, 10, 10, 20, 50)
        self.client.force_login(self.supervisor)
        r = self.client.get(reverse('sobrestock'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context['total_exceso'], 40)

    def test_dashboard_muestra_total_de_sobrestock(self):
        inv = crear_inventario(self.tienda, crear_producto(), stock=90)
        crear_analisis(inv, 10, 10, 20, 50)
        self.client.force_login(self.supervisor)
        r = self.client.get(reverse('home'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context['total_sobrestock'], 1)
