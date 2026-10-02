from django.contrib import messages
from django.shortcuts import redirect
from django.views.generic import DetailView, TemplateView

from nucleo.mixin import TiendaRequeridaMixin
from nucleo.models import Pedido, Producto
from nucleo.services.pedidos import generar_pedido_sugerido
from nucleo.services.reposicion import productos_a_reponer


class PedidoDetalleView(TiendaRequeridaMixin, DetailView):
    """Detalle de un pedido, filtrado por tienda del usuario."""
    model = Pedido
    template_name = 'pedido_detalle.html'
    context_object_name = 'pedido'

    def get_queryset(self):
        return Pedido.todos.filter(tienda=self.tienda)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['detalles'] = self.object.detalles.select_related('producto')
        return ctx