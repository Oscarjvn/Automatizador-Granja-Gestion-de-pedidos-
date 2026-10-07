from datetime import date, timedelta

from nucleo.models import Lote


def lotes_vencidos(tienda=None, dias_atras=30):
    """Lotes cuya fecha_vencimiento ya pasó (últimos N días)."""
    hoy = date.today()
    desde = hoy - timedelta(days=dias_atras)
    qs = (
        Lote.todos
        .select_related('producto', 'pedido_origen')
        .filter(fecha_vencimiento__lt=hoy, fecha_vencimiento__gte=desde)
        .order_by('fecha_vencimiento')
    )
    if tienda:
        qs = qs.filter(tienda=tienda)
    return qs


def lotes_por_vencer(dias=7, tienda=None):
    """Lotes que vencen en los próximos N días (sin incluir vencidos)."""
    hoy = date.today()
    limite = hoy + timedelta(days=dias)
    qs = (
        Lote.todos
        .select_related('producto', 'pedido_origen')
        .filter(fecha_vencimiento__gte=hoy, fecha_vencimiento__lte=limite)
        .order_by('fecha_vencimiento')
    )
    if tienda:
        qs = qs.filter(tienda=tienda)
    return qs


def resumen_vencimientos(tienda=None, dias_por_vencer=7):
    return {
        'vencidos': lotes_vencidos(tienda=tienda),
        'por_vencer': lotes_por_vencer(dias=dias_por_vencer, tienda=tienda),
        'dias_alerta': dias_por_vencer,
    }