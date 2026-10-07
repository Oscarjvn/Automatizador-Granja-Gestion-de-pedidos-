from django.views.generic import TemplateView

from nucleo.mixin import TiendaRequeridaMixin
from nucleo.services.vencimientos import resumen_vencimientos


class VencimientosView(TiendaRequeridaMixin, TemplateView):
    template_name = 'vencimientos.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(resumen_vencimientos(tienda=self.tienda, dias_por_vencer=7))
        return ctx