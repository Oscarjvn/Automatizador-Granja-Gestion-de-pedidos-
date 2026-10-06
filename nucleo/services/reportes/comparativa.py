from decimal import Decimal

from django.db.models import Sum, F, DecimalField, ExpressionWrapper

from nucleo.models import Ventas


INGRESO = ExpressionWrapper(
    F('cantidad_vendida') * F('precio_usd'),
    output_field=DecimalField(max_digits=15, decimal_places=2),
)


def _totales(tienda, desde, hasta):
    qs = Ventas.todos.filter(tienda=tienda, fecha__gte=desde, fecha__lte=hasta)
    agg = qs.aggregate(
        usd=Sum(INGRESO),
        unidades=Sum('cantidad_vendida'),
    )
    return {
        'usd': float(agg['usd'] or 0),
        'unidades': agg['unidades'] or 0,
    }


def _variacion(actual, anterior):
    if anterior == 0:
        return 100.0 if actual > 0 else 0.0
    return round(((actual - anterior) / anterior) * 100, 2)


def comparar_periodos(tienda, p1_desde, p1_hasta, p2_desde, p2_hasta):
    """Compara dos períodos y devuelve totales + variación."""
    actual = _totales(tienda, p2_desde, p2_hasta)
    anterior = _totales(tienda, p1_desde, p1_hasta)

    return {
        'periodo_actual': {
            'desde': p2_desde.isoformat(),
            'hasta': p2_hasta.isoformat(),
            'usd': actual['usd'],
            'unidades': actual['unidades'],
        },
        'periodo_anterior': {
            'desde': p1_desde.isoformat(),
            'hasta': p1_hasta.isoformat(),
            'usd': anterior['usd'],
            'unidades': anterior['unidades'],
        },
        'variacion_usd': _variacion(actual['usd'], anterior['usd']),
        'variacion_unidades': _variacion(actual['unidades'], anterior['unidades']),
    }


def variacion_por_cuadrante(tienda, p1_desde, p1_hasta, p2_desde, p2_hasta):
    """Variación del ingreso por cuadrante entre dos períodos."""

    def totales(tienda, desde, hasta):
        qs = (
            Ventas.todos
            .filter(tienda=tienda, fecha__gte=desde, fecha__lte=hasta)
            .values('codigo_producto__cuadrante')
            .annotate(usd=Sum(INGRESO))
        )
        return {r['codigo_producto__cuadrante'] or 'Sin asignar': float(r['usd'] or 0) for r in qs}

    actual = totales(tienda, p2_desde, p2_hasta)
    anterior = totales(tienda, p1_desde, p1_hasta)

    cuadrantes = set(actual.keys()) | set(anterior.keys())
    resultado = []
    for c in sorted(cuadrantes):
        a = actual.get(c, 0)
        b = anterior.get(c, 0)
        resultado.append({
            'cuadrante': c,
            'actual': a,
            'anterior': b,
            'variacion': _variacion(a, b),
        })

    resultado.sort(key=lambda x: -x['actual'])
    return resultado


def variacion_top_productos(tienda, p1_desde, p1_hasta, p2_desde, p2_hasta, limite=15):
    """Productos con mayor variación (positiva o negativa) entre períodos."""

    def totales(tienda, desde, hasta):
        qs = (
            Ventas.todos
            .filter(tienda=tienda, fecha__gte=desde, fecha__lte=hasta)
            .values('codigo_producto__sku', 'codigo_producto__nombre')
            .annotate(usd=Sum(INGRESO))
        )
        return {
            r['codigo_producto__sku']: {
                'nombre': r['codigo_producto__nombre'],
                'usd': float(r['usd'] or 0),
            }
            for r in qs
        }

    actual = totales(tienda, p2_desde, p2_hasta)
    anterior = totales(tienda, p1_desde, p1_hasta)

    skus = set(actual.keys()) | set(anterior.keys())
    resultado = []
    for sku in skus:
        a = actual.get(sku, {}).get('usd', 0)
        b = anterior.get(sku, {}).get('usd', 0)
        nombre = actual.get(sku, {}).get('nombre') or anterior.get(sku, {}).get('nombre', '')
        # Solo productos con movimiento en alguno de los dos períodos
        if a == 0 and b == 0:
            continue
        resultado.append({
            'sku': sku,
            'nombre': nombre,
            'actual': a,
            'anterior': b,
            'variacion': _variacion(a, b),
            'variacion_abs': round(a - b, 2),
        })

    # Ordenar por valor absoluto de la variación
    resultado.sort(key=lambda x: -abs(x['variacion_abs']))
    return resultado[:limite]