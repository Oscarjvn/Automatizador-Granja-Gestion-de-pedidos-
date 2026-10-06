from datetime import date, datetime, timedelta

from django.views.generic import TemplateView

from nucleo.mixin import TiendaRequeridaMixin
from nucleo.services.reportes.historico import (
    distribucion_dia_semana,
    distribucion_por_hora,
    kpis_periodo,
    serie_diaria,
    serie_mensual,
    serie_semanal,
)


def _parse_fecha(s, default):
    if not s:
        return default
    try:
        return datetime.strptime(s, '%Y-%m-%d').date()
    except ValueError:
        return default


class HistoricoView(TiendaRequeridaMixin, TemplateView):
    template_name = 'reportes/historico.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        hoy = date.today()
        desde = _parse_fecha(self.request.GET.get('desde'), hoy - timedelta(days=29))
        hasta = _parse_fecha(self.request.GET.get('hasta'), hoy)
        agrupacion = self.request.GET.get('agrupacion', 'dia')

        if desde > hasta:
            desde, hasta = hasta, desde

        ctx['desde'] = desde
        ctx['hasta'] = hasta
        ctx['agrupacion'] = agrupacion

        # Serie según agrupación
        if agrupacion == 'semana':
            ctx['serie'] = serie_semanal(self.tienda, desde, hasta)
        elif agrupacion == 'mes':
            ctx['serie'] = serie_mensual(self.tienda, desde, hasta)
        else:
            ctx['serie'] = serie_diaria(self.tienda, desde, hasta)

        ctx['kpis'] = kpis_periodo(self.tienda, desde, hasta)
        ctx['dias_semana'] = distribucion_dia_semana(self.tienda, desde, hasta)
        ctx['horas'] = distribucion_por_hora(self.tienda, desde, hasta)

        return ctx