"""
Predicción de ventas por producto para los productos más vendidos.

Para cada uno de los N productos con más unidades vendidas en la tienda se
ajusta un modelo de suavizamiento exponencial y se pronostican las unidades
de los próximos días. El modelo se elige según el historial disponible:

    Historial del producto        Modelo
    21 días o más                 Holt-Winters (tendencia amortiguada +
                                  estacionalidad semanal aditiva)
    7 a 20 días                   Holt (tendencia amortiguada, sin estacionalidad)
    menos de 7 días               Promedio diario simple

La precisión se mide con una validación hacia atrás: se reservan los últimos
7 días, se ajusta el modelo con el resto y se compara lo pronosticado con lo
vendido realmente. Precisión = 1 − WAPE, donde
WAPE = Σ|real − pronóstico| / Σ real.
"""
import warnings
from datetime import timedelta

import numpy as np
import pandas as pd
from django.core.cache import cache
from django.db.models import Max, Sum
from statsmodels.tsa.holtwinters import ExponentialSmoothing

from nucleo.models import InventarioProducto, Producto, Ventas

DIAS_VALIDACION = 7
MIN_HOLT_WINTERS = 21
MIN_HOLT = 7


def _ajustar(serie):
    """Devuelve (modelo_ajustado, nombre_metodo) o (None, 'Promedio')."""
    n = len(serie)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        if n >= MIN_HOLT_WINTERS and serie.sum() > 0:
            try:
                modelo = ExponentialSmoothing(
                    serie, trend='add', damped_trend=True,
                    seasonal='add', seasonal_periods=7,
                    initialization_method='estimated',
                ).fit(optimized=True)
                return modelo, 'Holt-Winters'
            except Exception:
                pass
        if n >= MIN_HOLT and serie.sum() > 0:
            try:
                modelo = ExponentialSmoothing(
                    serie, trend='add', damped_trend=True,
                    initialization_method='estimated',
                ).fit(optimized=True)
                return modelo, 'Holt'
            except Exception:
                pass
    return None, 'Promedio'


def pronosticar_serie(serie, horizonte):
    """
    Pronostica `horizonte` días de una serie diaria de unidades.

    Retorna (lista_de_valores, metodo). Los valores nunca son negativos.
    """
    modelo, metodo = _ajustar(serie)
    if modelo is None:
        promedio = float(serie.mean()) if len(serie) else 0.0
        return [promedio] * horizonte, metodo
    valores = np.asarray(modelo.forecast(horizonte), dtype=float)
    return [max(float(v), 0.0) for v in valores], metodo


def precision_validacion(serie):
    """
    Precisión del modelo sobre los últimos 7 días reservados (1 − WAPE).
    Devuelve None si no hay historial suficiente para validar.
    """
    if len(serie) < MIN_HOLT + DIAS_VALIDACION:
        return None
    entrenamiento = serie.iloc[:-DIAS_VALIDACION]
    real = serie.iloc[-DIAS_VALIDACION:].to_numpy(dtype=float)
    pronostico, _ = pronosticar_serie(entrenamiento, DIAS_VALIDACION)
    total = real.sum()
    if total <= 0:
        return None
    wape = np.abs(real - np.asarray(pronostico)).sum() / total
    return round(float(max(0.0, 1.0 - wape)), 3)


def top_productos(tienda, desde, hasta, n=20):
    """SKU de los n productos con más unidades vendidas en el periodo."""
    filas = (
        Ventas.todos
        .filter(tienda=tienda, fecha__gte=desde, fecha__lte=hasta)
        .values('codigo_producto')
        .annotate(unidades=Sum('cantidad_vendida'))
        .order_by('-unidades', 'codigo_producto')[:n]
    )
    return [(f['codigo_producto'], int(f['unidades'] or 0)) for f in filas]


def _series_diarias(tienda, skus, desde, hasta):
    """
    {sku: pd.Series diaria de unidades}, en una sola consulta.
    Cada serie empieza el día de la primera venta del producto dentro del
    periodo y rellena con 0 los días sin ventas.
    """
    filas = (
        Ventas.todos
        .filter(tienda=tienda, codigo_producto__in=skus, fecha__gte=desde, fecha__lte=hasta)
        .values('codigo_producto', 'fecha')
        .annotate(unidades=Sum('cantidad_vendida'))
    )
    datos = {}
    for f in filas:
        datos.setdefault(f['codigo_producto'], {})[pd.Timestamp(f['fecha'])] = float(f['unidades'] or 0)

    series = {}
    fin = pd.Timestamp(hasta)
    for sku, puntos in datos.items():
        inicio = min(puntos)
        indice = pd.date_range(inicio, fin, freq='D')
        series[sku] = pd.Series(puntos).reindex(indice, fill_value=0.0).astype(float)
    return series


def predecir_top_productos(tienda, n=20, dias_historico=90, horizonte=14, usar_cache=True):
    """
    Pronóstico de unidades para los n productos más vendidos de la tienda.

    El historial termina en la fecha de la última venta registrada en la
    tienda, para no confundir con ceros los días que aún no se sincronizan.
    """
    ultima = Ventas.todos.filter(tienda=tienda).aggregate(m=Max('fecha'))['m']
    vacio = {
        'ok': False, 'items': [], 'horizonte': horizonte, 'dias_historico': dias_historico,
        'fecha_corte': ultima, 'error': 'No hay ventas registradas para esta tienda.',
    }
    if ultima is None:
        return vacio

    clave = f'pred_top:{tienda.pk}:{ultima.isoformat()}:{n}:{dias_historico}:{horizonte}'
    if usar_cache:
        guardado = cache.get(clave)
        if guardado is not None:
            return guardado

    hasta = ultima
    desde = hasta - timedelta(days=dias_historico - 1)
    top = top_productos(tienda, desde, hasta, n=n)
    if not top:
        return vacio

    skus = [sku for sku, _ in top]
    series = _series_diarias(tienda, skus, desde, hasta)
    inventarios = {
        inv.producto.sku: inv
        for inv in InventarioProducto.todos
        .filter(tienda=tienda, producto__sku__in=skus)
        .select_related('producto')
    }
    productos = {p.sku: p for p in Producto.objects.filter(sku__in=skus)}

    fechas_futuras = [hasta + timedelta(days=i) for i in range(1, horizonte + 1)]
    items = []
    for posicion, (sku, unidades) in enumerate(top, start=1):
        serie = series.get(sku, pd.Series(dtype=float))
        pronostico, metodo = pronosticar_serie(serie, horizonte)
        ultimos_28 = serie.iloc[-28:] if len(serie) else serie
        prom_hist = float(ultimos_28.mean()) if len(ultimos_28) else 0.0
        prom_pred = float(np.mean(pronostico)) if pronostico else 0.0
        total_7 = float(sum(pronostico[:7]))
        variacion = ((prom_pred - prom_hist) / prom_hist * 100) if prom_hist > 0 else 0.0

        inv = inventarios.get(sku)
        stock = inv.stock_actual if inv else None
        cobertura = round(stock / prom_pred, 1) if (stock is not None and prom_pred > 0) else None

        items.append({
            'posicion': posicion,
            'sku': sku,
            'nombre': productos[sku].nombre if sku in productos else sku,
            'cuadrante': productos[sku].cuadrante if sku in productos else '',
            'unidades_periodo': unidades,
            'dias_historial': len(serie),
            'promedio_historico': round(prom_hist, 2),
            'promedio_pronostico': round(prom_pred, 2),
            'total_7_dias': round(total_7, 1),
            'total_horizonte': round(float(sum(pronostico)), 1),
            'variacion_pct': round(variacion, 1),
            'tendencia': 'up' if variacion > 5 else ('down' if variacion < -5 else 'stable'),
            'metodo': metodo,
            'precision': precision_validacion(serie),
            'stock_actual': stock,
            'dias_cobertura': cobertura,
            # El stock no alcanza para lo que se espera vender en 7 días
            'riesgo_quiebre': stock is not None and stock < total_7,
            'historico': [
                {'fecha': f.date().isoformat(), 'unidades': round(float(v), 1)}
                for f, v in ultimos_28.items()
            ],
            'pronostico': [
                {'fecha': f.isoformat(), 'unidades': round(v, 1)}
                for f, v in zip(fechas_futuras, pronostico)
            ],
        })

    precisiones = [i['precision'] for i in items if i['precision'] is not None]
    resultado = {
        'ok': True,
        'error': None,
        'items': items,
        'horizonte': horizonte,
        'dias_historico': dias_historico,
        'fecha_corte': hasta,
        'total_unidades_pronostico': round(sum(i['total_horizonte'] for i in items), 1),
        'productos_en_riesgo': sum(1 for i in items if i['riesgo_quiebre']),
        'precision_media': round(float(np.mean(precisiones)), 3) if precisiones else None,
    }
    if usar_cache:
        cache.set(clave, resultado, 60 * 60 * 6)
    return resultado
