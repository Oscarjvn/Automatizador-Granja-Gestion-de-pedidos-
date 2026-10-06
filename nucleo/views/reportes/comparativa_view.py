from datetime import date, datetime, timedelta

from django.views.generic import TemplateView

from nucleo.mixin import TiendaRequeridaMixin
from nucleo.services.reportes.comparativa import (
    comparar_periodos,
    variacion_por_cuadrante,
    variacion_top_productos,
)


def _parse_fecha(s, default):
    if not s:
        return default
    try:
        return datetime.strptime(s, '%Y-%m-%d').date()
    except ValueError:
        return default


class ComparativaView(TiendaRequeridaMixin, TemplateView):
    template_name = 'reportes/comparativa.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        hoy = date.today()

        # Default: últimos 30 días vs los 30 anteriores
        p2_desde = _parse_fecha(self.request.GET.get('p2_desde'), hoy - timedelta(days=29))
        p2_hasta = _parse_fecha(self.request.GET.get('p2_hasta'), hoy)
        p1_desde = _parse_fecha(self.request.GET.get('p1_desde'), p2_desde - timedelta(days=30))
        p1_hasta = _parse_fecha(self.request.GET.get('p1_hasta'), p2_desde - timedelta(days=1))

        ctx['p1_desde'] = p1_desde
        ctx['p1_hasta'] = p1_hasta
        ctx['p2_desde'] = p2_desde
        ctx['p2_hasta'] = p2_hasta

        ctx['comparativa'] = comparar_periodos(
            self.tienda, p1_desde, p1_hasta, p2_desde, p2_hasta
        )
        ctx['cuadrantes'] = variacion_por_cuadrante(
            self.tienda, p1_desde, p1_hasta, p2_desde, p2_hasta
        )
        ctx['productos'] = variacion_top_productos(
            self.tienda, p1_desde, p1_hasta, p2_desde, p2_hasta, limite=20
        )

        return ctx