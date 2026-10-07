import re
from datetime import datetime

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


PATRON_LOTE = re.compile(r'^lote_cantidad_(\d+)_(\d+)$')


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
        lotes_por_detalle = {}

        for key, value in request.POST.items():
            if key.startswith('recibida_'):
                try:
                    detalle_pk = int(key.replace('recibida_', ''))
                    cantidades[detalle_pk] = int(value)
                except (ValueError, TypeError):
                    continue
                continue

            match = PATRON_LOTE.match(key)
            if not match:
                continue

            detalle_pk = int(match.group(1))
            idx = int(match.group(2))

            try:
                cant_lote = int(value)
            except (ValueError, TypeError):
                continue

            if cant_lote <= 0:
                continue

            fecha_str = request.POST.get(
                f'lote_vencimiento_{detalle_pk}_{idx}', ''
            ).strip()
            if not fecha_str:
                continue

            try:
                fecha_venc = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            except ValueError:
                continue

            lotes_por_detalle.setdefault(detalle_pk, []).append({
                'cantidad': cant_lote,
                'fecha_vencimiento': fecha_venc,
            })

        try:
            pedido, lotes_creados = recibir_pedido(
                pedido, cantidades, lotes_por_detalle
            )
            messages.success(
                request,
                f"Pedido #{pk} marcado como RECIBIDO. "
                f"{lotes_creados} lote(s) registrado(s)."
            )
        except EstadoInvalido as e:
            messages.error(request, str(e))

        return redirect('pedido_detalle', pk=pk)