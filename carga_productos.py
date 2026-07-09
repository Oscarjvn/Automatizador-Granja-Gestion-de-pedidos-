import os
import django
import pandas as pd

# Configurar entorno Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'configuraciones.settings')
django.setup()

from nucleo.models import Producto

def cargar_productos_excel(archivo_path):
    # Leer el archivo Excel
    df = pd.read_excel(archivo_path)
    
    contador = 0
    for _, fila in df.iterrows():
        # Usamos update_or_create para evitar errores de duplicados (como el que tuviste antes)
        obj, created = Producto.objects.update_or_create(
            sku=fila['sku'],
            defaults={
                'nombre': fila['nombre'],
                'categoria': fila['categoria'],
                'unidad_empaque': fila['unidad_empaque']
            }
        )
        if created:
            contador += 1
            
    print(f"✅ Proceso finalizado. Se cargaron {contador} productos nuevos.")

if __name__ == "__main__":
    cargar_productos_excel("./anexos/carga_productos.xlsx") # Asegúrate de que el archivo esté en la raíz