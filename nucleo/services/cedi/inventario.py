"""
Cliente de la API de inventario del CEDI.

El inventario del CEDI vive en su propio sistema; esta aplicación solo lo
consulta, nunca guarda una copia. Así no hay dos números que se contradigan.

Contrato esperado (ajustar `_interpretar_respuesta` si la API real difiere):

    POST {CEDI_INVENTARIO_URL}
    Authorization: Bearer {CEDI_INVENTARIO_TOKEN}      (si hay token)
    {"skus": ["5000", "5001", ...]}

    Respuesta: lista de productos con su existencia disponible, por ejemplo
    {"productos": [{"sku": "005000", "disponible": 120}, ...]}

El intérprete acepta variantes comunes de nombres de campos y normaliza los
SKU (sin ceros a la izquierda), igual que la carga de ventas del POS.
"""
import hashlib
import json
import logging

import requests
from django.conf import settings

from nucleo.services.ventas.carga import normalizar_sku

logger = logging.getLogger(__name__)

CLAVES_LISTA = ('productos', 'inventario', 'items', 'data')
CLAVES_SKU = ('sku', 'codigo_producto', 'codigo', 'producto')
CLAVES_CANTIDAD = ('disponible', 'existencia', 'stock', 'cantidad')


class InventarioCediNoDisponible(Exception):
    """No se pudo obtener el inventario del CEDI (sin conexión, error o respuesta inválida)."""


def _primero(dic, claves):
    for c in claves:
        if c in dic and dic[c] is not None:
            return dic[c]
    return None


def _interpretar_respuesta(data):
    """Convierte la respuesta de la API en {sku_normalizado: unidades_disponibles}."""
    if isinstance(data, dict):
        lista = _primero(data, CLAVES_LISTA)
    else:
        lista = data
    if not isinstance(lista, list):
        raise InventarioCediNoDisponible('La respuesta del inventario del CEDI no trae una lista de productos.')

    stock = {}
    for fila in lista:
        if not isinstance(fila, dict):
            continue
        sku = _primero(fila, CLAVES_SKU)
        cantidad = _primero(fila, CLAVES_CANTIDAD)
        if sku is None or cantidad is None:
            continue
        try:
            stock[normalizar_sku(str(sku))] = max(int(float(cantidad)), 0)
        except (TypeError, ValueError):
            continue
    return stock


def _stock_simulado(skus):
    """Existencias inventadas pero estables por SKU, solo para desarrollo y demostraciones."""
    niveles = [0, 6, 18, 60, 400]
    return {
        sku: niveles[int(hashlib.sha1(sku.encode()).hexdigest(), 16) % len(niveles)]
        for sku in skus
    }


def consultar_stock_cedi(skus):
    """
    Existencias disponibles en el CEDI para los SKU indicados, en una sola llamada.

    Retorna {sku: unidades}. Un SKU que la API no devuelve no está en el CEDI,
    y quien llama debe tratarlo como 0.
    Lanza InventarioCediNoDisponible si la consulta falla.
    """
    skus = sorted({normalizar_sku(str(s)) for s in skus})
    if not skus:
        return {}
    if getattr(settings, 'CEDI_INVENTARIO_SIMULADO', False):
        return _stock_simulado(skus)

    url = getattr(settings, 'CEDI_INVENTARIO_URL', '')
    if not url:
        raise InventarioCediNoDisponible('La API de inventario del CEDI no está configurada (CEDI_INVENTARIO_URL).')

    timeout = getattr(settings, 'CEDI_INVENTARIO_TIMEOUT', 8)
    headers = {}
    token = getattr(settings, 'CEDI_INVENTARIO_TOKEN', '')
    if token:
        headers['Authorization'] = f'Bearer {token}'

    try:
        respuesta = requests.post(url, json={'skus': skus}, headers=headers, timeout=timeout)
        respuesta.raise_for_status()
        data = respuesta.json()
    except requests.exceptions.Timeout:
        raise InventarioCediNoDisponible(f'El inventario del CEDI no respondió en {timeout} segundos.')
    except requests.exceptions.ConnectionError:
        raise InventarioCediNoDisponible('No hay conexión con el inventario del CEDI.')
    except requests.exceptions.HTTPError:
        raise InventarioCediNoDisponible(f'El inventario del CEDI respondió con error {respuesta.status_code}.')
    except (requests.exceptions.RequestException, json.JSONDecodeError, ValueError) as e:
        raise InventarioCediNoDisponible(f'Respuesta inválida del inventario del CEDI: {e}')

    stock = _interpretar_respuesta(data)
    logger.info('Inventario CEDI consultado: %s SKU solicitados, %s devueltos', len(skus), len(stock))
    return stock
