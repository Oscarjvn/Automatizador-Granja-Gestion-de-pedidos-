import os
import django
import pandas as pd

# Configurar entorno Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'configuraciones.settings')
django.setup()

from nucleo.models import Producto
from django.db import transaction

def cargar_productos_excel(archivo_path):
    # Leer el archivo Excel
    df = pd.read_excel(archivo_path, sheet_name='MAESTRO')
    
    creados=0
    actualizados= 0
    contador = 0
    with transaction.atomic():
        for _, fila in df.iterrows():
            obj, created = Producto.objects.update_or_create(
            sku=str(fila['sku']).strip(),
            defaults={
                'nombre': fila['nombre'],
                'cuadrante': fila['cuadrante'],
                'barra': fila['barra'],
                'unidad_empaque': fila['unidad_empaque']
            }
        )
        creados += created
        actualizados += not created
            
    print(f"✅ Proceso finalizado. Se creados {creados} productos nuevos, actualizados{actualizados}.")

if __name__ == "__main__":
    cargar_productos_excel("./anexos/maestro_productos.xlsx") # Asegúrate de que el archivo esté en la raíz