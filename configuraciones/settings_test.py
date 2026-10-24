"""
Configuración para ejecutar las pruebas automatizadas.

Uso:
    python manage.py test --settings=configuraciones.settings_test

No requiere archivo .env ni servidor PostgreSQL: usa SQLite en memoria,
un backend de correo local y contraseñas con hash rápido.
"""
import os

# Valores mínimos para que settings.py cargue sin .env
os.environ.setdefault('SECRET_KEY', 'clave-solo-para-pruebas')
os.environ.setdefault('DEBUG', 'False')
os.environ.setdefault('DB_NAME', 'pruebas')
os.environ.setdefault('DB_USER', 'pruebas')
os.environ.setdefault('DB_PASSWORD', 'pruebas')
os.environ.setdefault('SENDGRID_API_KEY', 'sin-clave')
os.environ.setdefault('DEFAULT_FROM_EMAIL', 'pruebas@example.com')

from .settings import *  # noqa: E402,F401,F403

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# La barra de depuración no debe intervenir en las pruebas
INSTALLED_APPS = [app for app in INSTALLED_APPS if app != 'debug_toolbar']
MIDDLEWARE = [m for m in MIDDLEWARE if 'debug_toolbar' not in m]
# Las pruebas de vistas existentes despachan sin API; las del inventario del CEDI
# activan el bloqueo explícitamente con override_settings.
CEDI_INVENTARIO_URL = ''
CEDI_INVENTARIO_SIMULADO = False
CEDI_PERMITIR_DESPACHO_SIN_INVENTARIO = True
CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}

EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'
