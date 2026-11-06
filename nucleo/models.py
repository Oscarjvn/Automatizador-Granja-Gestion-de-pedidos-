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
    cuadrante= models.CharField(max_length=50, blank= True, null=True)
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
        verbose_name = 'inventario de tienda'
        verbose_name_plural = 'inventario de tiendas'
        base_manager_name= 'todos'

class Lote(models.Model):
    id_lote = models.AutoField(primary_key=True)
    tienda = models.ForeignKey(Tienda, models.CASCADE, db_column='id_tienda')
    producto = models.ForeignKey(Producto, models.CASCADE, db_column='id_producto')
    codigo_lote = models.CharField(max_length=50, blank=True, null=True)
    fecha_vencimiento = models.DateField()
    cantidad = models.IntegerField(default=0, help_text='Unidades en este lote.')

    pedido_origen = models.ForeignKey(
        'Pedido',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='lotes_generados',
        db_column='id_pedido_origen',
    )
    detalle_origen = models.ForeignKey(
        'DetallePedido',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='lotes_generados',
        db_column='id_detalle_origen',
    )

    objects= TenantManager()
    todos= models.Manager()

    class Meta:
        managed = True
        db_table = 'lote'
        base_manager_name= 'todos'
        ordering = ['fecha_vencimiento']
    
    def __str__(self):
        return f"{self.producto.sku} — vence {self.fecha_vencimiento}"

    @property
    def dias_restantes(self):
        from datetime import date
        return (self.fecha_vencimiento - date.today()).days

    @property
    def esta_vencido(self):
        return self.dias_restantes < 0

class Pedido(models.Model):
    class  Estado(models.TextChoices):
        PENDIENTE= 'PE', 'Pendiente'
        CANCELADO= 'CA', 'Cancelado'
        APROBADO= 'AP', 'Aprobado'
        DESPACHADO = 'DE', 'Despachado'
        RECHAZADO = 'RC', 'Rechazado por CEDI'
        RECIBIDO= 'RE',  'Recibido'

    
    id_pedido = models.AutoField(primary_key=True)
    tienda = models.ForeignKey(Tienda, models.PROTECT, db_column='id_tienda')
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.PROTECT, 
        related_name='pedidos',
        verbose_name='creado por',
    )
    fecha_creacion = models.DateTimeField('fecha de creación', auto_now_add=True)
    estatus = models.CharField(
        'estado',
        max_length=20,
        choices= Estado.choices,
        default= Estado.PENDIENTE

    )
    fecha_aprobacion = models.DateTimeField('fecha de aprobación', null=True, blank=True)
    fecha_despacho = models.DateTimeField('fecha de despacho', null=True, blank=True)
    despachado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pedidos_despachados',
        verbose_name='despachado por',
    )
    fecha_recepcion = models.DateTimeField('fecha de recepción', null=True, blank=True)

    objects= TenantManager()
    todos= models.Manager()
    class Meta:
        managed = True
        db_table = 'pedido'
        base_manager_name= 'todos'
        verbose_name = 'pedido'
        verbose_name_plural = 'pedidos'

    def __str__(self):
        return f'Pedido #{self.pk} · {self.tienda}'

class DetallePedido(models.Model):
    id_detalle = models.AutoField(primary_key=True)
    pedido = models.ForeignKey(Pedido, models.CASCADE, db_column='id_pedido', related_name='detalles')
    producto = models.ForeignKey(Producto, models.PROTECT, db_column='id_producto')
    cant_sugerida = models.IntegerField('sugerida')
    cant_ajustada = models.IntegerField('ajustada', blank=True, null=True)
    cant_despachada = models.IntegerField('despachada', blank=True, null=True)
    # Existencia que informó la API del CEDI al despachar (None = no se pudo verificar)
    stock_cedi_al_despachar = models.IntegerField('stock del CEDI al despachar', blank=True, null=True)
    cant_recibida = models.IntegerField('recibida', blank=True, null=True)

    class MotivoAjuste(models.TextChoices):
        SIN_STOCK = 'SIN_STOCK', 'Sin stock en el CEDI'
        STOCK_PARCIAL = 'STOCK_PARCIAL', 'Stock parcial'
        DESCONTINUADO = 'DESCONTINUADO', 'Producto descontinuado'
        OTRO = 'OTRO', 'Otro motivo'

    motivo_ajuste = models.CharField('motivo del ajuste', max_length=20, choices=MotivoAjuste.choices, blank=True, default='')

    class Meta:
        managed = True
        db_table = 'detalle_pedido'
        verbose_name = 'línea de pedido'
        verbose_name_plural = 'líneas de pedido'

    def __str__(self):
        return f'{self.producto} · pedido #{self.pedido_id}'

    @property
    def cant_pedida(self):
        """Lo que la tienda pidió finalmente: la cantidad ajustada o, si no hay, la sugerida."""
        return self.cant_ajustada if self.cant_ajustada is not None else self.cant_sugerida

    @property
    def diferencia_despacho(self):
        """Unidades que el CEDI dejó de enviar respecto a lo pedido."""
        if self.cant_despachada is None:
            return None
        return self.cant_pedida - self.cant_despachada

    @property
    def diferencia_recepcion(self):
        """Unidades que llegaron de menos (o de más, si es negativo) respecto a lo despachado."""
        if self.cant_despachada is None or self.cant_recibida is None:
            return None
        return self.cant_despachada - self.cant_recibida

class Usuario(models.Model):
    """Perfil del usuario: tienda a la que pertenece y rol que ocupa en ella."""

    class Rol(models.TextChoices):
        GERENTE = 'GERENTE', 'Gerente de tienda'
        SUBGERENTE = 'SUBGERENTE', 'Subgerente'
        SUPERVISOR = 'SUPERVISOR', 'Supervisor'
        CEDI = 'CEDI', 'Operador de CEDI'

    usuario= models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True)
    # El operador de CEDI no pertenece a una tienda: atiende los pedidos de todas
    tienda= models.ForeignKey('Tienda', on_delete=models.CASCADE, db_column='id_tienda', null=True, blank=True)
    rol = models.CharField(max_length=20, choices=Rol.choices, default=Rol.SUPERVISOR)

    class Meta:
        db_table = 'usuario'
    
    @property
    def es_cedi(self):
        return self.rol == self.Rol.CEDI

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.es_cedi and self.tienda_id:
            raise ValidationError({'tienda': 'El operador de CEDI no se asigna a una tienda.'})
        if not self.es_cedi and not self.tienda_id:
            raise ValidationError({'tienda': 'Los usuarios de tienda deben tener una tienda asignada.'})

    def __str__(self):
        return f"{self.usuario.username} ({self.get_rol_display()})"


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
        verbose_name = 'venta'
        verbose_name_plural = 'ventas'
        base_manager_name = 'todos'
        indexes = [
            models.Index(fields=['tienda', 'codigo_producto', 'fecha']),
            models.Index(fields=['fecha']),
        ]

    def __str__(self):
        return f"Factura N° {self.numero_factura} - {self.fecha} - {self.hora} - {self.codigo_producto_id}"



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
    def tiene_sobrestock(self):
        """
        ¿El stock actual supera el stock máximo calculado?
        Solo aplica a productos con ventas (DDP > 0); los productos sin
        ventas se reportan aparte como "sin movimiento".
        """
        return (
            float(self.promedio_venta_diario) > 0
            and float(self.inventario.stock_actual) > float(self.stock_maximo)
        )

    @property
    def exceso_unidades(self):
        """Unidades por encima del stock máximo (0 si no hay sobrestock)."""
        if not self.tiene_sobrestock:
            return 0
        return int(round(float(self.inventario.stock_actual) - float(self.stock_maximo)))

    @property
    def dias_cobertura(self):
        """Días que alcanza el stock actual al ritmo de venta promedio."""
        ddp = float(self.promedio_venta_diario)
        if ddp <= 0:
            return None
        return round(float(self.inventario.stock_actual) / ddp, 1)

    @property
    def cantidad_sugerida(self):
        """Cuánto pedir para llegar al stock máximo."""
        if not self.necesita_reposicion:
            return 0
        faltante = float(self.stock_maximo) - float(self.inventario.stock_actual)
        return max(int(round(faltante)), 0)


class InventarioCedi(models.Model):
    """
    Existencias del CEDI para la fuente LOCAL de inventario (demostración y pruebas).

    En producción el inventario del CEDI vive en su propio sistema y se consulta
    por API (CEDI_INVENTARIO_FUENTE=api); esta tabla no se usa en ese modo.
    No es una tienda: no tiene ventas, reposición ni usuarios.
    """
    producto = models.OneToOneField('Producto', on_delete=models.CASCADE, related_name='inventario_cedi')
    disponible = models.PositiveIntegerField(default=0)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'inventario_cedi'
        verbose_name = 'inventario del CEDI'
        verbose_name_plural = 'inventario del CEDI'

    def __str__(self):
        return f"{self.producto.sku} · {self.disponible} u."
