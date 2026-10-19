from datetime import timedelta

from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F
from django.db.models.functions import TruncDate
from django.shortcuts import render
from django.utils import dateformat, timezone

from apps.accounts.decorators import admin_required
from apps.tickets.models import Ticket


@admin_required
def reportes(request):
    total = Ticket.objects.count()
    abiertos = Ticket.objects.filter(estado=Ticket.Estado.ABIERTO).count()
    en_proceso = Ticket.objects.filter(estado=Ticket.Estado.EN_PROCESO).count()
    por_confirmar = Ticket.objects.filter(estado=Ticket.Estado.POR_CONFIRMAR).count()
    cerrados = Ticket.objects.filter(estado=Ticket.Estado.CERRADO).count()

    promedio = Ticket.objects.filter(
        estado=Ticket.Estado.CERRADO, cerrado_en__isnull=False
    ).aggregate(
        promedio=Avg(ExpressionWrapper(F("cerrado_en") - F("creado_en"), output_field=DurationField()))
    )["promedio"]
    tiempo_promedio_horas = round(promedio.total_seconds() / 3600, 1) if promedio else None

    porcentaje_resueltos = round((cerrados / total) * 100) if total else 0

    hoy = timezone.localdate()
    dias = [hoy - timedelta(days=i) for i in range(6, -1, -1)]
    por_dia = dict(
        Ticket.objects.filter(creado_en__date__gte=dias[0])
        .annotate(dia=TruncDate("creado_en"))
        .order_by()
        .values_list("dia")
        .annotate(total=Count("id"))
    )

    graficas = {
        "actividad": {
            "labels": [dateformat.format(d, "d-b") for d in dias],
            "data": [por_dia.get(d, 0) for d in dias],
        },
        "distribucion": {
            "labels": ["Abiertos", "En proceso", "Por confirmar", "Cerrados"],
            "data": [abiertos, en_proceso, por_confirmar, cerrados],
        },
    }

    return render(request, "dashboard/reportes.html", {
        "total": total,
        "abiertos": abiertos,
        "en_proceso": en_proceso,
        "por_confirmar": por_confirmar,
        "cerrados": cerrados,
        "tiempo_promedio_horas": tiempo_promedio_horas,
        "porcentaje_resueltos": porcentaje_resueltos,
        "graficas": graficas,
    })