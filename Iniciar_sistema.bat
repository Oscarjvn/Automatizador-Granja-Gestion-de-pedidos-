@echo off
REM Plan B: inicia el sistema en este equipo y abre el navegador
cd /d "%~dp0"
start "" http://127.0.0.1:8000/login/
python manage.py runserver 127.0.0.1:8000
