from django.views.generic import TemplateView

from nucleo.mixin import TiendaRequeridaMixin
from nucleo.services.inventario import (
    listar_cuadrantes_disponibles,
    listar_inventario,
)


class InventarioView(TiendaRequeridaMixin, TemplateView):
    template_name = 'inventario.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        cuadrante = self.request.GET.get('cuadrante', '').strip()
        estado = self.request.GET.get('estado', '').strip()
        q = self.request.GET.get('q', '').strip()
        orden = self.request.GET.get('orden', '-stock').strip()
        pagina = self.request.GET.get('pagina', 1)

        data = listar_inventario(
            tienda=self.tienda,
            cuadrante=cuadrante or None,
            estado=estado or None,
            q=q or None,
            orden=orden,
            pagina=pagina,
        )

        ctx.update(data)
        ctx['cuadrantes'] = listar_cuadrantes_disponibles()
        ctx['filtros'] = {
            'cuadrante': cuadrante,
            'estado': estado,
            'q': q,
            'orden': orden,
        }
        return ctx