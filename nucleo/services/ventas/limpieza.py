import json
import logging
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)

CAMPOS_REQUERIDOS = [
    'numero_factura',
    'fecha',
    'hora',
    'producto.codigo_producto',
    'cantidad.cantidad_vendida',
    'financiero.precio_unitario_usd',
]


class LimpiezaError(Exception):
    """Error al limpiar el JSON crudo."""
    pass


def _extraer_campo(venta, campo):
    """
    Extrae 'producto.codigo_producto' de un dict anidado con puntos.
    Soporta tanto dict anidado como clave plana con puntos.
    """
    # Caso 1: clave plana con punto
    if campo in venta:
        return venta[campo]

    # Caso 2: dict anidado
    partes = campo.split('.')
    valor = venta
    for parte in partes:
        if not isinstance(valor, dict) or parte not in valor:
            return None
        valor = valor[parte]
    return valor


def limpiar_ventas(data_crudo):
    """
    Recibe la respuesta cruda de la API y devuelve una lista de dicts
    plana con solo los campos que necesita el cargador.

    Retorna: list[dict]
    Lanza: LimpiezaError si falta la clave 'ventas'.
    """
    if 'ventas' not in data_crudo:
        raise LimpiezaError("JSON crudo no tiene clave 'ventas'")

    ventas = data_crudo['ventas']
    if not isinstance(ventas, list):
        raise LimpiezaError("'ventas' no es una lista")

    limpias = []
    omitidas = 0

    for venta in ventas:
        fila = {}
        for campo in CAMPOS_REQUERIDOS:
            valor = _extraer_campo(venta, campo)
            if valor is None:
                omitidas += 1
                break
            fila[campo] = valor
        else:
            # 'linea' es opcional
            fila['linea'] = venta.get('linea', 1)
            limpias.append(fila)

    if omitidas:
        logger.warning(f"{omitidas} filas omitidas por campos faltantes")

    logger.info(f"Limpias: {len(limpias)} de {len(ventas)}")
    return limpias


def guardar_json_limpio(ventas_limpias, fecha):
    """Guarda el JSON limpio en disco."""
    base = Path(settings.VENTAS_JSON_DIR) / 'limpios'
    base.mkdir(parents=True, exist_ok=True)
    ruta = base / f'ventas_{fecha.isoformat()}.json'

    with open(ruta, 'w', encoding='utf-8') as f:
        json.dump(ventas_limpias, f, ensure_ascii=False, indent=2)

    logger.info(f"JSON limpio guardado: {ruta}")
    return ruta


def cargar_json_limpio(fecha):
    """Carga un JSON limpio previamente guardado."""
    ruta = Path(settings.VENTAS_JSON_DIR) / 'limpios' / f'ventas_{fecha.isoformat()}.json'
    if not ruta.exists():
        raise LimpiezaError(f"No existe JSON limpio: {ruta}")

    with open(ruta, 'r', encoding='utf-8') as f:
        return json.load(f)