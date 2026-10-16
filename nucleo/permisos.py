"""
Seguridad por roles.

Cada acción sensible del sistema tiene un conjunto de roles autorizados.
Las vistas lo verifican con PermisoRequeridoMixin (respuesta 403 si el rol
no alcanza) y las plantillas lo usan, mediante el context processor
`nucleo.context_processors.permisos`, para ocultar botones y menús.

Matriz de permisos:

    Acción              Gerente  Subgerente  Supervisor  Operador
    generar_pedido         sí        sí          sí         no
    aprobar_pedido         sí        no          no         no
    cancelar_pedido        sí        no          no         no
    recibir_pedido         sí        sí          sí         sí
    ver_reportes           sí        sí          no         no
    exportar               sí        sí          no         no

Consultar el dashboard, el inventario, la reposición, el sobrestock y los
vencimientos está permitido a todos los roles.
"""
from django.core.exceptions import PermissionDenied

from nucleo.mixin import TiendaRequeridaMixin
from nucleo.models import Usuario

R = Usuario.Rol

PERMISOS = {
    'generar_pedido': {R.GERENTE, R.SUBGERENTE, R.SUPERVISOR},
    'aprobar_pedido': {R.GERENTE},
    'cancelar_pedido': {R.GERENTE},
    'recibir_pedido': {R.GERENTE, R.SUBGERENTE, R.SUPERVISOR, R.OPERADOR},
    'ver_reportes': {R.GERENTE, R.SUBGERENTE},
    'exportar': {R.GERENTE, R.SUBGERENTE},
}


def rol_de(user):
    """Rol del usuario autenticado, o None si no tiene perfil de tienda."""
    if not getattr(user, 'is_authenticated', False):
        return None
    perfil = getattr(user, 'usuario', None)
    return perfil.rol if perfil else None


def tiene_permiso(user, accion):
    """¿El rol del usuario permite ejecutar la acción indicada?"""
    if accion not in PERMISOS:
        raise ValueError(f"Acción desconocida: {accion}")
    return rol_de(user) in PERMISOS[accion]


def permisos_de(user):
    """Diccionario {acción: bool} con todos los permisos del usuario."""
    return {accion: tiene_permiso(user, accion) for accion in PERMISOS}


class PermisoRequeridoMixin(TiendaRequeridaMixin):
    """
    Exige login, tienda asignada y que el rol tenga el permiso indicado.

    Uso:
        class MiVista(PermisoRequeridoMixin, View):
            permiso_requerido = 'aprobar_pedido'
    """
    permiso_requerido = None

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and getattr(request.user, 'usuario', None):
            if self.permiso_requerido and not tiene_permiso(request.user, self.permiso_requerido):
                raise PermissionDenied("Su rol no tiene permiso para esta acción.")
        return super().dispatch(request, *args, **kwargs)
