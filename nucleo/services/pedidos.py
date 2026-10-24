from django.db import transaction
from django.utils import timezone

from nucleo.models import DetallePedido, Lote, Pedido
from nucleo.services.ventas.carga import normalizar_sku


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
def _bloquear(pedido):
    """
    Relee el pedido bloqueando su fila hasta que termine la transacción.
    Si dos personas actúan sobre el mismo pedido a la vez, la segunda espera
    y luego ve el estado ya actualizado, en lugar de repetir la operación.
    """
    # Bloquea la fila y actualiza el mismo objeto que recibió la función
    Pedido.todos.select_for_update().filter(pk=pedido.pk).first()
    pedido.refresh_from_db()
    return pedido


class DespachoInvalido(EstadoInvalido):
    """Las cantidades o motivos del despacho del CEDI no son válidos."""


class RecepcionInvalida(EstadoInvalido):
    """Los datos de recepción no son coherentes (ej. lotes que no cuadran)."""


@transaction.atomic
def aprobar_pedido(pedido):
    pedido = _bloquear(pedido)
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
    pedido = _bloquear(pedido)
    if pedido.estatus == Pedido.Estado.CANCELADO:
        raise EstadoInvalido("El pedido ya está cancelado.")
    if pedido.estatus not in (Pedido.Estado.PENDIENTE, Pedido.Estado.APROBADO):
        raise EstadoInvalido(
            f"No se puede cancelar un pedido {pedido.get_estatus_display().lower()}: "
            f"el CEDI ya lo procesó."
        )

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
    pedido = _bloquear(pedido)
    if pedido.estatus != Pedido.Estado.DESPACHADO:
        raise EstadoInvalido(
            f"Solo se pueden recibir pedidos que el CEDI ya despachó. "
            f"Estado actual: {pedido.get_estatus_display()}."
        )

    lotes_creados = 0

    for detalle in pedido.detalles.select_related('producto'):
        propuesta = detalle.cant_despachada if detalle.cant_despachada is not None else detalle.cant_pedida
        cantidad = cantidades_recibidas.get(detalle.pk, propuesta)
        if cantidad < 0:
            cantidad = 0

        lotes_validos = [
            l for l in lotes_por_detalle.get(detalle.pk, [])
            if l.get('fecha_vencimiento') and l.get('cantidad', 0) > 0
        ]
        suma_lotes = sum(l['cantidad'] for l in lotes_validos)
        if lotes_validos and suma_lotes != cantidad:
            # La transacción se revierte: no queda nada a medio guardar
            raise RecepcionInvalida(
                f"{detalle.producto.nombre}: los lotes suman {suma_lotes} "
                f"unidades, pero la cantidad recibida es {cantidad}. "
                f"Corrija las cantidades y vuelva a intentarlo."
            )

        detalle.cant_recibida = cantidad
        detalle.save(update_fields=['cant_recibida'])

        for idx, lote_data in enumerate(lotes_validos, start=1):
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


@transaction.atomic
def despachar_pedido(pedido, usuario, cantidades, motivos, stock_cedi=None):
    """
    El CEDI confirma un pedido aprobado y registra lo que despacha.

    cantidades: {detalle_pk: unidades despachadas}. Si falta una línea, se
                despacha completa (lo que pidió la tienda).
    motivos:    {detalle_pk: código de MotivoAjuste}. Obligatorio en cada línea
                que se despacha incompleta o en cero.

    stock_cedi: {sku: unidades disponibles} según la API del CEDI, o None si no
                se pudo verificar. Con stock, no se despacha más de lo que hay
                y el motivo se deduce de los datos cuando es posible:
                0 disponibles → Sin stock; se envía todo lo que había → Stock parcial.
                El operador solo indica el motivo si envía menos de lo que podría.
                Un SKU que la API no devuelve se toma como 0 disponibles.

    Si no se despacha ninguna unidad, el pedido queda RECHAZADO por el CEDI.
    """
    pedido = _bloquear(pedido)
    if pedido.estatus != Pedido.Estado.APROBADO:
        raise EstadoInvalido(
            f"Solo se despachan pedidos aprobados por el gerente. "
            f"Estado actual: {pedido.get_estatus_display()}."
        )

    motivos_validos = set(DetallePedido.MotivoAjuste.values)
    total = 0
    for detalle in pedido.detalles.select_related('producto'):
        pedida = detalle.cant_pedida
        disponible = None
        if stock_cedi is not None:
            disponible = stock_cedi.get(normalizar_sku(detalle.producto.sku), 0)
        maximo = pedida if disponible is None else min(pedida, disponible)

        cantidad = cantidades.get(detalle.pk, maximo)
        if cantidad < 0 or cantidad > pedida:
            raise DespachoInvalido(
                f"{detalle.producto.nombre}: la cantidad despachada debe estar entre 0 y {pedida}."
            )
        if disponible is not None and cantidad > disponible:
            raise DespachoInvalido(
                f"{detalle.producto.nombre}: el CEDI solo tiene {disponible} unidades disponibles."
            )

        motivo = ''
        if cantidad < pedida:
            motivo = motivos.get(detalle.pk, '')
            if motivo not in motivos_validos:
                if disponible is not None and cantidad == disponible:
                    # El inventario explica la diferencia: el motivo no depende de la persona
                    motivo = (DetallePedido.MotivoAjuste.SIN_STOCK if disponible == 0
                              else DetallePedido.MotivoAjuste.STOCK_PARCIAL)
                else:
                    raise DespachoInvalido(
                        f"{detalle.producto.nombre}: indique el motivo por el que se despachan "
                        f"{cantidad} de {pedida} unidades."
                    )
        detalle.cant_despachada = cantidad
        detalle.motivo_ajuste = motivo
        detalle.stock_cedi_al_despachar = disponible
        detalle.save(update_fields=['cant_despachada', 'motivo_ajuste', 'stock_cedi_al_despachar'])
        total += cantidad

    pedido.estatus = Pedido.Estado.DESPACHADO if total > 0 else Pedido.Estado.RECHAZADO
    pedido.fecha_despacho = timezone.now()
    pedido.despachado_por = usuario
    pedido.save(update_fields=['estatus', 'fecha_despacho', 'despachado_por'])
    return pedido
