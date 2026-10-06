from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Count, Sum, F, DecimalField, ExpressionWrapper
from django.db.models.functions import TruncDate, TruncWeek, TruncMonth, ExtractHour, ExtractWeekDay

from nucleo.models import Ventas


# Expresión reutilizable: cantidad * precio = ingreso por línea
INGRESO = ExpressionWrapper(
    F('cantidad_vendida') * F('precio_usd'),
    output_field=DecimalField(max_digits=15, decimal_places=2),
)


def _base_qs(tienda, desde, hasta):
    return Ventas.todos.filter(
        tienda=tienda,
        fecha__gte=desde,
        fecha__lte=hasta,
    )


def kpis_periodo(tienda, desde, hasta):
    """KPIs agregados del período."""
    qs = _base_qs(tienda, desde, hasta)
    agg = qs.aggregate(
        total_usd=Sum(INGRESO),
        total_unidades=Sum('cantidad_vendida'),
        total_transacciones=Count('id_venta'),
    )
    total_usd = agg['total_usd'] or Decimal('0')
    total_trans = agg['total_transacciones'] or 0
    ticket_promedio = (total_usd / total_trans) if total_trans else Decimal('0')

    return {
        'total_usd': float(total_usd),
        'total_unidades': agg['total_unidades'] or 0,
        'total_transacciones': total_trans,
        'ticket_promedio': float(ticket_promedio),
    }


def serie_diaria(tienda, desde, hasta):
    """Ventas por día."""
    qs = (
        _base_qs(tienda, desde, hasta)
        .annotate(dia=TruncDate('fecha'))
        .values('dia')
        .annotate(
            usd=Sum(INGRESO),
            unidades=Sum('cantidad_vendida'),
        )
        .order_by('dia')
    )
    return [
        {
            'fecha': row['dia'].isoformat(),
            'usd': float(row['usd'] or 0),
            'unidades': row['unidades'] or 0,
        }
        for row in qs
    ]


def serie_semanal(tienda, desde, hasta):
    qs = (
        _base_qs(tienda, desde, hasta)
        .annotate(semana=TruncWeek('fecha'))
        .values('semana')
        .annotate(usd=Sum(INGRESO), unidades=Sum('cantidad_vendida'))
        .order_by('semana')
    )
    return [
        {
            'fecha': row['semana'].isoformat(),
            'usd': float(row['usd'] or 0),
            'unidades': row['unidades'] or 0,
        }
        for row in qs
    ]


def serie_mensual(tienda, desde, hasta):
    qs = (
        _base_qs(tienda, desde, hasta)
        .annotate(mes=TruncMonth('fecha'))
        .values('mes')
        .annotate(usd=Sum(INGRESO), unidades=Sum('cantidad_vendida'))
        .order_by('mes')
    )
    return [
        {
            'fecha': row['mes'].isoformat()[:7],  # YYYY-MM
            'usd': float(row['usd'] or 0),
            'unidades': row['unidades'] or 0,
        }
        for row in qs
    ]


def distribucion_dia_semana(tienda, desde, hasta):
    """Ventas por día de la semana (1=domingo en Postgres)."""
    qs = (
        _base_qs(tienda, desde, hasta)
        .annotate(dow=ExtractWeekDay('fecha'))
        .values('dow')
        .annotate(usd=Sum(INGRESO), unidades=Sum('cantidad_vendida'))
        .order_by('dow')
    )
    nombres = ['Domingo', 'Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado']
    resultado = {i: {'dia': nombres[i-1], 'usd': 0, 'unidades': 0} for i in range(1, 8)}
    for row in qs:
        resultado[row['dow']] = {
            'dia': nombres[row['dow'] - 1],
            'usd': float(row['usd'] or 0),
            'unidades': row['unidades'] or 0,
        }
    return list(resultado.values())


def distribucion_por_hora(tienda, desde, hasta):
    qs = (
        _base_qs(tienda, desde, hasta)
        .annotate(hora_dia=ExtractHour('hora'))     
        .values('hora_dia')                          
        .annotate(usd=Sum(INGRESO), unidades=Sum('cantidad_vendida'))
        .order_by('hora_dia')
    )
    resultado = {h: {'hora': h, 'usd': 0.0, 'unidades': 0} for h in range(24)}
    for row in qs:
        if row['hora_dia'] is not None:
            resultado[row['hora_dia']] = {
                'hora': row['hora_dia'],
                'usd': float(row['usd'] or 0),
                'unidades': row['unidades'] or 0,
            }
    return [resultado[h] for h in range(24) if resultado[h]['unidades'] > 0]