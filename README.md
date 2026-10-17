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

```bash
python manage.py sincronizar_ventas        # descarga y carga las ventas de ayer
python manage.py recalcular_reposicion     # recalcula DDP, ROP y stock máximo
python manage.py productos_a_reponer       # alerta de productos bajo el ROP
python manage.py productos_sobrestock      # alerta de productos sobre el stock máximo
python manage.py lotes_por_vencer          # alerta de lotes por vencer
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

El rol se asigna en el panel de administración, en el perfil de tienda del usuario.

## Pruebas

```bash
python manage.py test --settings=configuraciones.settings_test
```

Usan SQLite en memoria, así que no necesitan `.env` ni PostgreSQL.
