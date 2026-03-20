# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models


class Cedis(models.Model):
    id_cedis_inv = models.AutoField(primary_key=True)
    id_producto = models.OneToOneField('Producto', models.DO_NOTHING, db_column='id_producto', blank=True, null=True)
    stock_disponible = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'cedis'


class DetallePedido(models.Model):
    id_detalle = models.AutoField(primary_key=True)
    id_pedido = models.ForeignKey('Pedido', models.DO_NOTHING, db_column='id_pedido', blank=True, null=True)
    id_producto = models.ForeignKey('Producto', models.DO_NOTHING, db_column='id_producto', blank=True, null=True)
    cant_sugerida = models.IntegerField()
    cant_ajustada = models.IntegerField(blank=True, null=True)
    cant_recibida = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'detalle_pedido'


class InventarioProducto(models.Model):
    id_inv_prod = models.AutoField(primary_key=True)
    id_tienda = models.ForeignKey('Tienda', models.DO_NOTHING, db_column='id_tienda', blank=True, null=True)
    id_producto = models.ForeignKey('Producto', models.DO_NOTHING, db_column='id_producto', blank=True, null=True)
    stock_actual = models.IntegerField(blank=True, null=True)
    stock_min = models.IntegerField()
    stock_max = models.IntegerField()
    ventas_prom_dia = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'inventario_producto'
        unique_together = (('id_tienda', 'id_producto'),)


class Lote(models.Model):
    id_lote = models.AutoField(primary_key=True)
    id_tienda = models.ForeignKey('Tienda', models.DO_NOTHING, db_column='id_tienda', blank=True, null=True)
    id_producto = models.ForeignKey('Producto', models.DO_NOTHING, db_column='id_producto', blank=True, null=True)
    codigo_lote = models.CharField(max_length=50, blank=True, null=True)
    fecha_vencimiento = models.DateField()
    cantidad = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'lote'


class Pedido(models.Model):
    id_pedido = models.AutoField(primary_key=True)
    id_tienda = models.ForeignKey('Tienda', models.DO_NOTHING, db_column='id_tienda', blank=True, null=True)
    id_usuario = models.ForeignKey('Usuario', models.DO_NOTHING, db_column='id_usuario', blank=True, null=True)
    fecha_creacion = models.DateTimeField(blank=True, null=True)
    estatus = models.CharField(max_length=20, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'pedido'


class Producto(models.Model):
    id_producto = models.AutoField(primary_key=True)
    sku = models.CharField(unique=True, max_length=20)
    nombre = models.CharField(max_length=150)
    categoria = models.CharField(max_length=50, blank=True, null=True)
    unidad_empaque = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'producto'


class Tienda(models.Model):
    id_tienda = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100)
    codigo_sucursal = models.CharField(unique=True, max_length=10)
    direccion = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'tienda'


class Usuario(models.Model):
    id_usuario = models.AutoField(primary_key=True)
    id_tienda = models.ForeignKey(Tienda, models.DO_NOTHING, db_column='id_tienda', blank=True, null=True)
    username = models.CharField(unique=True, max_length=50)
    password_hash = models.CharField(max_length=255)
    rol = models.CharField(max_length=20, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'usuario'
