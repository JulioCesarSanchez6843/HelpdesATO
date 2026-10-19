import os

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand
from django.core.validators import validate_email

from apps.accounts.models import Usuario


class Command(BaseCommand):
    help = "Crea el administrador inicial desde variables de entorno (idempotente)."

    def handle(self, *args, **options):
        correo = os.environ.get("DJANGO_SUPERUSER_CORREO", "").strip()
        nombre = os.environ.get("DJANGO_SUPERUSER_NOMBRE", "").strip() or "Administrador"
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "")
        reiniciar = os.environ.get("DJANGO_SUPERUSER_RESET", "") == "1"

        if not correo:
            self.stdout.write("DJANGO_SUPERUSER_CORREO no está definida: no se crea administrador.")
            return
        try:
            validate_email(correo)
        except ValidationError:
            self.stdout.write(self.style.WARNING(
                f"DJANGO_SUPERUSER_CORREO ({correo!r}) no es un correo válido: no se crea administrador."
            ))
            return
        if not password:
            self.stdout.write(self.style.WARNING(
                "DJANGO_SUPERUSER_PASSWORD no está definida: no se crea ni se modifica el administrador."
            ))
            return

        usuario = Usuario.objects.filter(correo__iexact=correo).first()

        if usuario is None:
            Usuario.objects.create_superuser(
                correo=correo, nombre=nombre, password=password,
            )
            self.stdout.write(self.style.SUCCESS(f"Administrador {correo} creado."))
            return

        if reiniciar or not usuario.has_usable_password():
            usuario.set_password(password)
            usuario.activo = True
            usuario.save()
            self.stdout.write(self.style.SUCCESS(f"Contraseña de {correo} establecida."))
            return

        self.stdout.write(f"El administrador {correo} ya existe: no se modifica.")