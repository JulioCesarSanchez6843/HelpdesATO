from .models import Evento


def registrar(tipo, actor, ticket=None, afectado=None, detalle=""):
    sucursal_id = None
    if ticket is not None:
        sucursal_id = ticket.sucursal_id
    elif afectado is not None:
        sucursal_id = afectado.sucursal_id
    if sucursal_id is None and actor is not None:
        sucursal_id = actor.sucursal_id
    return Evento.objects.create(
        tipo=tipo,
        actor=actor,
        actor_nombre=actor.nombre if actor else "",
        afectado=afectado,
        afectado_nombre=afectado.nombre if afectado else "",
        ticket=ticket,
        ticket_numero=ticket.pk if ticket else None,
        sucursal_id=sucursal_id,
        detalle=detalle,
    )