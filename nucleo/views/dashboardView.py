from datetime import date, timedelta

from django.db.models import F
from django.views.generic import TemplateView

from nucleo.mixin import TiendaRequeridaMixin
from nucleo.models import (
    AnalisisReposicion,
    InventarioProducto,
    Lote,
    Pedido,
)


class HomePage(TiendaRequeridaMixin, TemplateView):
    template_name = 'home.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        tienda = self.tienda
        hoy = date.today()

        # --- KPIs ---
        ctx['total_productos'] = InventarioProducto.todos.filter(
            tienda=tienda
        ).count()

        ctx['total_criticos'] = AnalisisReposicion.objects.filter(
            inventario__tienda=tienda,
            promedio_venta_diario__gt=0,
            inventario__stock_actual__lte=F('stock_seguridad'),
        ).count()

        ctx['total_a_reponer'] = AnalisisReposicion.objects.filter(
            inventario__tienda=tienda,
            promedio_venta_diario__gt=0,
            inventario__stock_actual__lte=F('reorder_point'),
        ).count()

        ctx['lotes_por_vencer'] = Lote.todos.filter(
            tienda=tienda,
            fecha_vencimiento__gte=hoy,
            fecha_vencimiento__lte=hoy + timedelta(days=7),
        ).count()

        ctx['pedidos_pendientes'] = Pedido.todos.filter(
            tienda=tienda,
            estatus=Pedido.Estado.PENDIENTE,
        ).count()

        ctx['pedidos_aprobados'] = Pedido.todos.filter(
            tienda=tienda,
            estatus=Pedido.Estado.APROBADO,
        ).count()

        # --- Top 10 productos por demanda diaria ---
        ctx['top_demanda'] = list(
            AnalisisReposicion.objects
            .filter(inventario__tienda=tienda, promedio_venta_diario__gt=0)
            .select_related('inventario__producto')
            .order_by('-promedio_venta_diario')[:10]
        )

        # --- Top 5 críticos ---
        ctx['top_criticos'] = list(
            AnalisisReposicion.objects
            .filter(
                inventario__tienda=tienda,
                promedio_venta_diario__gt=0,
                inventario__stock_actual__lte=F('reorder_point'),
            )
            .select_related('inventario__producto')
            .order_by('inventario__stock_actual')[:5]
        )

        # --- Últimos 5 lotes por vencer ---
        ctx['top_vencimientos'] = list(
            Lote.todos
            .filter(
                tienda=tienda,
                fecha_vencimiento__gte=hoy,
                fecha_vencimiento__lte=hoy + timedelta(days=7),
            )
            .select_related('producto')
            .order_by('fecha_vencimiento')[:5]
        )

        return ctx