from django.db import transaction
from django.utils import timezone

from nucleo.models import DetallePedido, InventarioProducto, Pedido


class EstadoInvalido(Exception):
    """Transición no permitida entre estados del pedido."""
    pass


@transaction.atomic
def generar_pedido_sugerido(tienda, usuario, items):
    """Crea un Pedido en estado PENDIENTE con sus DetallePedido."""
    if not items:
        return None

    pedido = Pedido.objects.create(
        tienda=tienda,
        usuario=usuario,
        estatus=Pedido.Estado.PENDIENTE,
    )

    detalles = [
        DetallePedido(
            pedido=pedido,
            producto=item['producto'],
            cant_sugerida=item['cant_sugerida'],
            cant_ajustada=item['cant_ajustada'],
        )
        for item in items
    ]
    DetallePedido.objects.bulk_create(detalles)

    return pedido


@transaction.atomic
def aprobar_pedido(pedido):
    """PENDIENTE → APROBADO."""
    if pedido.estatus != Pedido.Estado.PENDIENTE:
        raise EstadoInvalido(
            f"No se puede aprobar un pedido en estado {pedido.get_estatus_display()}."
        )
    pedido.estatus = Pedido.Estado.APROBADO
    pedido.fecha_aprobacion = timezone.now()
    pedido.save(update_fields=['estatus', 'fecha_aprobacion'])
    return pedido


@transaction.atomic
def cancelar_pedido(pedido):
    """Cualquier estado salvo RECIBIDO → CANCELADO."""
    if pedido.estatus == Pedido.Estado.RECIBIDO:
        raise EstadoInvalido("No se puede cancelar un pedido ya recibido.")
    if pedido.estatus == Pedido.Estado.CANCELADO:
        raise EstadoInvalido("El pedido ya está cancelado.")

    pedido.estatus = Pedido.Estado.CANCELADO
    pedido.save(update_fields=['estatus'])
    return pedido


@transaction.atomic
def recibir_pedido(pedido, cantidades_recibidas):
    """
    APROBADO → RECIBIDO. Actualiza stock de inventario.

    cantidades_recibidas: {detalle_pk: cantidad, ...}
    """
    if pedido.estatus != Pedido.Estado.APROBADO:
        raise EstadoInvalido(
            f"Solo se pueden recibir pedidos APROBADOS. "
            f"Estado actual: {pedido.get_estatus_display()}."
        )

    for detalle in pedido.detalles.select_related('producto'):
        cantidad = cantidades_recibidas.get(
            detalle.pk,
            detalle.cant_ajustada or detalle.cant_sugerida,
        )
        if cantidad < 0:
            cantidad = 0

        detalle.cant_recibida = cantidad
        detalle.save(update_fields=['cant_recibida'])

        if cantidad > 0:
            inv, _ = InventarioProducto.todos.get_or_create(
                tienda=pedido.tienda,
                producto=detalle.producto,
                defaults={'stock_actual': 0},
            )
            inv.stock_actual += cantidad
            inv.save(update_fields=['stock_actual'])

    pedido.estatus = Pedido.Estado.RECIBIDO
    pedido.fecha_recepcion = timezone.now()
    pedido.save(update_fields=['estatus', 'fecha_recepcion'])
    return pedido