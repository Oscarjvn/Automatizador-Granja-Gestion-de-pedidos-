from django.db import transaction
from django.utils import timezone

from nucleo.models import DetallePedido, Lote, Pedido


class EstadoInvalido(Exception):
    """Transición no permitida entre estados del pedido."""
    pass


@transaction.atomic
def generar_pedido_sugerido(tienda, usuario, items):
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
    if pedido.estatus == Pedido.Estado.RECIBIDO:
        raise EstadoInvalido("No se puede cancelar un pedido ya recibido.")
    if pedido.estatus == Pedido.Estado.CANCELADO:
        raise EstadoInvalido("El pedido ya está cancelado.")

    pedido.estatus = Pedido.Estado.CANCELADO
    pedido.save(update_fields=['estatus'])
    return pedido


@transaction.atomic
def recibir_pedido(pedido, cantidades_recibidas, lotes_por_detalle):
    """
    Marca el pedido como RECIBIDO y crea los lotes con sus vencimientos.

    IMPORTANTE: NO modifica InventarioProducto.stock_actual.
    El stock se sincroniza por separado desde el POS.

    cantidades_recibidas: {detalle_pk: cantidad_total}
    lotes_por_detalle: {
        detalle_pk: [
            {'cantidad': int, 'fecha_vencimiento': date},
            ...
        ]
    }
    """
    if pedido.estatus != Pedido.Estado.APROBADO:
        raise EstadoInvalido(
            f"Solo se pueden recibir pedidos APROBADOS. "
            f"Estado actual: {pedido.get_estatus_display()}."
        )

    lotes_creados = 0

    for detalle in pedido.detalles.select_related('producto'):
        cantidad = cantidades_recibidas.get(
            detalle.pk,
            detalle.cant_ajustada or detalle.cant_sugerida,
        )
        if cantidad < 0:
            cantidad = 0

        detalle.cant_recibida = cantidad
        detalle.save(update_fields=['cant_recibida'])

        for idx, lote_data in enumerate(lotes_por_detalle.get(detalle.pk, []), start=1):
            cant_lote = lote_data.get('cantidad', 0)
            fecha_venc = lote_data.get('fecha_vencimiento')

            if not fecha_venc or cant_lote <= 0:
                continue

            Lote.todos.create(
                tienda=pedido.tienda,
                producto=detalle.producto,
                codigo_lote=f'PED-{pedido.pk}-{detalle.pk}-{idx}',
                fecha_vencimiento=fecha_venc,
                cantidad=cant_lote,
                pedido_origen=pedido,
                detalle_origen=detalle,
            )
            lotes_creados += 1

    pedido.estatus = Pedido.Estado.RECIBIDO
    pedido.fecha_recepcion = timezone.now()
    pedido.save(update_fields=['estatus', 'fecha_recepcion'])

    return pedido, lotes_creados