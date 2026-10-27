from datetime import timedelta

from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from . import services
from .models import ConfiguracionSistema, Ticket


def _por_confirmar():
    return Ticket.objects.filter(
        estado=Ticket.Estado.POR_CONFIRMAR, resuelto_en__isnull=False
    )


def para_cerrar(dias, ahora=None):
    ahora = ahora or timezone.now()
    return _por_confirmar().filter(resuelto_en__lte=ahora - timedelta(days=dias))


def para_recordar(dias, dias_antes, ahora=None):
    ahora = ahora or timezone.now()
    return (
        _por_confirmar()
        .filter(
            resuelto_en__lte=ahora - timedelta(days=dias - dias_antes),
            resuelto_en__gt=ahora - timedelta(days=dias),
        )
        .filter(
            Q(recordatorio_cierre_en__isnull=True)
            | Q(recordatorio_cierre_en__lt=F("resuelto_en"))
        )
    )


def _ids(consulta):
    return list(consulta.order_by("resuelto_en").values_list("pk", flat=True))


def _bloqueado(consulta, pk):
    return (
        consulta.select_for_update(of=("self",))
        .select_related("creado_por", "resuelto_por", "area")
        .filter(pk=pk)
        .first()
    )


def ejecutar(dias=None, forzar=False, dry_run=False):
    configuracion = ConfiguracionSistema.actual()
    dias_cierre = dias or configuracion.cierre_automatico_dias
    dias_antes = configuracion.recordatorio_dias_antes
    activo = configuracion.cierre_automatico_activo or forzar
    recordar = (
        activo
        and configuracion.recordatorio_activo
        and 0 < dias_antes < dias_cierre
    )

    resultado = {
        "activo": activo,
        "dias": dias_cierre,
        "a_cerrar": [],
        "a_recordar": [],
        "cerrados": 0,
        "recordatorios": 0,
        "errores": [],
    }

    if activo:
        resultado["a_cerrar"] = _ids(para_cerrar(dias_cierre))
        if recordar:
            resultado["a_recordar"] = _ids(para_recordar(dias_cierre, dias_antes))

    if dry_run:
        return resultado

    for pk in resultado["a_cerrar"]:
        try:
            with transaction.atomic():
                ticket = _bloqueado(para_cerrar(dias_cierre), pk)
                if ticket is None:
                    continue
                services.cerrar_automaticamente(ticket, dias_cierre)
            resultado["cerrados"] += 1
        except Exception as error:
            resultado["errores"].append(f"Ticket #{pk}: {error}")

    for pk in resultado["a_recordar"]:
        try:
            with transaction.atomic():
                ticket = _bloqueado(para_recordar(dias_cierre, dias_antes), pk)
                if ticket is None:
                    continue
                cierra_el = ticket.resuelto_en + timedelta(days=dias_cierre)
                services.enviar_recordatorio_cierre(ticket, cierra_el)
            resultado["recordatorios"] += 1
        except Exception as error:
            resultado["errores"].append(f"Ticket #{pk}: {error}")

    ConfiguracionSistema.objects.filter(pk=configuracion.pk).update(
        ultima_ejecucion=timezone.now(),
        ultima_ejecucion_cerrados=resultado["cerrados"],
        ultima_ejecucion_recordatorios=resultado["recordatorios"],
        ultima_ejecucion_errores=len(resultado["errores"]),
    )
    return resultado