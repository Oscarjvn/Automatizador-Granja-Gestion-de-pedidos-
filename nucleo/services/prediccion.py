import warnings
from datetime import date, timedelta

import pandas as pd
from django.db.models import DecimalField, ExpressionWrapper, F, Sum
from django.db.models.functions import TruncDate
from statsmodels.tsa.holtwinters import ExponentialSmoothing

from nucleo.models import Ventas


INGRESO = ExpressionWrapper(
    F('cantidad_vendida') * F('precio_usd'),
    output_field=DecimalField(max_digits=15, decimal_places=2),
)


def predecir_ventas(tienda, dias_historico=90, dias_prediccion=14):
    """
    Predice las ventas de los próximos N días usando Holt-Winters.

    Retorna:
      {
        'ok': bool,
        'error': str | None,
        'historico': [{'fecha': 'YYYY-MM-DD', 'usd': float}],
        'prediccion': [{'fecha': 'YYYY-MM-DD', 'usd': float}],
        'tendencia': 'up' | 'down' | 'stable',
        'confianza': float,
        'promedio_historico': float,
        'promedio_predicho': float,
        'dias_historico': int,
        'dias_prediccion': int,
      }
    """
    hoy = date.today()
    desde = hoy - timedelta(days=dias_historico)

    # --- Obtener serie diaria ---
    qs = (
        Ventas.todos
        .filter(tienda=tienda, fecha__gte=desde, fecha__lte=hoy)
        .annotate(dia=TruncDate('fecha'))
        .values('dia')
        .annotate(usd=Sum(INGRESO))
        .order_by('dia')
    )

    rows = [{'ds': r['dia'], 'y': float(r['usd'] or 0)} for r in qs]
    df = pd.DataFrame(rows)

    if len(df) < 14:
        return {
            'ok': False,
            'error': (
                f'Se necesitan al menos 14 días de datos. '
                f'Solo hay {len(df)}.'
            ),
            'historico': [],
            'prediccion': [],
            'tendencia': 'stable',
            'confianza': 0,
            'promedio_historico': 0,
            'promedio_predicho': 0,
            'dias_historico': dias_historico,
            'dias_prediccion': dias_prediccion,
        }

    # --- Rellenar huecos con 0 ---
    df = df.set_index('ds').asfreq('D', fill_value=0).reset_index()

    # --- Ajustar modelo ---
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')

        try:
            # Intento 1: tendencia + estacionalidad semanal
            modelo = ExponentialSmoothing(
                df['y'],
                seasonal_periods=7,
                trend='add',
                seasonal='add',
                initialization_method='estimated',
            ).fit(optimized=True)
        except Exception:
            try:
                # Intento 2: solo tendencia
                modelo = ExponentialSmoothing(
                    df['y'],
                    trend='add',
                    initialization_method='estimated',
                ).fit(optimized=True)
            except Exception as e:
                return {
                    'ok': False,
                    'error': f'No se pudo ajustar el modelo: {e}',
                    'historico': [
                        {'fecha': r['ds'].isoformat(), 'usd': round(r['y'], 2)}
                        for _, r in df.iterrows()
                    ],
                    'prediccion': [],
                    'tendencia': 'stable',
                    'confianza': 0,
                    'promedio_historico': round(df['y'].mean(), 2),
                    'promedio_predicho': 0,
                    'dias_historico': dias_historico,
                    'dias_prediccion': dias_prediccion,
                }

    # --- Predecir ---
    predicciones = modelo.forecast(dias_prediccion)
    fecha_ultimo = df['ds'].iloc[-1]

    prediccion = []
    for i, valor in enumerate(predicciones, start=1):
        fecha_pred = fecha_ultimo + timedelta(days=i)
        prediccion.append({
            'fecha': fecha_pred.isoformat(),
            'usd': round(max(float(valor), 0), 2),
        })

    # --- Tendencia ---
    primeros = df['y'].head(7).mean()
    ultimos = df['y'].tail(7).mean()
    if primeros > 0:
        cambio = (ultimos - primeros) / primeros
        if cambio > 0.05:
            tendencia = 'up'
        elif cambio < -0.05:
            tendencia = 'down'
        else:
            tendencia = 'stable'
    else:
        tendencia = 'stable'

    # --- Confianza (R²) ---
    residuos = df['y'] - modelo.fittedvalues
    ss_res = (residuos ** 2).sum()
    ss_tot = ((df['y'] - df['y'].mean()) ** 2).sum()
    r2 = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

    historico = [
        {'fecha': r['ds'].isoformat(), 'usd': round(r['y'], 2)}
        for _, r in df.iterrows()
    ]

    return {
        'ok': True,
        'error': None,
        'historico': historico,
        'prediccion': prediccion,
        'tendencia': tendencia,
        'confianza': round(max(min(float(r2), 1.0), 0), 3),
        'promedio_historico': round(df['y'].mean(), 2),
        'promedio_predicho': round(
            sum(p['usd'] for p in prediccion) / len(prediccion), 2
        ),
        'dias_historico': dias_historico,
        'dias_prediccion': dias_prediccion,
    }