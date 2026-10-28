from decouple import config
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand
from django.core.validators import validate_email

from apps.accounts.models import Usuario


class Command(BaseCommand):
    help = "Crea el administrador inicial desde variables de entorno."

    def handle(self, *args, **options):
        correo = config("ADMIN_CORREO", default="").strip()
        nombre = config("ADMIN_NOMBRE", default="").strip() or "Administrador"
        password = config("ADMIN_PASSWORD", default="")

        if not correo or not password:
            self.stdout.write("ADMIN_CORREO o ADMIN_PASSWORD no están definidas: no se crea administrador.")
            return

        try:
            validate_email(correo)
        except ValidationError:
            self.stdout.write(self.style.WARNING(f"{correo!r} no es un correo válido."))
            return

        if Usuario.objects.filter(correo__iexact=correo).exists():
            self.stdout.write(f"El administrador {correo} ya existe: no se modifica.")
            return

        Usuario.objects.create_superuser(
            correo=correo,
            nombre=nombre,
            password=password,
            debe_cambiar_password=True,
        )
        self.stdout.write(self.style.SUCCESS(f"Administrador {correo} creado."))