from datetime import date, timedelta

from django.views.generic import TemplateView

from nucleo.mixin import TiendaRequeridaMixin
from nucleo.services.reportes.historico import kpis_periodo, serie_diaria, distribucion_dia_semana
from nucleo.services.reportes.rotacion import (
    clasificacion_abc,
    resumen_por_cuadrante,
    top_productos,
)


class DashboardReportesView(TiendaRequeridaMixin, TemplateView):
    template_name = 'reportes/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        hoy = date.today()
        # Últimos 30 días
        desde = hoy - timedelta(days=29)

        # Período anterior (30 días antes)
        desde_prev = desde - timedelta(days=30)
        hasta_prev = desde - timedelta(days=1)

        ctx['desde'] = desde
        ctx['hasta'] = hoy
        ctx['kpis'] = kpis_periodo(self.tienda, desde, hoy)
        ctx['kpis_previo'] = kpis_periodo(self.tienda, desde_prev, hasta_prev)

        # Variaciones
        if ctx['kpis_previo']['total_usd'] > 0:
            ctx['var_usd'] = round(
                ((ctx['kpis']['total_usd'] - ctx['kpis_previo']['total_usd'])
                 / ctx['kpis_previo']['total_usd']) * 100, 2
            )
        else:
            ctx['var_usd'] = 0

        # Series para gráficos
        ctx['serie_diaria'] = serie_diaria(self.tienda, desde, hoy)
        ctx['dias_semana'] = distribucion_dia_semana(self.tienda, desde, hoy)

        # Top productos
        ctx['top_usd'] = top_productos(self.tienda, desde, hoy, limite=10, orden='usd')
        ctx['top_unidades'] = top_productos(self.tienda, desde, hoy, limite=10, orden='unidades')

        # ABC
        abc = clasificacion_abc(self.tienda, desde, hoy)
        ctx['abc'] = abc

        # Cuadrantes
        ctx['cuadrantes'] = resumen_por_cuadrante(self.tienda, desde, hoy)

        return ctx