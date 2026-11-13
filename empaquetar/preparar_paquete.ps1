<#
  Construye el paquete portátil del sistema para entregarlo en el pendrive.

  El paquete funciona en cualquier Windows de 64 bits sin instalar nada:
  trae su propio Python, todas las librerías y una copia de los datos en SQLite.

  Uso (desde la carpeta del proyecto, en PowerShell, con internet):
      powershell -ExecutionPolicy Bypass -File empaquetar\preparar_paquete.ps1

  Opcional: -Destino "D:\Sistema_Granja" para crearlo directamente en otra carpeta.
#>
param(
    [string]$Destino = "$env:USERPROFILE\Desktop\Sistema_Granja",
    [string]$VersionPython = "3.12.8"
)
$ErrorActionPreference = "Stop"
$proyecto = Split-Path -Parent $PSScriptRoot
$py = "$Destino\python\python.exe"

Write-Host "1/6 Preparando la carpeta $Destino"
if (Test-Path $Destino) { Remove-Item $Destino -Recurse -Force }
New-Item -ItemType Directory -Force -Path "$Destino\python", "$Destino\datos" | Out-Null

Write-Host "2/6 Descargando Python $VersionPython portátil"
$zip = "$env:TEMP\python-embed.zip"
Invoke-WebRequest "https://www.python.org/ftp/python/$VersionPython/python-$VersionPython-embed-amd64.zip" -OutFile $zip
Expand-Archive $zip -DestinationPath "$Destino\python" -Force
# El Python portátil viene sin site-packages: se habilita para poder instalar librerías
$pth = Get-ChildItem "$Destino\python\python*._pth" | Select-Object -First 1
(Get-Content $pth) -replace '^#\s*import site', 'import site' | Set-Content $pth
Add-Content $pth "..\app"

Write-Host "3/6 Copiando el código del sistema"
robocopy $proyecto "$Destino\app" /E /NFL /NDL /NJH /NJS /XD .git venv .venv env __pycache__ staticfiles datos node_modules empaquetar /XF *.patch .env db.sqlite3 *.pyc | Out-Null

Write-Host "4/6 Instalando pip y las librerías (puede tardar varios minutos)"
Invoke-WebRequest "https://bootstrap.pypa.io/get-pip.py" -OutFile "$env:TEMP\get-pip.py"
& $py "$env:TEMP\get-pip.py" --no-warn-script-location
& $py -m pip install -r "$Destino\app\requirements.txt" --no-warn-script-location
if ($LASTEXITCODE -ne 0) { throw "Falló la instalación de librerías" }

Write-Host "5/6 Copiando los datos de tu base local a SQLite"
Push-Location $proyecto
python manage.py dumpdata --all --natural-foreign --natural-primary -e contenttypes -e auth.permission -e admin.logentry -e sessions --indent 1 -o "$Destino\datos\datos_granja.json"
if ($LASTEXITCODE -ne 0) { Pop-Location; throw "Falló la exportación de datos" }
Pop-Location
$env:DATABASE_URL = "sqlite:///$Destino\datos\granja.sqlite3"
$env:SECRET_KEY = "paquete-local-granja"
$env:DEBUG = "False"
Push-Location "$Destino\app"
& $py manage.py migrate --no-input
& $py manage.py loaddata "$Destino\datos\datos_granja.json"
if ($LASTEXITCODE -ne 0) { Pop-Location; throw "Falló la importación de datos" }
& $py manage.py collectstatic --no-input
Pop-Location
Remove-Item Env:DATABASE_URL, Env:SECRET_KEY, Env:DEBUG
Remove-Item "$Destino\datos\datos_granja.json"

Write-Host "6/6 Copiando el lanzador y las instrucciones"
Copy-Item "$PSScriptRoot\Iniciar_sistema.bat", "$PSScriptRoot\LEEME.txt" $Destino

Write-Host ""
Write-Host "Listo. Paquete creado en: $Destino"
Write-Host "Pruébalo con doble clic en Iniciar_sistema.bat y luego cópialo al pendrive."
