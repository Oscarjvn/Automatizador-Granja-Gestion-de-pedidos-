from django.views.generic import TemplateView

from nucleo.permisos import PermisoRequeridoMixin
from nucleo.services.prediccion import predecir_ventas


class PrediccionView(PermisoRequeridoMixin, TemplateView):
    permiso_requerido = 'ver_reportes'

    template_name = 'reportes/prediccion.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        try:
            dias_pred = int(self.request.GET.get('dias', 14))
            dias_pred = max(7, min(dias_pred, 30))
        except (ValueError, TypeError):
            dias_pred = 14

        ctx['dias_prediccion'] = dias_pred
        ctx['data'] = predecir_ventas(
            self.tienda,
            dias_historico=90,
            dias_prediccion=dias_pred,
        )
        return ctx