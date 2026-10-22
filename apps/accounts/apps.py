from django.apps import AppConfig
from django.db.models.signals import post_migrate


def crear_admin_por_defecto(sender, **kwargs):
    from .models import Usuario

    if Usuario.objects.exists():
        return

    Usuario.objects.create_superuser(
        correo="admin@helpdesk.com",
        nombre="Administrador",
        password="admin",
        debe_cambiar_password=True,
    )


class AccountsConfig(AppConfig):
    name = 'apps.accounts'

    def ready(self):
        post_migrate.connect(crear_admin_por_defecto, sender=self)