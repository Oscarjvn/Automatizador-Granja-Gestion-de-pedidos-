import os
import sys
import django
import pandas as pd

# -------------------------------------------------------------------
# 1. Configurar el entorno de Django
# Reemplaza 'configuraciones.settings' si tu archivo settings.py está en otra carpeta
# -------------------------------------------------------------------
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'configuraciones.settings')
django.setup()

# 2. Importar los modelos LUEGO de inicializar Django
from nucleo.models import InventarioProducto, Tienda, Producto
from django.db import transaction


def cargar_inventario_desde_excel(ruta_excel):
    print(f"Leyendo archivo: {ruta_excel}...")

    try:
        df = pd.read_excel(ruta_excel)

        # 1. Eliminar filas donde la tienda o el sku estén completamente vacíos
        df = df.dropna(subset=['id_tienda', 'sku'])

        # 2. Asegurar que id_tienda y stock_actual sean enteros de Python
        df['id_tienda'] = df['id_tienda'].astype(int)
        df['stock_actual'] = df['stock_actual'].fillna(0).astype(int)

    except Exception as e:
        print(f"❌ Error al leer o procesar la estructura del Excel: {e}")
        return

    creados = 0
    actualizados = 0
    errores = 0

    print("Procesando filas e insertando en la base de datos...")

    with transaction.atomic():
        for index, row in df.iterrows():
            id_tienda = row['id_tienda']
            sku_producto = str(row['sku']).strip() # Asegurar que el SKU sea string sin espacios
            cantidad_stock = row['stock_actual']

            # Validar existencia de Tienda y Producto en la BD
            try:
                instancia_tienda = Tienda.objects.get(pk=id_tienda)
                instancia_producto = Producto.objects.get(pk=sku_producto)
            except Tienda.DoesNotExist:
                print(f"⚠️ Fila {index + 2}: La Tienda con ID '{id_tienda}' no existe en la BD. Omitiendo...")
                errores += 1
                continue
            except Producto.DoesNotExist:
                print(f"⚠️ Fila {index + 2}: El Producto con SKU '{sku_producto}' no existe en la BD. Omitiendo...")
                errores += 1
                continue

            # Crear o actualizar el stock_actual
            obj, created = InventarioProducto.objects.update_or_create(
                tienda=instancia_tienda,
                producto=instancia_producto,
                defaults={
                    'stock_actual': cantidad_stock
                }
            )

            if created:
                creados += 1
            else:
                actualizados += 1

    print("\n--- RESUMEN DE CARGA ---")
    print(f"✅ Registros creados: {creados}")
    print(f"🔄 Registros actualizados: {actualizados}")
    print(f"❌ Errores/Omitidos: {errores}")


if __name__ == "__main__":
    # Nombre exacto de tu archivo Excel
    ARCHIVO_EXCEL = "./anexos/inventario_carga.xlsx"

    if os.path.exists(ARCHIVO_EXCEL):
        cargar_inventario_desde_excel(ARCHIVO_EXCEL)
    else:
        print(f"❌ El archivo '{ARCHIVO_EXCEL}' no está en la raíz del proyecto.")