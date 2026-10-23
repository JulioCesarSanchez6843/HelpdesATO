import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tickets", "0003_datos_sucursal_tickets"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveField(
            model_name="ticket",
            name="asignado_a",
        ),
        migrations.AddField(
            model_name="ticket",
            name="resuelto_por",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="tickets_resueltos",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]