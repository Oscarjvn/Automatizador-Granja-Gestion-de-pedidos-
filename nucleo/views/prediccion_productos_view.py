from django.views.generic import TemplateView

from nucleo.permisos import PermisoRequeridoMixin
from nucleo.services.prediccion_productos import predecir_top_productos


class PrediccionProductosView(PermisoRequeridoMixin, TemplateView):
    """Pronóstico de unidades para los 20 productos más vendidos de la tienda."""
    permiso_requerido = 'ver_reportes'
    template_name = 'reportes/prediccion_productos.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        try:
            horizonte = int(self.request.GET.get('dias', 14))
        except (TypeError, ValueError):
            horizonte = 14
        if horizonte not in (7, 14, 21, 30):
            horizonte = 14
        data = predecir_top_productos(self.tienda, n=20, dias_historico=90, horizonte=horizonte)
        ctx['data'] = data
        ctx['dias_prediccion'] = horizonte
        ctx['series'] = [
            {'sku': i['sku'], 'nombre': i['nombre'], 'historico': i['historico'], 'pronostico': i['pronostico']}
            for i in data['items']
        ]
        return ctx
