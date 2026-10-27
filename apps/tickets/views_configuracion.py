from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.accounts.decorators import superadmin_required
from apps.actividad.models import Evento
from apps.actividad.registro import registrar as registrar_evento

from .forms import ConfiguracionSistemaForm
from .models import ConfiguracionSistema, Ticket

HORAS_SIN_EJECUTAR = 48
MAXIMO_FILAS = 50


def _detalle_cambio(configuracion):
    cierre = "activado" if configuracion.cierre_automatico_activo else "desactivado"
    aviso = "activado" if configuracion.recordatorio_activo else "desactivado"
    return (
        f"Cierre automático {cierre} ({configuracion.cierre_automatico_dias} días). "
        f"Recordatorio {aviso} ({configuracion.recordatorio_dias_antes} días antes)."
    )


@superadmin_required
def configuracion_sistema(request):
    if request.method == "POST":
        form = ConfiguracionSistemaForm(
            request.POST, instance=ConfiguracionSistema.actual()
        )
        if form.is_valid():
            hubo_cambios = form.has_changed()
            guardada = form.save(commit=False)
            guardada.actualizado_en = timezone.now()
            guardada.actualizado_por = request.user
            guardada.save()
            if hubo_cambios:
                registrar_evento(
                    Evento.Tipo.CONFIG_CAMBIADA,
                    request.user,
                    detalle=_detalle_cambio(guardada),
                )
            messages.success(request, "Configuración guardada.")
            return redirect("configuracion_sistema")
    else:
        form = ConfiguracionSistemaForm(instance=ConfiguracionSistema.actual())

    configuracion = ConfiguracionSistema.actual()
    ahora = timezone.now()
    sin_ejecutar = configuracion.cierre_automatico_activo and (
        configuracion.ultima_ejecucion is None
        or ahora - configuracion.ultima_ejecucion
        > timedelta(hours=HORAS_SIN_EJECUTAR)
    )

    por_confirmar = Ticket.objects.filter(
        estado=Ticket.Estado.POR_CONFIRMAR, resuelto_en__isnull=False
    )
    pendientes = []
    for ticket in (
        por_confirmar.select_related("sucursal", "creado_por")
        .order_by("resuelto_en")[:MAXIMO_FILAS]
    ):
        cierra_el = ticket.resuelto_en + timedelta(
            days=configuracion.cierre_automatico_dias
        )
        pendientes.append(
            {
                "ticket": ticket,
                "dias": (ahora - ticket.resuelto_en).days,
                "cierra_el": cierra_el,
                "vencido": cierra_el <= ahora,
                "avisado": bool(
                    ticket.recordatorio_cierre_en
                    and ticket.recordatorio_cierre_en >= ticket.resuelto_en
                ),
            }
        )

    return render(
        request,
        "tickets/configuracion.html",
        {
            "form": form,
            "configuracion": configuracion,
            "sin_ejecutar": sin_ejecutar,
            "horas_sin_ejecutar": HORAS_SIN_EJECUTAR,
            "pendientes": pendientes,
            "total_por_confirmar": por_confirmar.count(),
            "vigencia_enlace_dias": settings.CIERRE_TOKEN_MAX_AGE // 86400,
        },
    )