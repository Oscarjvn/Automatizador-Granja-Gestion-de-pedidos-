import json
import logging
from datetime import date, timedelta
from pathlib import Path

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class APIError(Exception):
    """Error al comunicarse con la API de ventas."""
    pass


def descargar_ventas(fecha, sucursal=None, timeout=30):
    """
    Descarga las ventas de un día desde la API del POS.

    Retorna: dict con la respuesta cruda de la API.
    Lanza: APIError si falla la descarga.
    """
    url = settings.VENTAS_API_URL
    sucursal = sucursal or settings.VENTAS_SUCURSAL_DEFAULT

    payload = {
        'sucursal': sucursal,
        'fecha_desde': fecha.isoformat(),
        'fecha_hasta': fecha.isoformat(),
        'hora_desde': '00:00',
        'hora_hasta': '23:59',
    }

    logger.info(f"Descargando ventas: {sucursal} / {fecha}")

    try:
        response = requests.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
    except requests.exceptions.ConnectionError as e:
        raise APIError(f"Error de conexión con {url}: {e}")
    except requests.exceptions.Timeout:
        raise APIError(f"Timeout ({timeout}s) al llamar a {url}")
    except requests.exceptions.HTTPError as e:
        raise APIError(f"HTTP error {response.status_code}: {e}")
    except requests.exceptions.RequestException as e:
        raise APIError(f"Error inesperado: {e}")

    try:
        data = response.json()
    except json.JSONDecodeError as e:
        raise APIError(f"Respuesta no es JSON válido: {e}")

    if 'ventas' not in data:
        raise APIError("Respuesta no tiene clave 'ventas'")

    cantidad = len(data['ventas'])
    logger.info(f"Descargadas {cantidad} ventas")

    return data


def ruta_json_crudo(fecha):
    """Devuelve la ruta donde guardar el JSON crudo del día."""
    base = Path(settings.VENTAS_JSON_DIR) / 'crudos'
    base.mkdir(parents=True, exist_ok=True)
    return base / f'ventas_{fecha.isoformat()}.json'