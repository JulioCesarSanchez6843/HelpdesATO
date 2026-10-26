import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0006_usuario_debe_cambiar_password'),
        ('catalog', '0006_remove_sucursal_logo_blanco'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='usuario',
            name='usuario_sucursal_obligatoria',
        ),
        migrations.AlterField(
            model_name='usuario',
            name='sucursal',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='usuarios',
                to='catalog.sucursal',
            ),
        ),
        migrations.AddConstraint(
            model_name='usuario',
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ('rol', 'SUPERADMIN'),
                    ('is_superuser', True),
                    ('sucursal__isnull', False),
                    ('activo', False),
                    _connector='OR',
                ),
                name='usuario_sucursal_obligatoria',
            ),
        ),
    ]