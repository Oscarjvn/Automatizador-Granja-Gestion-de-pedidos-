import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'configuraciones.settings')
django.setup()

from nucleo.models import Tienda, Producto, InventarioProducto, Lote, Pedido, DetallePedido



# 2. Crear un Producto
producto = Producto.objects.create(
    sku="SKU-001",
    nombre="Producto Test 001",
    categoria="Pruebas",
    unidad_empaque=1
)

# 3. Crear un Inventario
inventario = InventarioProducto.objects.create(
   
    stock_actual=10,
    stock_min=2,
    stock_max=20
)

# 4. Crear un Lote
lote = Lote.objects.create(
    codigo_lote="LOTE-2026-001",
    fecha_vencimiento="2026-12-31",
    cantidad=100
)

# 5. Crear un Pedido
pedido = Pedido.objects.create(estatus="PENDIENTE")

# 6. Crear un Detalle
detalle = DetallePedido.objects.create(
   
    cant_sugerida=5
)

print("¡Carga mínima de 1 registro por tabla completada con éxito!")