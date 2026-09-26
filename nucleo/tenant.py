from contextvars import ContextVar

_tienda_actual = ContextVar('tienda_actual', default=None)


def set_tienda_actual(tienda):
    _tienda_actual.set(tienda)


def get_tienda_actual():
    return _tienda_actual.get()


def limpiar_tienda_actual():
    _tienda_actual.set(None)