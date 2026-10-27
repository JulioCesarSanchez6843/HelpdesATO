import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tickets', '0007_alter_notificacion_tipo_alter_ticket_estado_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='ticket',
            name='recordatorio_cierre_en',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name='ConfiguracionSistema',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cierre_automatico_activo', models.BooleanField(default=False)),
                ('cierre_automatico_dias', models.PositiveSmallIntegerField(default=7)),
                ('recordatorio_activo', models.BooleanField(default=True)),
                ('recordatorio_dias_antes', models.PositiveSmallIntegerField(default=2)),
                ('ultima_ejecucion', models.DateTimeField(blank=True, null=True)),
                ('ultima_ejecucion_cerrados', models.PositiveIntegerField(default=0)),
                ('ultima_ejecucion_recordatorios', models.PositiveIntegerField(default=0)),
                ('ultima_ejecucion_errores', models.PositiveIntegerField(default=0)),
                ('actualizado_en', models.DateTimeField(blank=True, null=True)),
                ('actualizado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Configuración del sistema',
                'verbose_name_plural': 'Configuración del sistema',
            },
        ),
    ]