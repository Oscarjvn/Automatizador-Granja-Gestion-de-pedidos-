from datetime import date, datetime, timedelta

from django.views.generic import TemplateView

from nucleo.mixin import TiendaRequeridaMixin
from nucleo.services.reportes.rotacion import (
    clasificacion_abc,
    productos_sin_movimiento,
    resumen_por_cuadrante,
    top_productos,
)


def _parse_fecha(s, default):
    if not s:
        return default
    try:
        return datetime.strptime(s, '%Y-%m-%d').date()
    except ValueError:
        return default


class RotacionView(TiendaRequeridaMixin, TemplateView):
    template_name = 'reportes/rotacion.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        hoy = date.today()
        desde = _parse_fecha(self.request.GET.get('desde'), hoy - timedelta(days=29))
        hasta = _parse_fecha(self.request.GET.get('hasta'), hoy)

        ctx['desde'] = desde
        ctx['hasta'] = hasta

        ctx['top_usd'] = top_productos(self.tienda, desde, hasta, limite=20, orden='usd')
        ctx['top_unidades'] = top_productos(self.tienda, desde, hasta, limite=20, orden='unidades')

        abc = clasificacion_abc(self.tienda, desde, hasta)
        ctx['abc'] = abc
        ctx['abc_top'] = abc['productos'][:100]  # Solo los primeros 100 para no ahogar

        ctx['sin_movimiento'] = productos_sin_movimiento(self.tienda, dias=60)
        ctx['cuadrantes'] = resumen_por_cuadrante(self.tienda, desde, hasta)

        return ctx