from django.views.generic import TemplateView
from ..models import Pedido, InventarioProducto, Lote,Tienda


class Pedido_view(TemplateView):
    template_name= 'pedidos.html'
    def get_context_data(self, **kwargs):
            context= super().get_context_data(**kwargs)
            context["pedidos"]= Pedido.objects.all()
            print(context)
        
            return context