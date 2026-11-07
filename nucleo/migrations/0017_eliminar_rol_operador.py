# El rol "Operador integral" se elimina: sus funciones pasan al supervisor.

from django.db import migrations, models


def operador_a_supervisor(apps, schema_editor):
    Usuario = apps.get_model('nucleo', 'Usuario')
    Usuario.objects.filter(rol='OPERADOR').update(rol='SUPERVISOR')


class Migration(migrations.Migration):

    dependencies = [
        ('nucleo', '0016_usuario_rol_choices'),
    ]

    operations = [
        migrations.RunPython(operador_a_supervisor, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='usuario',
            name='rol',
            field=models.CharField(
                choices=[
                    ('GERENTE', 'Gerente de tienda'),
                    ('SUBGERENTE', 'Subgerente'),
                    ('SUPERVISOR', 'Supervisor'),
                ],
                default='SUPERVISOR',
                max_length=20,
            ),
        ),
    ]
