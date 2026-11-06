from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from accounts.forms import CustomUserCreationForm, CustomUserChangeForm
from .models import Tienda, Producto, InventarioProducto, Lote, Pedido, DetallePedido, Usuario, Ventas, AnalisisReposicion, InventarioCedi
# Register your models here.
# Esto hace que las tablas aparezcan en el panel web
@admin.register(Tienda)
class TiendaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'codigo_sucursal', 'direccion')
    search_fields = ('nombre', 'codigo_sucursal')


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('sku', 'nombre', 'categoria', 'cuadrante', 'lead_time_dias',
                    'dias_stock_seguridad', 'ciclo_reposicion_dias', 'dias_historial_ventas')
    list_filter = ('cuadrante', 'categoria')
    search_fields = ('sku', 'nombre', 'barra')
    ordering = ('nombre',)


@admin.register(InventarioProducto)
class InventarioProductoAdmin(admin.ModelAdmin):
    list_display = ('producto', 'tienda', 'stock_actual')
    list_filter = ('tienda',)
    search_fields = ('producto__sku', 'producto__nombre')
    list_select_related = ('producto', 'tienda')

    def get_queryset(self, request):
        return InventarioProducto.todos.all()


@admin.register(Lote)
class LoteAdmin(admin.ModelAdmin):
    list_display = ('producto', 'tienda', 'cantidad', 'fecha_vencimiento', 'codigo_lote', 'pedido_origen')
    list_filter = ('tienda',)
    search_fields = ('producto__sku', 'producto__nombre', 'codigo_lote')
    date_hierarchy = 'fecha_vencimiento'
    list_select_related = ('producto', 'tienda')

    def get_queryset(self, request):
        return Lote.todos.all()


class DetallePedidoInline(admin.TabularInline):
    """Líneas del pedido de solo lectura: las cantidades cambian solo por el flujo del sistema."""
    model = DetallePedido
    extra = 0
    can_delete = False
    fields = ('producto', 'cant_sugerida', 'cant_ajustada', 'cant_despachada', 'motivo_ajuste',
              'stock_cedi_al_despachar', 'cant_recibida')
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ('numero', 'tienda', 'estatus', 'usuario', 'fecha_creacion', 'fecha_aprobacion',
                    'fecha_despacho', 'despachado_por', 'fecha_recepcion')
    list_filter = ('estatus', 'tienda')
    date_hierarchy = 'fecha_creacion'
    list_select_related = ('tienda', 'usuario', 'despachado_por')
    inlines = (DetallePedidoInline,)
    # El estado y las fechas solo cambian con el flujo del sistema (aprobar, despachar, recibir),
    # para que nadie pueda saltarse sus validaciones desde el admin.
    readonly_fields = ('estatus', 'fecha_creacion', 'fecha_aprobacion', 'fecha_despacho', 'despachado_por', 'fecha_recepcion')

    @admin.display(description='Pedido', ordering='pk')
    def numero(self, obj):
        return f'#{obj.pk}'

    def get_queryset(self, request):
        return Pedido.todos.all()


@admin.register(DetallePedido)
class DetallePedidoAdmin(admin.ModelAdmin):
    list_display = ('pedido', 'producto', 'cant_sugerida', 'cant_ajustada', 'cant_despachada',
                    'cant_recibida', 'motivo_ajuste')
    list_filter = ('motivo_ajuste',)
    search_fields = ('producto__sku', 'producto__nombre')
    list_select_related = ('pedido', 'producto')


@admin.register(Ventas)
class VentasAdmin(admin.ModelAdmin):
    list_display = ('numero_factura', 'fecha', 'hora', 'tienda', 'codigo_producto', 'cantidad_vendida', 'precio_usd')
    list_filter = ('tienda',)
    search_fields = ('numero_factura', 'codigo_producto__sku', 'codigo_producto__nombre')
    date_hierarchy = 'fecha'
    list_select_related = ('tienda', 'codigo_producto')

    def get_queryset(self, request):
        return Ventas.todos.all()

# 1. Inline para meter Tienda y Rol en la edición del Usuario nativo
class UsuarioInline(admin.StackedInline):
    model = Usuario
    can_delete = False
    verbose_name_plural = 'Perfil de Tienda y Rol'

class CustomUserAdmin(UserAdmin):
    inlines = (UsuarioInline,)
    list_display = ('username', 'first_name', 'last_name', 'rol', 'tienda', 'is_staff', 'is_active')
    list_select_related = ('usuario', 'usuario__tienda')

    @admin.display(description='Rol')
    def rol(self, obj):
        perfil = getattr(obj, 'usuario', None)
        return perfil.get_rol_display() if perfil else '—'

    @admin.display(description='Tienda')
    def tienda(self, obj):
        perfil = getattr(obj, 'usuario', None)
        if perfil is None:
            return '—'
        return perfil.tienda or 'Centro de distribución'


admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


@admin.register(InventarioCedi)
class InventarioCediAdmin(admin.ModelAdmin):
    """Existencias del CEDI para la fuente local (datos de prueba)."""
    list_display = ('producto', 'disponible', 'actualizado')
    list_editable = ('disponible',)
    search_fields = ('producto__sku', 'producto__nombre')
    list_select_related = ('producto',)
    ordering = ('producto__nombre',)
