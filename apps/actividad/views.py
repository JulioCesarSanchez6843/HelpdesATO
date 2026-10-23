from io import BytesIO

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import render
from django.utils.dateparse import parse_date
from openpyxl import Workbook

from apps.accounts.models import Usuario
from apps.catalog.models import Sucursal
from apps.dashboard.views import _escribir, _estilizar_encabezado, _local

from .models import Evento

EVENTOS_POR_PAGINA = 25
MAXIMO_EXPORTAR = 20000
TIPOS_VALIDOS = {valor for valor, _ in Evento.Tipo.choices}


def _eventos_visibles(usuario):
    eventos = Evento.objects.select_related("sucursal")
    if usuario.es_superadmin:
        return eventos
    if usuario.es_encargado:
        return eventos.filter(sucursal_id=usuario.sucursal_id)
    return eventos.filter(
        Q(actor=usuario)
        | Q(afectado=usuario)
        | Q(ticket__creado_por=usuario)
        | Q(ticket__resuelto_por=usuario)
    ).distinct()


def _personas(usuario):
    if usuario.es_superadmin:
        return Usuario.objects.all()
    if usuario.es_encargado:
        return Usuario.objects.filter(sucursal_id=usuario.sucursal_id)
    return Usuario.objects.none()


def _fecha(request, nombre):
    try:
        return parse_date(request.GET.get(nombre, ""))
    except ValueError:
        return None


def _aplicar_filtros(request, eventos):
    usuario = request.user

    desde = _fecha(request, "desde")
    hasta = _fecha(request, "hasta")
    if desde:
        eventos = eventos.filter(creado_en__date__gte=desde)
    if hasta:
        eventos = eventos.filter(creado_en__date__lte=hasta)

    tipo = request.GET.get("tipo", "")
    if tipo in TIPOS_VALIDOS:
        eventos = eventos.filter(tipo=tipo)
    else:
        tipo = ""

    persona = request.GET.get("persona", "")
    if usuario.es_admin and persona.isdigit():
        eventos = eventos.filter(
            Q(actor_id=int(persona)) | Q(afectado_id=int(persona))
        )
    else:
        persona = ""

    sucursal = request.GET.get("sucursal", "")
    if usuario.es_superadmin and sucursal.isdigit():
        eventos = eventos.filter(sucursal_id=int(sucursal))
    else:
        sucursal = ""

    ticket = request.GET.get("ticket", "").strip().lstrip("#")
    if ticket.isdigit():
        eventos = eventos.filter(ticket_numero=int(ticket))
    else:
        ticket = ""

    filtros = {
        "desde": desde.isoformat() if desde else "",
        "hasta": hasta.isoformat() if hasta else "",
        "tipo": tipo,
        "persona": persona,
        "sucursal": sucursal,
        "ticket": ticket,
    }
    return eventos, filtros


def _resumen(eventos):
    tipos = Evento.Tipo
    filas = (
        eventos.filter(actor__isnull=False)
        .values("actor_id", "actor__nombre")
        .annotate(
            creados=Count("id", filter=Q(tipo=tipos.TICKET_CREADO)),
            tomados=Count("id", filter=Q(tipo=tipos.TICKET_TOMADO)),
            delegados=Count("id", filter=Q(tipo=tipos.TICKET_ASIGNADO)),
            resueltos=Count("id", filter=Q(tipo=tipos.TICKET_RESUELTO)),
            forzados=Count("id", filter=Q(tipo=tipos.CIERRE_FORZADO)),
            passwords=Count("id", filter=Q(tipo=tipos.PASSWORD_CAMBIADO)),
            total=Count("id"),
        )
        .order_by("actor__nombre")
    )
    return list(filas)


@login_required
def lista(request):
    base = _eventos_visibles(request.user)
    eventos, filtros = _aplicar_filtros(request, base)
    tipos = Evento.Tipo

    totales = eventos.aggregate(
        total=Count("id"),
        creados=Count("id", filter=Q(tipo=tipos.TICKET_CREADO)),
        resueltos=Count("id", filter=Q(tipo=tipos.TICKET_RESUELTO)),
        forzados=Count("id", filter=Q(tipo=tipos.CIERRE_FORZADO)),
        passwords=Count("id", filter=Q(tipo=tipos.PASSWORD_CAMBIADO)),
    )
    resumen = _resumen(eventos) if request.user.es_admin else []

    pagina = Paginator(eventos, EVENTOS_POR_PAGINA).get_page(request.GET.get("page"))
    parametros = request.GET.copy()
    parametros.pop("page", None)

    return render(request, "actividad/lista.html", {
        "page_obj": pagina,
        "totales": totales,
        "resumen": resumen,
        "filtros": filtros,
        "tipos": Evento.Tipo.choices,
        "personas": _personas(request.user),
        "sucursales": Sucursal.objects.all() if request.user.es_superadmin else [],
        "querystring": parametros.urlencode(),
    })


@login_required
def exportar(request):
    base = _eventos_visibles(request.user)
    eventos, _ = _aplicar_filtros(request, base)
    resumen = _resumen(eventos) if request.user.es_admin else []

    wb = Workbook()
    hoja = wb.active
    hoja.title = "Actividad"
    encabezados = [
        "Fecha", "Quién", "Acción", "Persona afectada",
        "Ticket", "Sucursal", "Detalle",
    ]
    hoja.append(encabezados)
    _estilizar_encabezado(hoja, 1, len(encabezados))

    for fila, evento in enumerate(eventos[:MAXIMO_EXPORTAR], start=2):
        valores = [
            _local(evento.creado_en),
            evento.actor_nombre,
            evento.get_tipo_display(),
            evento.afectado_nombre,
            evento.ticket_numero or "",
            evento.sucursal.nombre if evento.sucursal else "",
            evento.detalle,
        ]
        for col, valor in enumerate(valores, start=1):
            _escribir(hoja, fila, col, valor, "dd/mm/yyyy hh:mm" if col == 1 else None)

    for i, ancho in enumerate([18, 24, 26, 24, 10, 20, 70], start=1):
        hoja.column_dimensions[chr(64 + i)].width = ancho

    if request.user.es_admin:
        hoja_resumen = wb.create_sheet("Resumen por persona", 0)
        encabezados_resumen = [
            "Persona", "Tickets creados", "Tickets tomados", "Tickets delegados",
            "Tickets resueltos", "Cierres forzados", "Contraseñas cambiadas",
            "Total de acciones",
        ]
        hoja_resumen.append(encabezados_resumen)
        _estilizar_encabezado(hoja_resumen, 1, len(encabezados_resumen))
        for fila, datos in enumerate(resumen, start=2):
            valores = [
                datos["actor__nombre"], datos["creados"], datos["tomados"],
                datos["delegados"], datos["resueltos"], datos["forzados"],
                datos["passwords"], datos["total"],
            ]
            for col, valor in enumerate(valores, start=1):
                _escribir(hoja_resumen, fila, col, valor)
        for i, ancho in enumerate([28, 16, 16, 18, 18, 16, 22, 18], start=1):
            hoja_resumen.column_dimensions[chr(64 + i)].width = ancho

    salida = BytesIO()
    wb.save(salida)
    respuesta = HttpResponse(
        salida.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    respuesta["Content-Disposition"] = 'attachment; filename="actividad.xlsx"'
    return respuesta