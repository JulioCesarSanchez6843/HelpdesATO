from django.conf import settings
from django.core import mail
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Envía un correo de prueba y muestra la configuración de correo en uso."

    def add_arguments(self, parser):
        parser.add_argument(
            "destino", nargs="?",
            help="Correo al que se manda la prueba (por defecto, EMAIL_HOST_USER).",
        )

    def handle(self, *args, **options):
        backend = settings.EMAIL_BACKEND
        if backend.endswith("console.EmailBackend"):
            modo = "CONSOLA (el correo solo se imprime, NO se envía de verdad)"
        elif backend.endswith("BrevoAPIEmailBackend"):
            modo = "API de Brevo (HTTPS) — la opción para Render gratis"
        elif backend.endswith("smtp.EmailBackend"):
            modo = f"SMTP {settings.EMAIL_HOST}:{settings.EMAIL_PORT} como {settings.EMAIL_HOST_USER}"
        else:
            modo = backend

        self.stdout.write(f"Modo de envío : {modo}")
        self.stdout.write(f"Remitente     : {settings.DEFAULT_FROM_EMAIL}")
        self.stdout.write(f"Enlaces a     : {settings.SITE_URL}")

        if backend.endswith("BrevoAPIEmailBackend") and "@localhost" in settings.DEFAULT_FROM_EMAIL:
            self.stdout.write(self.style.WARNING(
                "Con Brevo, DEFAULT_FROM_EMAIL debe ser un remitente verificado en tu cuenta de Brevo."
            ))
        if not settings.DEBUG and settings.SITE_URL.startswith("http://localhost"):
            self.stdout.write(self.style.WARNING(
                "SITE_URL apunta a localhost: los enlaces de los correos no abrirán desde otro equipo. "
                "Define SITE_URL con la dirección pública del sitio."
            ))

        destino = options["destino"] or settings.EMAIL_HOST_USER
        if not destino:
            raise CommandError("Indica a qué correo mandar la prueba: probar_correo tucorreo@gmail.com")

        mensaje = mail.EmailMessage(
            subject="Prueba de correo — Helpdesk",
            body=(
                "Si lees esto, el envío de correos del Helpdesk funciona.\n\n"
                f"Sitio: {settings.SITE_URL}\n"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[destino],
        )
        try:
            enviados = mail.get_connection(fail_silently=False).send_messages([mensaje])
        except Exception as error:
            raise CommandError(f"No se pudo enviar el correo: {error}") from error

        if not enviados:
            raise CommandError("El proveedor no aceptó el correo (0 enviados). Revisa la configuración.")
        self.stdout.write(self.style.SUCCESS(f"Correo de prueba enviado a {destino}."))