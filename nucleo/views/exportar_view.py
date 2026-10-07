from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.views import View
from datetime import date, datetime, timedelta

from nucleo.mixin import TiendaRequeridaMixin
from nucleo.models import Pedido
from nucleo.services.exportar.pedidos import (
    exportar_lista_pedidos,
    exportar_pedido,
)


XLSX_MIME = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


def _respuesta_excel(buffer, nombre):
    response = HttpResponse(buffer.getvalue(), content_type=XLSX_MIME)
    response['Content-Disposition'] = f'attachment; filename="{nombre}"'
    return response


class ExportarPedidoView(TiendaRequeridaMixin, View):
    """Descarga un pedido individual en Excel."""

    def get(self, request, pk):
        pedido = get_object_or_404(
            Pedido.todos.filter(tienda=self.tienda),
            pk=pk,
        )
        buffer = exportar_pedido(pedido)
        nombre = f'orden_compra_{pedido.pk}.xlsx'
        return _respuesta_excel(buffer, nombre)


class ExportarListaPedidosView(TiendaRequeridaMixin, View):
    """Descarga la lista de pedidos filtrada en Excel."""

    def get(self, request):
        qs = (
            Pedido.todos
            .filter(tienda=self.tienda)
            .select_related('usuario', 'tienda')
            .order_by('-fecha_creacion')
        )

        # Filtros opcionales
        estatus = request.GET.get('estatus')
        if estatus:
            qs = qs.filter(estatus=estatus)

        desde = request.GET.get('desde')
        if desde:
            try:
                qs = qs.filter(fecha_creacion__date__gte=datetime.strptime(desde, '%Y-%m-%d').date())
            except ValueError:
                pass

        hasta = request.GET.get('hasta')
        if hasta:
            try:
                qs = qs.filter(fecha_creacion__date__lte=datetime.strptime(hasta, '%Y-%m-%d').date())
            except ValueError:
                pass

        buffer = exportar_lista_pedidos(qs)
        nombre = f'pedidos_{date.today().isoformat()}.xlsx'
        return _respuesta_excel(buffer, nombre)