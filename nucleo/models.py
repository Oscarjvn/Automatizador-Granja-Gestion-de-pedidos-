from django.db import models
from django.contrib.auth.models import User

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
 

    class Meta:
        managed = True
        db_table = 'inventario_producto'
        unique_together = (('tienda', 'producto'),)

class Lote(models.Model):
    id_lote = models.AutoField(primary_key=True)
    tienda = models.ForeignKey(Tienda, models.CASCADE, db_column='id_tienda')
    producto = models.ForeignKey(Producto, models.CASCADE, db_column='id_producto')
    codigo_lote = models.CharField(max_length=50, blank=True, null=True)
    fecha_vencimiento = models.DateField()
    cantidad = models.IntegerField(default=0)

    class Meta:
        managed = True
        db_table = 'lote'

class Pedido(models.Model):
    id_pedido = models.AutoField(primary_key=True)
    tienda = models.ForeignKey(Tienda, models.PROTECT, db_column='id_tienda')
    # Nota: Aquí más adelante usaremos el modelo de usuario de Django
    fecha_creacion = models.DateTimeField(auto_now_add=True) 
    estatus = models.CharField(max_length=20, default='PENDIENTE')

    class Meta:
        managed = True
        db_table = 'pedido'

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