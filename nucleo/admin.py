from django.contrib import admin
from .models import Tienda, Producto, InventarioProducto, Lote, Pedido, DetallePedido
# Register your models here.
# Esto hace que las tablas aparezcan en el panel web
admin.site.register(Tienda)
admin.site.register(Producto)
admin.site.register(InventarioProducto)
admin.site.register(Lote)
admin.site.register(Pedido)
admin.site.register(DetallePedido)