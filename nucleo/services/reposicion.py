from datetime import date, timedelta
from decimal import Decimal
from django.db.models import F, Count
from django.db.models import Min, Sum

from nucleo.models import AnalisisReposicion, Ventas, Producto


def calcular_parametros(inventario, hoy=None):
    """
    Calcula los parámetros de reposición para un InventarioProducto.

    Divisor híbrido:
        divisor = MIN(dias_historial_ventas, dias_reales_con_datos)

    Donde dias_reales_con_datos = días entre la primera venta y hoy + 1.
    Si no hay ventas registradas, DDP = 0 y todos los parámetros quedan en 0.
    """
    hoy = hoy or date.today()
    producto = inventario.producto

    # Primera venta registrada para este producto-tienda
    primera = (
        Ventas.objects
        .filter(tienda=inventario.tienda, codigo_producto=producto)
        .aggregate(primera=Min('fecha'))['primera']
    )

    if primera is None:
        # Sin historial: DDP = 0, sin reposición
        return _datos_sin_ventas(inventario, hoy)

    # Divisor real: días entre primera venta y hoy, con tope la ventana
    dias_reales = (hoy - primera).days + 1
    divisor = min(producto.dias_historial_ventas, dias_reales)
    desde = hoy - timedelta(days=divisor - 1)

    total_vendido = (
        Ventas.objects
        .filter(
            tienda=inventario.tienda,
            codigo_producto=producto,
            fecha__gte=desde,
            fecha__lte=hoy,
        )
        .aggregate(total=Sum('cantidad_vendida'))['total']
    ) or 0

    ddp = Decimal(total_vendido) / Decimal(divisor)
    stock_seguridad = ddp * producto.dias_stock_seguridad
    reorder_point = ddp * producto.lead_time_dias + stock_seguridad
    stock_maximo = reorder_point + ddp * producto.ciclo_reposicion_dias

    return {
        'periodo_desde': desde,
        'periodo_hasta': hoy,
        'dias_analizados': divisor,
        'promedio_venta_diario': round(ddp, 3),
        'stock_seguridad': round(stock_seguridad, 2),
        'reorder_point': round(reorder_point, 2),
        'stock_maximo': round(stock_maximo, 2),
        'leadtime': producto.lead_time_dias,
        'dias_seguridad_usados': producto.dias_stock_seguridad,
        'ciclo_usado': producto.ciclo_reposicion_dias,
    }


def _datos_sin_ventas(inventario, hoy):
    """Devuelve parámetros en cero para productos sin historial de ventas."""
    return {
        'periodo_desde': hoy,
        'periodo_hasta': hoy,
        'dias_analizados': 0,
        'promedio_venta_diario': Decimal('0.000'),
        'stock_seguridad': Decimal('0.00'),
        'reorder_point': Decimal('0.00'),
        'stock_maximo': Decimal('0.00'),
        'leadtime': inventario.producto.lead_time_dias,
        'dias_seguridad_usados': inventario.producto.dias_stock_seguridad,
        'ciclo_usado': inventario.producto.ciclo_reposicion_dias,
    }


def actualizar_analisis(inventario, hoy=None):
    """
    Calcula y persiste el AnalisisReposicion del inventario.
    Idempotente: correrlo dos veces no duplica.
    """
    datos = calcular_parametros(inventario, hoy=hoy)
    obj, created = AnalisisReposicion.objects.update_or_create(
        inventario=inventario,
        defaults=datos,
    )
    return obj, created


def productos_a_reponer(tienda=None):
    """
    Devuelve lista de dicts con los inventarios que necesitan reposición.
    """
    qs = (
        AnalisisReposicion.objects
        .select_related('inventario__producto', 'inventario__tienda')
        .filter(inventario__stock_actual__lte=F('reorder_point'))
    )
    if tienda:
        qs = qs.filter(inventario__tienda=tienda)

    resultado = []
    for a in qs:
        resultado.append({
            'inventario': a.inventario,
            'producto': a.inventario.producto,
            'stock_actual': a.inventario.stock_actual,
            'reorder_point': float(a.reorder_point),
            'stock_maximo': float(a.stock_maximo),
            'cantidad_sugerida': a.cantidad_sugerida,
            'es_critico': a.es_critico,
            'ddp': float(a.promedio_venta_diario),
        })
    resultado.sort(key=lambda x: (not x['es_critico'], -x['cantidad_sugerida']))
    return resultado


def listar_cuadrantes():
    """
    Devuelve lista de cuadrantes con su conteo de productos y cuántos
    necesitan reposición.
    """
    totales_catalogo = dict(
        Producto.objects
        .exclude(cuadrante__isnull=True)
        .exclude(cuadrante='')
        .values_list('cuadrante')
        .annotate(n=Count('id_producto'))
        .values_list('cuadrante', 'n')
    )

    a_reponer = dict(
        AnalisisReposicion.objects
        .filter(promedio_venta_diario__gt=0)
        .filter(inventario__stock_actual__lte=F('reorder_point'))
        .exclude(inventario__producto__cuadrante__isnull=True)
        .exclude(inventario__producto__cuadrante='')
        .values_list('inventario__producto__cuadrante')
        .annotate(n=Count('inventario'))
        .values_list('inventario__producto__cuadrante', 'n')
    )

    resultado = []
    for cuadrante in sorted(totales_catalogo.keys()):
        resultado.append({
            'nombre': cuadrante,
            'total_productos': totales_catalogo[cuadrante],
            'a_reponer': a_reponer.get(cuadrante, 0),
        })
    return resultado

def productos_a_reponer_de_cuadrante(cuadrante, tienda=None):
    """Lista de items a reponer de un cuadrante específico."""
    if not cuadrante:
        return []

    qs = (
        AnalisisReposicion.objects
        .select_related('inventario__producto', 'inventario__tienda')
        .filter(promedio_venta_diario__gt=0)
        .filter(inventario__stock_actual__lte=F('reorder_point'))
        .filter(inventario__producto__cuadrante=cuadrante)
    )
    if tienda:
        qs = qs.filter(inventario__tienda=tienda)

    resultado = []
    for a in qs:
        resultado.append({
            'inventario': a.inventario,
            'producto': a.inventario.producto,
            'stock_actual': a.inventario.stock_actual,
            'reorder_point': float(a.reorder_point),
            'stock_maximo': float(a.stock_maximo),
            'cantidad_sugerida': a.cantidad_sugerida,
            'es_critico': a.es_critico,
            'ddp': float(a.promedio_venta_diario),
        })

    resultado.sort(key=lambda x: (not x['es_critico'], -x['cantidad_sugerida']))
    return resultado