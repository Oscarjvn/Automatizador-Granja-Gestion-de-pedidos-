from nucleo.permisos import permisos_de, rol_de


def permisos(request):
    """Expone a las plantillas el rol y los permisos del usuario actual."""
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return {'permisos': {}, 'rol_actual': None}
    return {'permisos': permisos_de(user), 'rol_actual': rol_de(user)}
