from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.views import View

from nucleo.mixin import TiendaRequeridaMixin
from nucleo.models import Pedido       
from nucleo.services.pedidos import (
    EstadoInvalido,
    aprobar_pedido,
    cancelar_pedido,
    recibir_pedido,
)

class PedidoAprobarView(TiendaRequeridaMixin, View):
    def post(self, request, pk):
        pedido = get_object_or_404(Pedido.todos.filter(tienda=self.tienda), pk=pk)
        try:
            aprobar_pedido(pedido)
            messages.success(request, f"Pedido #{pk} aprobado.")
        except EstadoInvalido as e:
            messages.error(request, str(e))
        return redirect('pedido_detalle', pk=pk)


class PedidoCancelarView(TiendaRequeridaMixin, View):
    def post(self, request, pk):
        pedido = get_object_or_404(Pedido.todos.filter(tienda=self.tienda), pk=pk)
        try:
            cancelar_pedido(pedido)
            messages.success(request, f"Pedido #{pk} cancelado.")
        except EstadoInvalido as e:
            messages.error(request, str(e))
        return redirect('pedido_detalle', pk=pk)


class PedidoRecibirView(TiendaRequeridaMixin, View):
    def post(self, request, pk):
        pedido = get_object_or_404(Pedido.todos.filter(tienda=self.tienda), pk=pk)

        cantidades = {}
        for key, value in request.POST.items():
            if not key.startswith('recibida_'):
                continue
            try:
                detalle_pk = int(key.replace('recibida_', ''))
                cantidades[detalle_pk] = int(value)
            except (ValueError, TypeError):
                continue

        try:
            recibir_pedido(pedido, cantidades)
            messages.success(request, f"Pedido #{pk} recibido. Stock actualizado.")
        except EstadoInvalido as e:
            messages.error(request, str(e))
        return redirect('pedido_detalle', pk=pk)