@echo off
title Sistema de pedidos - Granja Mercados
REM Inicia el sistema con su Python portatil y su base de datos, sin instalar nada.
cd /d "%~dp0app"
set "DATABASE_URL=sqlite:///%~dp0datos\granja.sqlite3"
set "SECRET_KEY=paquete-local-granja"
set "DEBUG=False"
set "ALLOWED_HOSTS=127.0.0.1,localhost"
echo.
echo  Iniciando el sistema de pedidos de Granja Mercados...
echo  El navegador se abrira en unos segundos.
echo  No cierre esta ventana mientras use el sistema.
echo.
start "" cmd /c "timeout /t 5 >nul & start http://127.0.0.1:8000/login/"
"%~dp0python\python.exe" manage.py runserver 127.0.0.1:8000 --noreload --insecure
pause
