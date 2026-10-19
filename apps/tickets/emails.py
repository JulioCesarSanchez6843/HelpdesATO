import logging

from django.conf import settings
from django.core import mail
from django.db import transaction
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def _una_linea(texto):
    return " ".join(str(texto).split())


def construir(usuarios, asunto, plantilla, contexto, carpeta="tickets/emails"):
    cuerpo = render_to_string(f"{carpeta}/{plantilla}.txt", contexto)
    vistos = set()
    mensajes = []
    for usuario in usuarios:
        if not usuario or not usuario.activo or not usuario.correo:
            continue
        clave = usuario.correo.lower()
        if clave in vistos:
            continue
        vistos.add(clave)
        mensajes.append(
            mail.EmailMessage(
                subject=_una_linea(asunto),
                body=cuerpo,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[usuario.correo],
            )
        )
    return mensajes


def enviar_tras_commit(mensajes):
    if mensajes:
        transaction.on_commit(lambda: _enviar(mensajes))


def _enviar(mensajes):
    try:
        with mail.get_connection() as conexion:
            for mensaje in mensajes:
                try:
                    conexion.send_messages([mensaje])
                except Exception:
                    logger.exception(
                        "No se pudo enviar el correo «%s» a %s.",
                        mensaje.subject, ", ".join(mensaje.to),
                    )
    except Exception:
        logger.exception("No se pudieron enviar los correos.")