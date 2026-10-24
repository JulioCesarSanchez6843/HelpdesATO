from django.db import migrations, models


def asignar_sucursal_a_datos_viejos(apps, schema_editor):
    Usuario = apps.get_model("accounts", "Usuario")
    Sucursal = apps.get_model("catalog", "Sucursal")
    Ticket = apps.get_model("tickets", "Ticket")

    Usuario.objects.filter(rol="ADMIN").update(rol="SUPERADMIN")

    sin_sucursal = Usuario.objects.filter(sucursal__isnull=True, is_superuser=False).exclude(
        rol="SUPERADMIN"
    )
    tickets_sin_sucursal = Ticket.objects.filter(sucursal__isnull=True)
    if not sin_sucursal.exists() and not tickets_sin_sucursal.exists():
        return

    sucursal = Sucursal.objects.order_by("id").first()
    if sucursal is None:
        sucursal = Sucursal.objects.create(nombre="Tollocan")
    sin_sucursal.update(sucursal=sucursal)
    tickets_sin_sucursal.update(sucursal=sucursal)


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ('accounts', '0004_datos_roles_sucursales'),
        ('auth', '0012_alter_user_first_name_max_length'),
        ('catalog', '0002_sucursal'),
        ('tickets', '0002_ticket_asignado_a_ticket_sucursal_and_more'),
    ]

    operations = [
        migrations.RunPython(asignar_sucursal_a_datos_viejos, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='usuario',
            constraint=models.CheckConstraint(condition=models.Q(('rol', 'SUPERADMIN'), ('is_superuser', True), ('sucursal__isnull', False), _connector='OR'), name='usuario_sucursal_obligatoria'),
        ),
    ]