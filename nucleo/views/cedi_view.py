from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.generic import TemplateView

from nucleo.mixin import CediRequeridoMixin
from nucleo.models import DetallePedido, Pedido, Tienda
from nucleo.services.cedi.inventario import (
    InventarioCediNoDisponible, consultar_stock_cedi, registrar_salida_cedi,
)
from nucleo.services.pedidos import EstadoInvalido, despachar_pedido
from nucleo.services.ventas.carga import normalizar_sku


def stock_del_pedido(pedido):
    """(stock, error): existencias del CEDI para los productos del pedido, o el motivo del fallo."""
    skus = [d.producto.sku for d in pedido.detalles.select_related('producto')]
    try:
        return consultar_stock_cedi(skus), None
    except InventarioCediNoDisponible as e:
        return None, str(e)

ESTADOS_CEDI = {
    'AP': 'Por despachar',
    'DE': 'Despachados (en tránsito)',
    'RE': 'Recibidos por la tienda',
    'RC': 'Rechazados',
    'todos': 'Todos',
}


class CediPanelView(CediRequeridoMixin, TemplateView):
    """Cola de trabajo del CEDI: pedidos aprobados por los gerentes de todas las tiendas."""
    template_name = 'cedi/panel.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        estado = self.request.GET.get('estado', 'AP')
        if estado not in ESTADOS_CEDI:
            estado = 'AP'
        tienda_id = self.request.GET.get('tienda') or ''

        base = Pedido.todos.exclude(estatus__in=[Pedido.Estado.PENDIENTE, Pedido.Estado.CANCELADO])
        qs = base
        if estado != 'todos':
            qs = qs.filter(estatus=estado)
        if tienda_id.isdigit():
            qs = qs.filter(tienda_id=int(tienda_id))

        # Los más antiguos primero: el CEDI atiende por orden de llegada
        orden = 'fecha_aprobacion' if estado == 'AP' else '-fecha_despacho'
        ctx['pedidos'] = (
            qs.select_related('tienda', 'usuario', 'despachado_por')
            .annotate(
                lineas=Count('detalles'),
                unidades=Sum(Coalesce('detalles__cant_ajustada', 'detalles__cant_sugerida')),
            )
            .order_by(orden, 'pk')
        )

        hoy = timezone.localdate()
        ctx['kpi'] = base.aggregate(
            por_despachar=Count('pk', filter=Q(estatus=Pedido.Estado.APROBADO)),
            en_transito=Count('pk', filter=Q(estatus=Pedido.Estado.DESPACHADO)),
            despachados_hoy=Count('pk', filter=Q(fecha_despacho__date=hoy,
                                                 estatus__in=[Pedido.Estado.DESPACHADO, Pedido.Estado.RECIBIDO])),
            rechazados=Count('pk', filter=Q(estatus=Pedido.Estado.RECHAZADO)),
        )
        ctx['estados'] = ESTADOS_CEDI
        ctx['estado'] = estado
        ctx['tiendas'] = Tienda.objects.order_by('nombre')
        ctx['tienda_id'] = tienda_id
        ctx['ahora'] = timezone.now()
        return ctx


class CediPedidoView(CediRequeridoMixin, TemplateView):
    """Revisar un pedido y confirmar el despacho, ajustando o rechazando productos."""
    template_name = 'cedi/pedido.html'

    def get_pedido(self):
        return get_object_or_404(
            Pedido.todos.select_related('tienda', 'usuario', 'despachado_por')
            .exclude(estatus__in=[Pedido.Estado.PENDIENTE, Pedido.Estado.CANCELADO]),
            pk=self.kwargs['pk'],
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        pedido = self.get_pedido()
        editable = pedido.estatus == Pedido.Estado.APROBADO
        detalles = list(pedido.detalles.select_related('producto').order_by('producto__cuadrante', 'producto__nombre'))

        stock, error = (None, None)
        if editable:
            stock, error = stock_del_pedido(pedido)
        for d in detalles:
            d.disponible = None if stock is None else stock.get(normalizar_sku(d.producto.sku), 0)
            d.propuesta = d.cant_pedida if d.disponible is None else min(d.cant_pedida, d.disponible)

        ctx['pedido'] = pedido
        ctx['detalles'] = detalles
        ctx['motivos'] = DetallePedido.MotivoAjuste.choices
        ctx['editable'] = editable
        ctx['inventario_verificado'] = stock is not None
        ctx['error_inventario'] = error
        ctx['puede_despachar'] = editable and (stock is not None or settings.CEDI_PERMITIR_DESPACHO_SIN_INVENTARIO)
        if editable and stock is not None:
            ctx['unidades_sin_stock'] = sum(d.cant_pedida - d.propuesta for d in detalles)
        return ctx

    def post(self, request, *args, **kwargs):
        pedido = self.get_pedido()
        cantidades, motivos = {}, {}
        for detalle in pedido.detalles.all():
            valor = request.POST.get(f'despachada_{detalle.pk}', '').strip()
            if valor != '':
                try:
                    cantidades[detalle.pk] = int(valor)
                except ValueError:
                    messages.error(request, 'Las cantidades deben ser números enteros.')
                    return redirect('cedi_pedido', pk=pedido.pk)
            motivos[detalle.pk] = request.POST.get(f'motivo_{detalle.pk}', '')
        # Se vuelve a consultar: entre abrir la pantalla y confirmar, el stock pudo cambiar
        stock, error = stock_del_pedido(pedido)
        if error and not settings.CEDI_PERMITIR_DESPACHO_SIN_INVENTARIO:
            messages.error(request, f'No se despachó: {error} Inténtalo de nuevo en unos minutos.')
            return redirect('cedi_pedido', pk=pedido.pk)
        try:
            # Despacho y salida de inventario juntos: o se registran los dos, o ninguno
            with transaction.atomic():
                pedido = despachar_pedido(pedido, request.user, cantidades, motivos, stock_cedi=stock)
                registrar_salida_cedi(pedido)
        except EstadoInvalido as e:
            messages.error(request, str(e))
            return redirect('cedi_pedido', pk=pedido.pk)

        if pedido.estatus == Pedido.Estado.RECHAZADO:
            messages.warning(request, f'Pedido #{pedido.pk} rechazado: no se despachó ningún producto.')
        else:
            messages.success(request, f'Pedido #{pedido.pk} de {pedido.tienda.nombre} despachado.')
        return redirect('cedi_panel')
