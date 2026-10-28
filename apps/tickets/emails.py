import logging
import pickle
from datetime import timedelta
from email.mime.image import MIMEImage
from pathlib import Path
from django.conf import settings
from django.core import mail
from django.db import transaction
from django.template import TemplateDoesNotExist
from django.template.loader import render_to_string
from django.utils import timezone
from apps.accounts.models import PreferenciasUsuario

from .models import CorreoPendiente

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
        if not PreferenciasUsuario.de(usuario).permite_correo(plantilla):
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

MAX_INTENTOS = 5


def enviar_tras_commit(mensajes):
    if not mensajes:
        return
    if not settings.CORREOS_EN_SEGUNDO_PLANO:
        transaction.on_commit(lambda: _enviar(mensajes))
        return
    CorreoPendiente.objects.bulk_create(
        [
            CorreoPendiente(
                destinatarios=", ".join(mensaje.to)[:500],
                asunto=mensaje.subject[:250],
                contenido=pickle.dumps(mensaje),
            )
            for mensaje in mensajes
        ]
    )


def procesar_pendientes(limite=50):
    enviados = 0
    fallidos = 0
    with transaction.atomic():
        lote = list(
            CorreoPendiente.objects.select_for_update(skip_locked=True)
            .filter(
                estado=CorreoPendiente.Estado.PENDIENTE,
                proximo_intento__lte=timezone.now(),
            )
            .order_by("id")[:limite]
        )
        for correo in lote:
            ahora = timezone.now()
            try:
                mensaje = pickle.loads(bytes(correo.contenido))
                mail.get_connection().send_messages([mensaje])
                correo.estado = CorreoPendiente.Estado.ENVIADO
                correo.enviado_en = ahora
                correo.error = ""
                enviados += 1
            except Exception as error:
                correo.intentos += 1
                correo.error = str(error)[:500]
                if correo.intentos >= MAX_INTENTOS:
                    correo.estado = CorreoPendiente.Estado.ERROR
                else:
                    correo.proximo_intento = ahora + timedelta(
                        minutes=2 ** correo.intentos
                    )
                fallidos += 1
                logger.exception(
                    "No se pudo enviar el correo «%s» a %s.",
                    correo.asunto, correo.destinatarios,
                )
            correo.save()
    return enviados, fallidos


def limpiar_enviados(dias=30):
    limite = timezone.now() - timedelta(days=dias)
    CorreoPendiente.objects.filter(
        estado=CorreoPendiente.Estado.ENVIADO, enviado_en__lt=limite
    ).delete()


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