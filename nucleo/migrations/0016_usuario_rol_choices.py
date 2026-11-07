# Roles fijos para los usuarios de tienda (seguridad por roles).

from django.db import migrations, models


def normalizar_roles(apps, schema_editor):
    """
    Convierte los roles escritos a mano antes de esta migración
    (ej. 'gerente', 'Supervisor') a los códigos fijos del sistema.
    Lo que no se reconoce queda como OPERADOR, el rol con menos permisos.
    """
    Usuario = apps.get_model('nucleo', 'Usuario')
    equivalencias = {
        'GERENTE': 'GERENTE',
        'GERENTE DE TIENDA': 'GERENTE',
        'SUBGERENTE': 'SUBGERENTE',
        'SUB GERENTE': 'SUBGERENTE',
        'SUPERVISOR': 'SUPERVISOR',
        'OPERADOR': 'OPERADOR',
        'OPERADOR INTEGRAL': 'OPERADOR',
    }
    for perfil in Usuario.objects.all():
        valor = (perfil.rol or '').strip().upper()
        perfil.rol = equivalencias.get(valor, 'OPERADOR')
        perfil.save(update_fields=['rol'])


class Migration(migrations.Migration):

    dependencies = [
        ('nucleo', '0015_alter_lote_options_lote_cantidad_lote_detalle_origen_and_more'),
    ]

    operations = [
        migrations.RunPython(normalizar_roles, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='usuario',
            name='rol',
            field=models.CharField(
                choices=[
                    ('GERENTE', 'Gerente de tienda'),
                    ('SUBGERENTE', 'Subgerente'),
                    ('SUPERVISOR', 'Supervisor'),
                    ('OPERADOR', 'Operador integral'),
                ],
                default='OPERADOR',
                max_length=20,
            ),
        ),
    ]
