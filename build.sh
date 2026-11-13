#!/usr/bin/env bash
# Construcción en Render: dependencias, archivos estáticos y migraciones
set -o errexit
pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate
