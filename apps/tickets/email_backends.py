import json
from email.utils import parseaddr
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend


class BrevoAPIEmailBackend(BaseEmailBackend):
    endpoint = "https://api.brevo.com/v3/smtp/email"

    def send_messages(self, email_messages):
        enviados = 0
        for mensaje in email_messages or []:
            try:
                self._enviar(mensaje)
                enviados += 1
            except Exception:
                if not self.fail_silently:
                    raise
        return enviados

    def _enviar(self, mensaje):
        nombre, correo = parseaddr(mensaje.from_email or settings.DEFAULT_FROM_EMAIL)
        remitente = {"email": correo}
        if nombre:
            remitente["name"] = nombre

        datos = {
            "sender": remitente,
            "to": [{"email": destino} for destino in mensaje.to],
            "subject": mensaje.subject,
            "textContent": mensaje.body,
        }
        peticion = Request(
            self.endpoint,
            data=json.dumps(datos).encode("utf-8"),
            headers={
                "api-key": settings.BREVO_API_KEY,
                "accept": "application/json",
                "content-type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(peticion, timeout=settings.EMAIL_TIMEOUT or 10):
                pass
        except HTTPError as error:
            detalle = error.read().decode("utf-8", "replace")[:300]
            raise RuntimeError(f"Brevo respondió {error.code}: {detalle}") from error