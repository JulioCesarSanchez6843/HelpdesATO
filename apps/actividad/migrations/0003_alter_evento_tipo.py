from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('actividad', '0002_alter_evento_tipo'),
    ]

    operations = [
        migrations.AlterField(
            model_name='evento',
            name='tipo',
            field=models.CharField(choices=[('TICKET_CREADO', 'Ticket creado'), ('TICKET_TOMADO', 'Ticket tomado'), ('TICKET_ASIGNADO', 'Ticket asignado'), ('TICKET_ESTADO', 'Cambio de estado'), ('TICKET_CATEGORIA', 'Cambio de categoría'), ('TICKET_RESUELTO', 'Ticket resuelto'), ('TICKET_COMENTARIO', 'Comentario en ticket'), ('CIERRE_CONFIRMADO', 'Cierre confirmado'), ('CIERRE_RECHAZADO', 'Cierre rechazado'), ('CIERRE_FORZADO', 'Cierre forzado'), ('PASSWORD_SOLICITADO', 'Solicitud de contraseña'), ('PASSWORD_CAMBIADO', 'Contraseña cambiada'), ('PASSWORD_PROPIO', 'Contraseña propia cambiada'), ('USUARIO_CREADO', 'Usuario creado'), ('USUARIO_ESTADO', 'Usuario activado o desactivado'), ('ROL_CAMBIADO', 'Rol cambiado'), ('CONFIG_CAMBIADA', 'Configuración cambiada')], max_length=24),
        ),
    ]