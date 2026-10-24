from django.contrib import messages
from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.generic import TemplateView

from nucleo.mixin import CediRequeridoMixin
from nucleo.models import DetallePedido, Pedido, Tienda
from nucleo.services.pedidos import EstadoInvalido, despachar_pedido

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
        ctx['pedido'] = pedido
        ctx['detalles'] = pedido.detalles.select_related('producto').order_by('producto__cuadrante', 'producto__nombre')
        ctx['motivos'] = DetallePedido.MotivoAjuste.choices
        ctx['editable'] = pedido.estatus == Pedido.Estado.APROBADO
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
        try:
            pedido = despachar_pedido(pedido, request.user, cantidades, motivos)
        except EstadoInvalido as e:
            messages.error(request, str(e))
            return redirect('cedi_pedido', pk=pedido.pk)

        if pedido.estatus == Pedido.Estado.RECHAZADO:
            messages.warning(request, f'Pedido #{pedido.pk} rechazado: no se despachó ningún producto.')
        else:
            messages.success(request, f'Pedido #{pedido.pk} de {pedido.tienda.nombre} despachado.')
        return redirect('cedi_panel')
