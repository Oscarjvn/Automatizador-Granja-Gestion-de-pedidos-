from decimal import Decimal

from django.db.models import Count, Sum, F, DecimalField, ExpressionWrapper

from nucleo.models import Producto, Ventas


INGRESO = ExpressionWrapper(
    F('cantidad_vendida') * F('precio_usd'),
    output_field=DecimalField(max_digits=15, decimal_places=2),
)


def top_productos(tienda, desde, hasta, limite=10, orden='usd'):
    """Top N productos por ingreso o unidades."""
    qs = (
        Ventas.todos
        .filter(tienda=tienda, fecha__gte=desde, fecha__lte=hasta)
        .values('codigo_producto__sku', 'codigo_producto__nombre', 'codigo_producto__cuadrante')
        .annotate(
            usd=Sum(INGRESO),
            unidades=Sum('cantidad_vendida'),
        )
    )
    if orden == 'unidades':
        qs = qs.order_by('-unidades')
    else:
        qs = qs.order_by('-usd')
    qs = qs[:limite]

    return [
        {
            'sku': r['codigo_producto__sku'],
            'nombre': r['codigo_producto__nombre'],
            'cuadrante': r['codigo_producto__cuadrante'] or '—',
            'usd': float(r['usd'] or 0),
            'unidades': r['unidades'] or 0,
        }
        for r in qs
    ]


def productos_sin_movimiento(tienda, dias=60):
    """Productos con stock > 0 que no se han vendido en N días."""
    from datetime import date, timedelta
    from nucleo.models import InventarioProducto

    limite = date.today() - timedelta(days=dias)

    # SKUs vendidos en el período
    skus_con_venta = set(
        Ventas.todos
        .filter(tienda=tienda, fecha__gte=limite)
        .values_list('codigo_producto__sku', flat=True)
        .distinct()
    )

    # Productos en inventario con stock > 0
    inventarios = (
        InventarioProducto.todos
        .filter(tienda=tienda, stock_actual__gt=0)
        .select_related('producto')
    )

    resultado = []
    for inv in inventarios:
        if inv.producto.sku not in skus_con_venta:
            resultado.append({
                'sku': inv.producto.sku,
                'nombre': inv.producto.nombre,
                'cuadrante': inv.producto.cuadrante or '—',
                'stock_actual': inv.stock_actual,
            })

    resultado.sort(key=lambda x: -x['stock_actual'])
    return resultado


def clasificacion_abc(tienda, desde, hasta):
    """
    Clasificación ABC por ingreso:
      A: productos que acumulan hasta 80% del ingreso
      B: del 80% al 95%
      C: del 95% al 100%
    """
    qs = (
        Ventas.todos
        .filter(tienda=tienda, fecha__gte=desde, fecha__lte=hasta)
        .values('codigo_producto__sku', 'codigo_producto__nombre', 'codigo_producto__cuadrante')
        .annotate(usd=Sum(INGRESO), unidades=Sum('cantidad_vendida'))
        .order_by('-usd')
    )

    productos = [
        {
            'sku': r['codigo_producto__sku'],
            'nombre': r['codigo_producto__nombre'],
            'cuadrante': r['codigo_producto__cuadrante'] or '—',
            'usd': float(r['usd'] or 0),
            'unidades': r['unidades'] or 0,
        }
        for r in qs
    ]

    total_usd = sum(p['usd'] for p in productos)
    if total_usd == 0:
        return {
            'productos': [],
            'resumen': {
                'A': {'cantidad': 0, 'usd': 0, 'porcentaje_usd': 0},
                'B': {'cantidad': 0, 'usd': 0, 'porcentaje_usd': 0},
                'C': {'cantidad': 0, 'usd': 0, 'porcentaje_usd': 0},
            },
            'total_usd': 0,
            'total_productos': 0,
        }

    acumulado = 0.0
    for p in productos:
        acumulado += p['usd']
        pct_acum = (acumulado / total_usd) * 100
        p['pct_acumulado'] = round(pct_acum, 2)
        p['pct_participacion'] = round((p['usd'] / total_usd) * 100, 2)

        if pct_acum <= 80:
            p['clase'] = 'A'
        elif pct_acum <= 95:
            p['clase'] = 'B'
        else:
            p['clase'] = 'C'

    resumen = {'A': {'cantidad': 0, 'usd': 0}, 'B': {'cantidad': 0, 'usd': 0}, 'C': {'cantidad': 0, 'usd': 0}}
    for p in productos:
        resumen[p['clase']]['cantidad'] += 1
        resumen[p['clase']]['usd'] += p['usd']

    for clase in ['A', 'B', 'C']:
        resumen[clase]['usd'] = round(resumen[clase]['usd'], 2)
        resumen[clase]['porcentaje_usd'] = round(
            (resumen[clase]['usd'] / total_usd) * 100, 2
        )

    return {
        'productos': productos,
        'resumen': resumen,
        'total_usd': round(total_usd, 2),
        'total_productos': len(productos),
    }


def resumen_por_cuadrante(tienda, desde, hasta):
    """Ingreso y unidades agrupado por cuadrante del producto."""
    qs = (
        Ventas.todos
        .filter(tienda=tienda, fecha__gte=desde, fecha__lte=hasta)
        .values('codigo_producto__cuadrante')
        .annotate(usd=Sum(INGRESO), unidades=Sum('cantidad_vendida'), transacciones=Count('id_venta'))
        .order_by('-usd')
    )
    return [
        {
            'cuadrante': r['codigo_producto__cuadrante'] or 'Sin asignar',
            'usd': float(r['usd'] or 0),
            'unidades': r['unidades'] or 0,
            'transacciones': r['transacciones'] or 0,
        }
        for r in qs
    ]