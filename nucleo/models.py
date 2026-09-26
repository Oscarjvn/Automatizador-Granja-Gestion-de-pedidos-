from django.db import models
from django.contrib.auth.models import User
from django.conf import settings
from nucleo.managers import TenantManager

class Tienda(models.Model):
    id_tienda = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100)
    codigo_sucursal = models.CharField(unique=True, max_length=10)
    direccion = models.TextField(blank=True, null=True)

    class Meta:
        managed = True # <--- Activado
        db_table = 'tienda'
    
    def __str__(self):
        return self.nombre

class Producto(models.Model):
    id_producto = models.AutoField(primary_key=True)
    sku = models.CharField(unique=True, max_length=20)
    nombre = models.CharField(max_length=150)
    categoria = models.CharField(max_length=50, blank=True, null=True)
    unidad_empaque = models.IntegerField(blank=True, null=True)
    barra= models.CharField(max_length=100)
    lead_time_dias= models.IntegerField(default=1)
    dias_stock_seguridad= models.IntegerField(default=1)
    ciclo_reposicion_dias= models.IntegerField(default=3)
    dias_historial_ventas= models.IntegerField(default=30)

    class Meta:
        managed = True
        db_table = 'producto'

    def __str__(self):
        return f"{self.sku} - {self.nombre}"

class InventarioProducto(models.Model):
    id_inv_prod = models.AutoField(primary_key=True)
    tienda = models.ForeignKey(Tienda, models.CASCADE, db_column='id_tienda')
    producto = models.ForeignKey(Producto, models.CASCADE, db_column='sku')
    stock_actual = models.IntegerField(default=0)

    objects = TenantManager()
    todos= models.Manager()


    class Meta:
        managed = True
        db_table = 'inventario_producto'
        unique_together = (('tienda', 'producto'),)
        base_manager_name= 'todos'

class Lote(models.Model):
    id_lote = models.AutoField(primary_key=True)
    tienda = models.ForeignKey(Tienda, models.CASCADE, db_column='id_tienda')
    producto = models.ForeignKey(Producto, models.CASCADE, db_column='id_producto')
    codigo_lote = models.CharField(max_length=50, blank=True, null=True)
    fecha_vencimiento = models.DateField()

    objects= TenantManager()
    todos= models.Manager()

    class Meta:
        managed = True
        db_table = 'lote'
        base_manager_name= 'todos'

class Pedido(models.Model):
    id_pedido = models.AutoField(primary_key=True)
    tienda = models.ForeignKey(Tienda, models.PROTECT, db_column='id_tienda')
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.PROTECT, 
        related_name='pedidos'
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True) 
    estatus = models.CharField(max_length=20, default='PENDIENTE')

    objects= TenantManager()
    todos= models.Manager()
    class Meta:
        managed = True
        db_table = 'pedido'
        base_manager_name= 'todos'

class DetallePedido(models.Model):
    id_detalle = models.AutoField(primary_key=True)
    pedido = models.ForeignKey(Pedido, models.CASCADE, db_column='id_pedido', related_name='detalles')
    producto = models.ForeignKey(Producto, models.PROTECT, db_column='id_producto')
    cant_sugerida = models.IntegerField()
    cant_ajustada = models.IntegerField(blank=True, null=True)
    cant_recibida = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'detalle_pedido'

class Usuario(models.Model):
    usuario= models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True)
    tienda= models.ForeignKey('Tienda', on_delete=models.CASCADE, db_column='id_tienda')
    rol = models.CharField(max_length=20)

    class Meta:
        db_table = 'usuario'
    
    def __str__(self):
        return self.usuario.username


class Ventas(models.Model):
    id_venta= models.AutoField(primary_key=True)
    numero_factura= models.CharField(max_length=100)
    fecha= models.DateField()
    hora= models.TimeField()
    #conexion de esta tabla con tabla Productos
    codigo_producto= models.ForeignKey(Producto, on_delete=models.PROTECT, db_column='sku', to_field='sku')
    cantidad_vendida= models.IntegerField()
    precio_usd= models.DecimalField(max_digits=10, decimal_places=2)
    #conexion con Tienda
    tienda = models.ForeignKey(Tienda, on_delete=models.PROTECT, db_column='id_tienda')

    objects=TenantManager()
    todos= models.Manager()

    class Meta: 
        
        base_manager_name = 'todos'
        indexes = [
            models.Index(fields=['tienda', 'codigo_producto', 'fecha']),
            models.Index(fields=['fecha']),
        ]

    def __str__(self):
        return f"Factura N° {self.numero_factura} - {self.fecha} - {self.hora} - {self.codigo_productoç}"



class AnalisisReposicion(models.Model):
    # ============================================
    # IDENTIDAD: 1 análisis por cada "producto en tienda"
    # ============================================
    inventario = models.OneToOneField(
        InventarioProducto,
        on_delete=models.CASCADE,
        db_column='id_inv_prod',
        related_name='analisis_reposicion',
        primary_key=True,
        help_text='Producto en tienda al que pertenece este análisis.'
    )

    # ============================================
    # TRAZABILIDAD: cuándo se calculó por última vez
    # ============================================
    fecha_actualizacion = models.DateTimeField(
        auto_now=True,
        help_text='Última vez que se recalculó este análisis.'
    )

    # ============================================
    # VENTANA DE ANÁLISIS
    # ============================================
    periodo_desde = models.DateField(
        help_text='Inicio de la ventana de ventas analizada.'
    )
    periodo_hasta = models.DateField(
        help_text='Fin de la ventana de ventas analizada.'
    )
    dias_analizados = models.PositiveIntegerField(
        help_text='Cantidad de días usados para el promedio.'
    )

    # ============================================
    # RESULTADOS DEL CÁLCULO
    # ============================================
    promedio_venta_diario = models.DecimalField(
        max_digits=10, decimal_places=3,
        help_text='Demanda diaria promedio (DDP).'
    )
    stock_seguridad = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text='Colchón ante variabilidad: DDP × días de seguridad.'
    )
    reorder_point = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text='ROP: DDP × lead time + stock de seguridad.'
    )
    stock_maximo = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text='Objetivo tras reponer: ROP + DDP × ciclo de reposición.'
    )

    # ============================================
    # PARÁMETROS USADOS (auditoría del cálculo)
    # ============================================
    leadtime = models.PositiveIntegerField(
        help_text='Lead time (en días) usado en este cálculo.'
    )
    dias_seguridad_usados = models.PositiveIntegerField(
        help_text='Días de stock de seguridad usados en este cálculo.'
    )
    ciclo_usado = models.PositiveIntegerField(
        help_text='Días de ciclo de reposición usados en este cálculo.'
    )

    # ============================================
    # METADATA
    # ============================================
    class Meta:
        db_table = 'analisis_reposicion'
        verbose_name = 'Análisis de reposición'
        verbose_name_plural = 'Análisis de reposición'

    def __str__(self):
        return f"{self.inventario.producto.sku} @ {self.inventario.tienda} — ROP {self.reorder_point}"

    # ============================================
    # PROPIEDADES DERIVADAS (no persistidas)
    # ============================================
    @property
    def necesita_reposicion(self):
        """¿El stock actual está por debajo del ROP?"""
        return float(self.inventario.stock_actual) <= float(self.reorder_point)

    @property
    def es_critico(self):
        """¿El stock actual está por debajo del stock de seguridad?"""
        return float(self.inventario.stock_actual) <= float(self.stock_seguridad)

    @property
    def cantidad_sugerida(self):
        """Cuánto pedir para llegar al stock máximo."""
        if not self.necesita_reposicion:
            return 0
        faltante = float(self.stock_maximo) - float(self.inventario.stock_actual)
        return max(int(round(faltante)), 0)
