"""
Candado de archivo multiplataforma.

Evita que dos procesos ejecuten la misma tarea a la vez (por ejemplo, si la
tarea de anoche se quedó colgada cuando arranca la de hoy). Cada sistema
operativo ofrece su propio mecanismo:

    Linux / macOS  →  fcntl.flock
    Windows        →  msvcrt.locking

El resto del código solo usa `Candado` y no necesita saber en qué sistema corre.
"""
import os


class CandadoOcupado(Exception):
    """Otro proceso ya tiene el candado."""


if os.name == 'nt':
    import msvcrt

    def _tomar(archivo):
        archivo.seek(0)
        try:
            msvcrt.locking(archivo.fileno(), msvcrt.LK_NBLCK, 1)   # bloquea 1 byte, sin esperar
        except OSError:
            raise CandadoOcupado()

    def _soltar(archivo):
        archivo.seek(0)
        msvcrt.locking(archivo.fileno(), msvcrt.LK_UNLCK, 1)
else:
    import fcntl

    def _tomar(archivo):
        try:
            fcntl.flock(archivo, fcntl.LOCK_EX | fcntl.LOCK_NB)      # exclusivo, sin esperar
        except BlockingIOError:
            raise CandadoOcupado()

    def _soltar(archivo):
        fcntl.flock(archivo, fcntl.LOCK_UN)


class Candado:
    """
    Uso:
        with Candado(ruta):
            ...trabajo que no debe correr dos veces a la vez...

    Si otro proceso ya lo tiene, lanza CandadoOcupado de inmediato.
    """

    def __init__(self, ruta):
        self.ruta = ruta
        self.archivo = None

    def __enter__(self):
        self.archivo = open(self.ruta, 'a+')
        try:
            _tomar(self.archivo)
        except CandadoOcupado:
            self.archivo.close()
            raise
        return self

    def __exit__(self, *exc):
        try:
            _soltar(self.archivo)
        finally:
            self.archivo.close()
        return False
