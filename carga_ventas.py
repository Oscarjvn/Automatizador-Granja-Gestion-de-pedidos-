import json
import os
import django

# Configurar entorno de Django (si lo ejecutas como script standalone)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'configuraciones.settings')  # Ajusta 'config' al nombre de tu carpeta principal
django.setup()

from django.db import transaction
from nucleo.models import Ventas  # Ajusta 'nucleo' a la app donde esté el modelo


def cargar_ventas_db():
    ruta_json = 'datos/ventas_limpias.json'

    if not os.path.exists(ruta_json):
        print(f"❌ Error: No se encontró el archivo {ruta_json}")
        return

    with open(ruta_json, 'r', encoding='utf-8') as archivo:
        ventas_data = json.load(archivo)

    registros_a_crear = []

    for item in ventas_data:
        venta = Ventas(
            numero_factura=item['numero_factura'],
            fecha=item['fecha'],
            hora=item['hora'],
            cantidad_vendida=item['cantidad.cantidad_vendida'],
            precio_usd=item['financiero.precio_unitario_usd'],
            
            # Asignación directa a las Foreign Keys usando el sufijo '_id':
            codigo_producto_id=item['producto.codigo_producto'],       # Coincide con to_field='sku'
            tienda_id=1           # Coincide con db_column='id_tienda'
        )
        #registros_a_crear.append(venta)
        print(venta)

    # Inserción atómica masiva para garantizar consistencia y rendimiento
    #with transaction.atomic():
    #    Ventas.objects.bulk_create(registros_a_crear)

    print(f"🎉 Se insertaron {len(registros_a_crear)} registros en la tabla Ventas exitosamente.")


if __name__ == '__main__':
    cargar_ventas_db()