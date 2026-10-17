"""Funciones auxiliares para crear datos de prueba."""
from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import User

from nucleo.models import (
    AnalisisReposicion, InventarioProducto, Producto, Tienda, Usuario, Ventas,
)

_contador = {'n': 0}


def _siguiente():
    _contador['n'] += 1
    return _contador['n']


def crear_tienda(nombre='Tienda Centro', codigo=None):
    n = _siguiente()
    return Tienda.objects.create(nombre=nombre, codigo_sucursal=codigo or f'SUC{n:03d}')


def crear_producto(sku=None, cuadrante='A1', lead_time=1, seguridad=1, ciclo=3, historial=30):
    n = _siguiente()
    return Producto.objects.create(
        sku=sku or str(1000 + n),
        nombre=f'Producto {n}',
        cuadrante=cuadrante,
        barra=f'75900000{n:05d}',
        lead_time_dias=lead_time,
        dias_stock_seguridad=seguridad,
        ciclo_reposicion_dias=ciclo,
        dias_historial_ventas=historial,
    )


def crear_usuario(tienda, rol=Usuario.Rol.SUPERVISOR, username=None, password='Clave-Segura-2026'):
    n = _siguiente()
    user = User.objects.create_user(username=username or f'usuario{n}', password=password)
    Usuario.objects.create(usuario=user, tienda=tienda, rol=rol)
    return user


def crear_inventario(tienda, producto, stock=0):
    return InventarioProducto.todos.create(tienda=tienda, producto=producto, stock_actual=stock)


def registrar_ventas(tienda, producto, unidades_por_dia, dias, hasta=None, precio='1.50'):
    """Registra `dias` ventas consecutivas de `unidades_por_dia` que terminan en `hasta`."""
    hasta = hasta or date.today()
    for i in range(dias):
        Ventas.todos.create(
            numero_factura=f'F-{tienda.pk}-{producto.pk}-{i}',
            fecha=hasta - timedelta(days=i),
            hora=time(10, 0),
            codigo_producto=producto,
            cantidad_vendida=unidades_por_dia,
            precio_usd=Decimal(precio),
            tienda=tienda,
        )


def crear_analisis(inventario, ddp, ss, rop, maximo):
    hoy = date.today()
    return AnalisisReposicion.objects.create(
        inventario=inventario,
        periodo_desde=hoy - timedelta(days=29),
        periodo_hasta=hoy,
        dias_analizados=30,
        promedio_venta_diario=Decimal(str(ddp)),
        stock_seguridad=Decimal(str(ss)),
        reorder_point=Decimal(str(rop)),
        stock_maximo=Decimal(str(maximo)),
        leadtime=1,
        dias_seguridad_usados=1,
        ciclo_usado=3,
    )
