import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0004_sucursal_color_primario_sucursal_logo_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='sucursal',
            name='color_barra',
            field=models.CharField(default='#2f2f2f', max_length=7, validators=[django.core.validators.RegexValidator('^#[0-9a-fA-F]{6}$', 'Color no válido.')]),
        ),
        migrations.AddField(
            model_name='sucursal',
            name='logo_blanco',
            field=models.BooleanField(default=True),
        ),
    ]