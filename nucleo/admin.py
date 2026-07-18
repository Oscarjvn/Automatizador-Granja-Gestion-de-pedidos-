from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from accounts.forms import CustomUserCreationForm, CustomUserChangeForm
from .models import Tienda, Producto, InventarioProducto, Lote, Pedido, DetallePedido, Usuario
# Register your models here.
# Esto hace que las tablas aparezcan en el panel web
admin.site.register(Tienda)
admin.site.register(Producto)
admin.site.register(InventarioProducto)
admin.site.register(Lote)
admin.site.register(Pedido)
admin.site.register(DetallePedido)

# 1. Inline para meter Tienda y Rol en la edición del Usuario nativo
class UsuarioInline(admin.StackedInline):
    model = Usuario
    can_delete = False
    verbose_name_plural = 'Perfil de Tienda y Rol'

class CustomUserAdmin(UserAdmin):
    inlines = (UsuarioInline,)

admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)