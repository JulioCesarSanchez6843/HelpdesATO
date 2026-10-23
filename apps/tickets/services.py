from django.conf import settings
from django.core import signing
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Usuario
from apps.actividad.models import Evento
from apps.actividad.registro import registrar as registrar_evento

from . import emails, imagenes
from .models import AdjuntoTicket, Historial, Notificacion, Ticket

_SAL_TOKEN = "tickets.confirmar-cierre"
_SAL_PROCESO = "tickets.marcar-en-proceso"


def _personal_activo(ticket):
    return list(
        Usuario.objects.filter(
            Q(rol=Usuario.Rol.SUPERADMIN)
            | Q(is_superuser=True)
            | Q(
                rol__in=[Usuario.Rol.ENCARGADO, Usuario.Rol.BECARIO],
                sucursal_id=ticket.sucursal_id,
            ),
            activo=True,
        ).distinct()
    )

def _admins_activos(ticket):
    return list(
        Usuario.objects.filter(
            Q(rol=Usuario.Rol.SUPERADMIN)
            | Q(is_superuser=True)
            | Q(rol=Usuario.Rol.ENCARGADO, sucursal_id=ticket.sucursal_id),
            activo=True,
        ).distinct()
    )


def _notificar(destinatarios, tipo, mensaje, ticket, actor):
    unicos = {}
    for usuario in destinatarios:
        if usuario and usuario.activo and usuario.pk != actor.pk:
            unicos[usuario.pk] = usuario

    Notificacion.objects.bulk_create(
        [
            Notificacion(usuario=usuario, ticket=ticket, tipo=tipo, mensaje=mensaje)
            for usuario in unicos.values()
        ]
    )


def _url_ticket(ticket):
    return settings.SITE_URL + reverse("detalle_ticket", args=[ticket.pk])


def _url_confirmacion(ticket):
    token = signing.dumps(
        {"t": ticket.pk, "r": ticket.resuelto_en.isoformat()},
        salt=_SAL_TOKEN,
    )
    return settings.SITE_URL + reverse("confirmar_cierre", args=[token])


def _url_en_proceso(ticket, admin):
    token = signing.dumps({"t": ticket.pk, "a": admin.pk}, salt=_SAL_PROCESO)
    return settings.SITE_URL + reverse("marcar_en_proceso", args=[token])


def _contexto(ticket, **extra):
    return {"ticket": ticket, "url_ticket": _url_ticket(ticket), **extra}


def _sin(usuarios, actor):
    return [u for u in usuarios if u.pk != actor.pk]


def ticket_desde_token(token):
    try:
        datos = signing.loads(
            token, salt=_SAL_TOKEN, max_age=settings.CIERRE_TOKEN_MAX_AGE
        )
    except signing.BadSignature:
        return None

    ticket = (
        Ticket.objects.select_related("creado_por", "area")
        .filter(pk=datos.get("t"))
        .first()
    )
    if (
        ticket is None
        or ticket.estado != Ticket.Estado.POR_CONFIRMAR
        or ticket.resuelto_en is None
        or ticket.resuelto_en.isoformat() != datos.get("r")
    ):
        return None
    return ticket


def ticket_y_admin_desde_token(token):
    try:
        datos = signing.loads(
            token, salt=_SAL_PROCESO, max_age=settings.CIERRE_TOKEN_MAX_AGE
        )
    except signing.BadSignature:
        return None, None

    ticket = (
        Ticket.objects.select_related("creado_por", "area", "categoria")
        .filter(pk=datos.get("t"))
        .first()
    )
    admin = Usuario.objects.filter(pk=datos.get("a"), activo=True).first()
    if ticket is None or admin is None or not admin.es_personal:
        return None, None
    if not admin.es_superadmin and admin.sucursal_id != ticket.sucursal_id:
        return None, None
    return ticket, admin


def poner_en_proceso(ticket, admin):
    antes = snapshot(ticket)
    ticket.estado = Ticket.Estado.EN_PROCESO
    ticket.save(update_fields=["estado"])
    registrar_gestion(ticket, admin, antes)


def guardar_adjuntos(ticket, archivos, autor):
    for archivo in archivos:
        nombre, tipo, contenido = imagenes.procesar(archivo)
        AdjuntoTicket.objects.create(
            ticket=ticket,
            nombre=nombre,
            tipo_contenido=tipo,
            contenido=contenido,
            tamano=len(contenido),
            subido_por=autor,
        )


def registrar_creacion(ticket, autor):
    Historial.objects.create(
        ticket=ticket,
        usuario=autor,
        tipo=Historial.Tipo.CREACION,
        contenido="Ticket creado.",
    )
    registrar_evento(
        Evento.Tipo.TICKET_CREADO,
        autor,
        ticket=ticket,
        detalle=ticket.titulo,
    )

    admins = _personal_activo(ticket)

    _notificar(
        admins,
        Notificacion.Tipo.NUEVO_TICKET,
        f"Nuevo ticket #{ticket.pk}: {ticket.titulo}",
        ticket,
        autor,
    )

    contexto = _contexto(ticket)
    imagenes_ticket = [
        (f"imagen{a.pk}", bytes(a.contenido), a.tipo_contenido)
        for a in ticket.adjuntos.all()
    ]
    mensajes = emails.construir(
        _sin(admins, autor),
        f"Nuevo ticket #{ticket.pk}: {ticket.titulo}",
        "nuevo_ticket_admin",
        contexto,
        imagenes=imagenes_ticket,
        contexto_usuario=lambda admin: {
            "url_en_proceso": _url_en_proceso(ticket, admin)
        },
    )
    mensajes += emails.construir(
        [ticket.creado_por],
        f"Recibimos tu ticket #{ticket.pk}",
        "ticket_recibido",
        contexto,
    )
    emails.enviar_tras_commit(mensajes)


def snapshot(ticket):
    return {
        "estado": ticket.estado,
        "categoria_id": ticket.categoria_id,
    }


def registrar_gestion(ticket, actor, antes):
    if ticket.estado != antes["estado"]:
        anterior = dict(Ticket.Estado.choices)[antes["estado"]]
        por_confirmar = ticket.estado == Ticket.Estado.POR_CONFIRMAR

        if por_confirmar:
            ticket.resuelto_por = actor
            ticket.save(update_fields=["resuelto_por"])
        elif ticket.resuelto_por_id:
            ticket.resuelto_por = None
            ticket.save(update_fields=["resuelto_por"])

        texto = (
            f"Estado cambiado de «{anterior}» a «{ticket.get_estado_display()}»."
        )
        if por_confirmar:
            texto += f" Nota de resolución: {ticket.nota_resolucion}"

        Historial.objects.create(
            ticket=ticket,
            usuario=actor,
            tipo=Historial.Tipo.CAMBIO_ESTADO,
            contenido=texto,
        )

        registrar_evento(
            Evento.Tipo.TICKET_RESUELTO if por_confirmar else Evento.Tipo.TICKET_ESTADO,
            actor,
            ticket=ticket,
            detalle=texto,
        )

        destinatarios = _sin([ticket.creado_por], actor)

        if por_confirmar:
            _notificar(
                [ticket.creado_por],
                Notificacion.Tipo.POR_CONFIRMAR,
                f"Tu ticket #{ticket.pk} fue resuelto. Confirma si quedó solucionado.",
                ticket,
                actor,
            )
            mensajes = emails.construir(
                destinatarios,
                f"Ticket #{ticket.pk} resuelto: confirma el cierre",
                "por_confirmar",
                _contexto(ticket, url_confirmacion=_url_confirmacion(ticket)),
            )
        else:
            _notificar(
                [ticket.creado_por],
                Notificacion.Tipo.CAMBIO_ESTADO,
                f"Tu ticket #{ticket.pk} ahora está «{ticket.get_estado_display()}».",
                ticket,
                actor,
            )
            mensajes = emails.construir(
                destinatarios,
                f"Ticket #{ticket.pk}: ahora está «{ticket.get_estado_display()}»",
                "cambio_estado",
                _contexto(ticket, estado_anterior=anterior),
            )
        emails.enviar_tras_commit(mensajes)

    if ticket.categoria_id != antes["categoria_id"]:
        nueva = ticket.categoria.nombre if ticket.categoria else "Sin categoría"
        registrar_evento(
            Evento.Tipo.TICKET_CATEGORIA,
            actor,
            ticket=ticket,
            detalle=f"Categoría cambiada a «{nueva}».",
        )
        Historial.objects.create(
            ticket=ticket,
            usuario=actor,
            tipo=Historial.Tipo.CATEGORIA,
            contenido=f"Categoría cambiada a «{nueva}».",
        )


def confirmar_cierre(ticket, actor):
    ticket.estado = Ticket.Estado.CERRADO
    ticket.cerrado_en = timezone.now()
    ticket.save(update_fields=["estado", "cerrado_en"])

    Historial.objects.create(
        ticket=ticket,
        usuario=actor,
        tipo=Historial.Tipo.CAMBIO_ESTADO,
        contenido=(
            "Estado cambiado de «Por confirmar» a «Cerrado». "
            "El usuario confirmó que el problema quedó resuelto."
        ),
    )
    registrar_evento(
        Evento.Tipo.CIERRE_CONFIRMADO,
        actor,
        ticket=ticket,
        afectado=ticket.resuelto_por,
        detalle="El usuario confirmó que el problema quedó resuelto.",
    )
    admins = _admins_activos(ticket)
    _notificar(
        admins,
        Notificacion.Tipo.TICKET_CERRADO,
        f"{actor.nombre} confirmó el cierre del ticket #{ticket.pk}.",
        ticket,
        actor,
    )

    contexto = _contexto(ticket)
    mensajes = emails.construir(
        admins,
        f"Ticket #{ticket.pk} cerrado: el usuario confirmó",
        "cierre_confirmado_admin",
        contexto,
    )
    mensajes += emails.construir(
        [ticket.creado_por],
        f"Tu ticket #{ticket.pk} quedó cerrado",
        "ticket_cerrado",
        contexto,
    )
    emails.enviar_tras_commit(mensajes)


def rechazar_cierre(ticket, actor, motivo=""):
    resolvio = ticket.resuelto_por
    ticket.estado = Ticket.Estado.EN_PROCESO
    ticket.resuelto_en = None
    ticket.resuelto_por = None
    ticket.nota_resolucion = ""
    ticket.save(
        update_fields=["estado", "resuelto_en", "resuelto_por", "nota_resolucion"]
    )

    texto = (
        "Estado cambiado de «Por confirmar» a «En proceso». "
        "El usuario indicó que el problema NO está resuelto."
    )
    if motivo:
        texto += f" Motivo: {motivo}"
    registrar_evento(
        Evento.Tipo.CIERRE_RECHAZADO,
        actor,
        ticket=ticket,
        afectado=resolvio,
        detalle=texto,
    )

    Historial.objects.create(
        ticket=ticket,
        usuario=actor,
        tipo=Historial.Tipo.CAMBIO_ESTADO,
        contenido=texto,
    )

    admins = _admins_activos(ticket)
    _notificar(
        admins,
        Notificacion.Tipo.CIERRE_RECHAZADO,
        f"{actor.nombre} indicó que el ticket #{ticket.pk} NO está resuelto.",
        ticket,
        actor,
    )
    emails.enviar_tras_commit(
        emails.construir(
            admins,
            f"Ticket #{ticket.pk} reabierto: el usuario dice que no está resuelto",
            "cierre_rechazado_admin",
            _contexto(ticket, motivo=motivo),
        )
    )

def forzar_cierre(ticket, admin, justificacion):
    ticket.estado = Ticket.Estado.CERRADO
    ticket.cerrado_en = timezone.now()
    ticket.justificacion_cierre = justificacion
    ticket.save(update_fields=["estado", "cerrado_en", "justificacion_cierre"])

    Historial.objects.create(
        ticket=ticket,
        usuario=admin,
        tipo=Historial.Tipo.CAMBIO_ESTADO,
        contenido=(
            "Estado cambiado de «Por confirmar» a «Cerrado». "
            "Cerrado por el administrador sin confirmación del usuario. "
            f"Justificación: {justificacion}"
        ),
    )
    registrar_evento(
        Evento.Tipo.CIERRE_FORZADO,
        admin,
        ticket=ticket,
        detalle=justificacion,
    )

    _notificar(
        [ticket.creado_por],
        Notificacion.Tipo.TICKET_CERRADO,
        f"Tu ticket #{ticket.pk} fue cerrado por el administrador.",
        ticket,
        admin,
    )
    emails.enviar_tras_commit(
        emails.construir(
            _sin([ticket.creado_por], admin),
            f"Tu ticket #{ticket.pk} fue cerrado",
            "cierre_forzado",
            _contexto(ticket),
        )
    )

def tomar_ticket(ticket, actor):
    antes = snapshot(ticket)
    ticket.asignado_a = actor
    campos = ["asignado_a"]
    if ticket.estado == Ticket.Estado.ABIERTO:
        ticket.estado = Ticket.Estado.EN_PROCESO
        campos.append("estado")
    ticket.save(update_fields=campos)

    Historial.objects.create(
        ticket=ticket,
        usuario=actor,
        tipo=Historial.Tipo.ASIGNACION,
        contenido=f"{actor.nombre} tomó el ticket.",
    )
    registrar_evento(
        Evento.Tipo.TICKET_TOMADO,
        actor,
        ticket=ticket,
        detalle=f"{actor.nombre} tomó el ticket.",
    )

    registrar_gestion(ticket, actor, antes)

    if actor.es_becario:
        _notificar(
            _admins_activos(ticket),
            Notificacion.Tipo.TICKET_ASIGNADO,
            f"{actor.nombre} tomó el ticket #{ticket.pk}: {ticket.titulo}",
            ticket,
            actor,
        )


def asignar_ticket(ticket, actor, destino):
    ticket.asignado_a = destino
    ticket.save(update_fields=["asignado_a"])

    if destino is None:
        texto = "El ticket quedó sin asignar."
    else:
        texto = f"Ticket asignado a {destino.nombre}."

    Historial.objects.create(
        ticket=ticket,
        usuario=actor,
        tipo=Historial.Tipo.ASIGNACION,
        contenido=texto,
    )

    registrar_evento(
        Evento.Tipo.TICKET_ASIGNADO,
        actor,
        ticket=ticket,
        afectado=destino,
        detalle=texto,
    )

    if destino is not None:
        _notificar(
            [destino],
            Notificacion.Tipo.TICKET_ASIGNADO,
            f"{actor.nombre} te asignó el ticket #{ticket.pk}: {ticket.titulo}",
            ticket,
            actor,
        )