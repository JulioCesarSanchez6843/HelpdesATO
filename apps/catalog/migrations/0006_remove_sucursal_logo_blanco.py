from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0005_sucursal_color_barra_sucursal_logo_blanco'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='sucursal',
            name='logo_blanco',
        ),
    ]