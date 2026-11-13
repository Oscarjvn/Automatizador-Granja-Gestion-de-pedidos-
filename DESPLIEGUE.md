# Despliegue del sistema en Render

## 1. Crear el servicio (una sola vez)

1. Sube los cambios a GitHub (`git push`).
2. Entra a https://render.com con tu cuenta de GitHub.
3. **New → Blueprint** y elige este repositorio. Render lee `render.yaml` y crea la base de datos
   PostgreSQL y la aplicación web. La construcción (`build.sh`) instala dependencias, reúne los
   archivos estáticos y ejecuta las migraciones.
4. Al terminar, la aplicación queda en una dirección del tipo `https://granja-pedidos.onrender.com`.

## 2. Pasar los datos de tu PC a Render

En tu PC, desde la carpeta del proyecto (PowerShell):

```powershell
# 1. Exportar los datos de tu base local (con --all, para incluir los datos de todas las tiendas)
python manage.py dumpdata --all --natural-foreign --natural-primary -e contenttypes -e auth.permission -e admin.logentry -e sessions --indent 1 -o datos_granja.json

# 2. Apuntar temporalmente a la base de Render
#    (Render → granja-db → Connections → "External Database URL")
$env:DATABASE_URL = "postgresql://...pega-aquí-la-URL-externa..."

# 3. Importar
python manage.py loaddata datos_granja.json

# 4. Volver a tu base local
Remove-Item Env:DATABASE_URL
```

Los usuarios y contraseñas son los mismos que en tu PC.

## 3. Para la entrega

- Crea `URL_del_sistema.txt` con la dirección y un usuario de prueba.
- En el plan gratuito, la aplicación se suspende tras 15 minutos sin uso y tarda cerca de un minuto
  en despertar. La base de datos gratuita tiene vigencia limitada: revisa las condiciones de Render.
- **Plan B:** `Iniciar_sistema.bat` levanta el sistema en tu PC y abre el navegador.
