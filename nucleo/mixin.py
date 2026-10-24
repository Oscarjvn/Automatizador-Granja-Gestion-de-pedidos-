from django.contrib.auth.mixins import LoginRequiredMixin


class TiendaRequeridaMixin(LoginRequiredMixin):
    """
    Mixin que:
    1. Exige login
    2. Expone self.tienda (la del usuario autenticado)
    3. Redirige al login si no está autenticado

    Uso:
        class MiVista(TiendaRequeridaMixin, TemplateView):
            def get_context_data(self, **kwargs):
                ctx = super().get_context_data(**kwargs)
                ctx['algo'] = algo_de(self.tienda)
                return ctx
    """

    def dispatch(self, request, *args, **kwargs):
        # LoginRequiredMixin se encarga del check de autenticación
        # Aquí solo resolvemos la tienda si el user está logueado
        if request.user.is_authenticated:
            perfil = getattr(request.user, 'usuario', None)
            if perfil is None:
                # Usuario sin perfil: redirige al login
                from django.contrib.auth.views import redirect_to_login
                return redirect_to_login(request.get_full_path())
            if perfil.es_cedi:
                # El CEDI no tiene tienda: su pantalla de inicio es el panel del CEDI
                from django.shortcuts import redirect
                return redirect('cedi_panel')
            self.tienda = perfil.tienda
        return super().dispatch(request, *args, **kwargs)


class CediRequeridoMixin(LoginRequiredMixin):
    """
    Pantallas del centro de distribución: exige login y el rol "Operador de CEDI".
    Un usuario de tienda que intente entrar recibe 403.
    Estas vistas consultan con el gestor `todos`, porque el CEDI ve los
    pedidos de todas las tiendas.
    """

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            perfil = getattr(request.user, 'usuario', None)
            if perfil is None:
                from django.contrib.auth.views import redirect_to_login
                return redirect_to_login(request.get_full_path())
            if not perfil.es_cedi:
                from django.core.exceptions import PermissionDenied
                raise PermissionDenied("Esta pantalla es solo para el centro de distribución.")
        return super().dispatch(request, *args, **kwargs)
