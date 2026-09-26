from nucleo.tenant import set_tienda_actual, limpiar_tienda_actual


class TiendaActualMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tienda = None

        if request.user.is_authenticated:
            perfil = getattr(request.user, 'usuario', None)
            if perfil is not None:
                tienda = perfil.tienda

        set_tienda_actual(tienda)

        try:
            response = self.get_response(request)
        finally:
            limpiar_tienda_actual()

        return response