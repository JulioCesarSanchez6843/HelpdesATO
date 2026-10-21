import logging
from email.mime.image import MIMEImage
from pathlib import Path

from django.conf import settings
from django.core import mail
from django.db import transaction
from django.template import TemplateDoesNotExist
from django.template.loader import render_to_string

from . import acceso

logger = logging.getLogger(__name__)

from . import acceso


def _una_linea(texto):
    return " ".join(str(texto).split())


def _firma():
    ruta = Path(settings.BASE_DIR) / "static" / "img" / "firma_ti.jpeg"
    try:
        return "firma_ti", ruta.read_bytes(), "image/jpeg"
    except OSError:
        return None


def _imagen_inline(cid, contenido, tipo):
    subtipo = tipo.split("/")[-1]
    imagen = MIMEImage(contenido, _subtype=subtipo)
    imagen.add_header("Content-ID", f"<{cid}>")
    imagen.add_header("Content-Disposition", "inline")
    return imagen


def _html(carpeta, plantilla, datos):
    try:
        return render_to_string(f"{carpeta}/{plantilla}.html", datos)
    except TemplateDoesNotExist:
        return None

def construir(
    usuarios,
    asunto,
    plantilla,
    contexto,
    carpeta="tickets/emails",
    adjuntos=(),
    imagenes=(),
    contexto_usuario=None,
):
    firma = _firma()
    inline = list(imagenes)
    if firma:
        inline.append(firma)
    vistos = set()
    mensajes = []
    for usuario in usuarios:
        if not usuario or not usuario.activo or not usuario.correo:
            continue
        clave = usuario.correo.lower()
        if clave in vistos:
            continue
        vistos.add(clave)

        datos = {
            **contexto,
            "firma_cid": firma[0] if firma else "",
            "imagenes": [cid for cid, _, _ in imagenes],
        }
        if "ticket" in contexto:
            datos["url_ticket"] = acceso.url_con_acceso(usuario, contexto["ticket"])
        if contexto_usuario:
            datos.update(contexto_usuario(usuario))

        mensaje = mail.EmailMultiAlternatives(
            subject=_una_linea(asunto),
            body=render_to_string(f"{carpeta}/{plantilla}.txt", datos),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[usuario.correo],
        )
        html = _html(carpeta, plantilla, datos)
        if html:
            mensaje.attach_alternative(html, "text/html")
            if inline:
                mensaje.mixed_subtype = "related"
                for cid, contenido, tipo in inline:
                    mensaje.attach(_imagen_inline(cid, contenido, tipo))
        for nombre, contenido, tipo in adjuntos:
            mensaje.attach(nombre, contenido, tipo)
        mensajes.append(mensaje)
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