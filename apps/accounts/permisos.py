from django.db.models import Q

from .models import Usuario


def roles_asignables(actor):
    if actor is None:
        return []
    if actor.es_maestro:
        return [
            Usuario.Rol.SUPERADMIN,
            Usuario.Rol.ENCARGADO,
            Usuario.Rol.BECARIO,
            Usuario.Rol.USUARIO,
        ]
    if actor.es_superadmin:
        return [Usuario.Rol.ENCARGADO, Usuario.Rol.BECARIO, Usuario.Rol.USUARIO]
    if actor.es_encargado:
        return [Usuario.Rol.BECARIO, Usuario.Rol.USUARIO]
    return []


def usuarios_gestionables(actor):
    usuarios = Usuario.objects.select_related("area", "puesto", "sucursal")
    if actor is None:
        return usuarios.none()
    if actor.es_maestro:
        return usuarios
    if actor.es_superadmin:
        return usuarios.filter(
            Q(pk=actor.pk)
            | (~Q(rol=Usuario.Rol.SUPERADMIN) & Q(is_superuser=False))
        )
    if actor.es_encargado:
        return usuarios.filter(sucursal_id=actor.sucursal_id).filter(
            Q(pk=actor.pk)
            | (
                Q(rol__in=[Usuario.Rol.BECARIO, Usuario.Rol.USUARIO])
                & Q(is_superuser=False)
            )
        )
    return usuarios.none()


def puede_cambiar_password(actor, objetivo):
    if actor is None or objetivo is None or objetivo.pk is None:
        return False
    if actor.pk == objetivo.pk:
        return False
    return usuarios_gestionables(actor).filter(pk=objetivo.pk).exists()


def quienes_pueden_cambiar(objetivo):
    candidatos = Usuario.objects.filter(activo=True).exclude(pk=objetivo.pk)
    if objetivo.es_maestro:
        return candidatos.none()
    maestro = Q(is_superuser=True)
    superadmin = Q(rol=Usuario.Rol.SUPERADMIN)
    if objetivo.rol == Usuario.Rol.SUPERADMIN:
        return candidatos.filter(maestro)
    if objetivo.rol == Usuario.Rol.ENCARGADO:
        return candidatos.filter(maestro | superadmin)
    encargados = Q(rol=Usuario.Rol.ENCARGADO, sucursal_id=objetivo.sucursal_id)
    return candidatos.filter(maestro | superadmin | encargados)