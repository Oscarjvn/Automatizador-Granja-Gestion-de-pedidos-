from django.views.generic import TemplateView

from nucleo.mixin import TiendaRequeridaMixin
from nucleo.services.reposicion import productos_con_sobrestock


class SobrestockView(TiendaRequeridaMixin, TemplateView):
    """Alertas de productos cuyo stock supera el stock máximo calculado."""
    template_name = 'sobrestock.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        items = productos_con_sobrestock(tienda=self.tienda)
        ctx['items'] = items
        ctx['total_exceso'] = sum(i['exceso'] for i in items)
        return ctx
