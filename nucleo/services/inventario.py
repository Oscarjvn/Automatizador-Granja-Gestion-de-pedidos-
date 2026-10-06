from django.core.paginator import Paginator
from django.db.models import F, Q

from nucleo.models import AnalisisReposicion, InventarioProducto, Producto


def listar_inventario(
    tienda,
    cuadrante=None,
    estado=None,
    q=None,
    orden='-stock',
    pagina=1,
    por_pagina=50,
):
    """
    Lista el inventario de una tienda con filtros y paginación.

    estado: 'criticos' | 'reponer' | 'ok' | None (todos)
    orden:  '-stock' | 'stock' | 'nombre' | '-ddp' | '-rop'
    """
    # Base: todos los InventarioProducto de la tienda con su análisis
    qs = (
        InventarioProducto.todos
        .filter(tienda=tienda)
        .select_related('producto')
    )

    # Solo los que tienen análisis calculado
    qs = qs.filter(analisis_reposicion__isnull=False)

    # Filtro por cuadrante
    if cuadrante:
        qs = qs.filter(producto__cuadrante=cuadrante)

    # Filtro por estado
    if estado == 'criticos':
        qs = qs.filter(
            analisis_reposicion__promedio_venta_diario__gt=0,
            stock_actual__lte=F('analisis_reposicion__stock_seguridad'),
        )
    elif estado == 'reponer':
        qs = qs.filter(
            analisis_reposicion__promedio_venta_diario__gt=0,
            stock_actual__lte=F('analisis_reposicion__reorder_point'),
        )
    elif estado == 'ok':
        qs = qs.filter(
            Q(analisis_reposicion__promedio_venta_diario=0) |
            Q(stock_actual__gt=F('analisis_reposicion__reorder_point'))
        )

    # Búsqueda
    if q:
        qs = qs.filter(
            Q(producto__sku__icontains=q) |
            Q(producto__nombre__icontains=q)
        )

    # Ordenamiento
    orden_map = {
        'stock': 'stock_actual',
        '-stock': '-stock_actual',
        'nombre': 'producto__nombre',
        '-nombre': '-producto__nombre',
        'ddp': 'analisis_reposicion__promedio_venta_diario',
        '-ddp': '-analisis_reposicion__promedio_venta_diario',
        'rop': 'analisis_reposicion__reorder_point',
        '-rop': '-analisis_reposicion__reorder_point',
    }
    qs = qs.order_by(orden_map.get(orden, '-stock_actual'))

    # Paginación
    paginator = Paginator(qs, por_pagina)
    page_obj = paginator.get_page(pagina)

    # Armar items con análisis accesible
    items = []
    for inv in page_obj:
        a = getattr(inv, 'analisis_reposicion', None)
        items.append({
            'inventario': inv,
            'producto': inv.producto,
            'stock_actual': inv.stock_actual,
            'analisis': a,
            'ddp': float(a.promedio_venta_diario) if a else 0,
            'reorder_point': float(a.reorder_point) if a else 0,
            'stock_seguridad': float(a.stock_seguridad) if a else 0,
            'stock_maximo': float(a.stock_maximo) if a else 0,
            'es_critico': a.es_critico if a else False,
            'necesita_reposicion': a.necesita_reposicion if a else False,
        })

    return {
        'items': items,
        'page_obj': page_obj,
        'total': paginator.count,
    }


def listar_cuadrantes_disponibles():
    """Cuadrantes distintos para el selector de filtro."""
    return list(
        Producto.objects
        .exclude(cuadrante__isnull=True)
        .exclude(cuadrante='')
        .values_list('cuadrante', flat=True)
        .distinct()
        .order_by('cuadrante')
    )