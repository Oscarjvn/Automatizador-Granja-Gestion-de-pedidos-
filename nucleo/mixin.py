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
            self.tienda = perfil.tienda
        return super().dispatch(request, *args, **kwargs)