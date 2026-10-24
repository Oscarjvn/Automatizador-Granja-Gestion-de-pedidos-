# Automatizador Granja Mercados – Gestión de pedidos

Aplicación web en Django 6 + PostgreSQL que automatiza los pedidos de reposición
de las tiendas de Granja Mercados a partir de las ventas del POS.

## Instalación

```bash
pip install -r requirements.txt
cp env.example .env        # completar con los datos reales
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## Tareas programadas

En producción basta con programar **un solo comando** una vez al día (por ejemplo a las 2:00 a. m.).
Ejecuta en orden la sincronización, el recálculo y las alertas, y evita que dos ejecuciones se pisen:

```bash
python manage.py tareas_diarias
python manage.py tareas_diarias --sin-sincronizar   # si el POS no está disponible
```

Los comandos individuales siguen disponibles:

```bash
python manage.py sincronizar_ventas        # descarga y carga las ventas de ayer
python manage.py recalcular_reposicion     # recalcula DDP, ROP y stock máximo
python manage.py productos_a_reponer       # alerta de productos bajo el ROP
python manage.py productos_sobrestock      # alerta de productos sobre el stock máximo
python manage.py lotes_por_vencer          # alerta de lotes por vencer
python manage.py predecir_top_productos    # pronóstico del top 20 de productos por tienda
```

## Roles

| Acción | Gerente | Subgerente | Supervisor |
| --- | --- | --- | --- |
| Consultar dashboard, inventario y alertas | sí | sí | sí |
| Generar pedido sugerido | sí | sí | sí |
| Recibir pedido y registrar lotes | sí | sí | sí |
| Reportes y predicción | sí | sí | no |
| Exportar a Excel | sí | sí | no |
| Aprobar o cancelar pedido | sí | no | no |

El rol **Operador de CEDI** no pertenece a ninguna tienda: ve los pedidos aprobados de todas
en `/cedi/`, ajusta cantidades o marca productos sin stock y confirma el despacho.

Al preparar un despacho, el sistema consulta las existencias en la **API de inventario del CEDI**
(variables `CEDI_INVENTARIO_*` en `.env`), propone las cantidades, impide despachar más de lo que hay
y guarda en cada línea el stock informado al despachar. El inventario del CEDI no se copia en esta
aplicación: su API es la única fuente de verdad. Para desarrollo sin API: `CEDI_INVENTARIO_SIMULADO=True`.

Flujo del pedido: **Pendiente → Aprobado (gerente) → Despachado (CEDI) → Recibido (tienda)**.
Si el CEDI no despacha ninguna unidad, el pedido queda **Rechazado por CEDI**.

El rol se asigna en el panel de administración, en el perfil de tienda del usuario.
No hay registro público: las cuentas solo se crean desde el panel de administración.

## Pruebas

```bash
python manage.py test --settings=configuraciones.settings_test
```

Usan SQLite en memoria, así que no necesitan `.env` ni PostgreSQL.
