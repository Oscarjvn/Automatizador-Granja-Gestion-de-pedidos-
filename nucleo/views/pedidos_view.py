from django.views.generic import TemplateView

from nucleo.mixin import TiendaRequeridaMixin
from nucleo.models import Pedido


class Pedido_view(TiendaRequeridaMixin, TemplateView):
    """Lista de pedidos de la tienda del usuario, del más reciente al más antiguo."""
    template_name = 'pedidos.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["pedidos"] = (
            Pedido.todos
            .filter(tienda=self.tienda)
            .select_related('usuario')
            .order_by('-fecha_creacion')
        )
        return context
