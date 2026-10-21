from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.contrib.auth import login

from apps.accounts.decorators import admin_required
from apps.catalog.models import Area, Categoria

from . import acceso, services
from .forms import TicketForm, TicketGestionForm
from .imagenes import ImagenInvalida
from .models import AdjuntoTicket, Ticket


ESTADOS_VALIDOS = {valor for valor, _ in Ticket.Estado.choices}

TICKETS_POR_PAGINA = 15


def _tickets_visibles(usuario):
    tickets = Ticket.objects.select_related("area", "categoria", "creado_por")

    if usuario.es_admin:
        return tickets

    return tickets.filter(creado_por=usuario)


@login_required
def lista_tickets(request):
    es_admin = request.user.es_admin
    base = _tickets_visibles(request.user)

    conteos = base.aggregate(
        total=Count("id"),
        abiertos=Count("id", filter=Q(estado=Ticket.Estado.ABIERTO)),
        en_proceso=Count("id", filter=Q(estado=Ticket.Estado.EN_PROCESO)),
        por_confirmar=Count("id", filter=Q(estado=Ticket.Estado.POR_CONFIRMAR)),
        cerrados=Count("id", filter=Q(estado=Ticket.Estado.CERRADO)),
    )
    conteos["activos"] = (
        conteos["abiertos"] + conteos["en_proceso"] + conteos["por_confirmar"]
    )

    q = request.GET.get("q", "").strip()
    estado = request.GET.get("estado", "")
    area = request.GET.get("area", "")
    categoria = request.GET.get("categoria", "")

    tickets = base

    if q:
        filtro = Q(titulo__icontains=q)

        if es_admin:
            filtro |= Q(creado_por__nombre__icontains=q)

        tickets = tickets.filter(filtro)

    if estado in ESTADOS_VALIDOS:
        tickets = tickets.filter(estado=estado)
    else:
        estado = ""

    if es_admin and area.isdigit():
        tickets = tickets.filter(area_id=int(area))
    else:
        area = ""

    if es_admin and categoria.isdigit():
        tickets = tickets.filter(categoria_id=int(categoria))
    else:
        categoria = ""

    pagina = Paginator(tickets, TICKETS_POR_PAGINA).get_page(request.GET.get("page"))

    parametros = request.GET.copy()
    parametros.pop("page", None)

    contexto = {
        "page_obj": pagina,
        "conteos": conteos,
        "q": q,
        "estado_sel": estado,
        "area_sel": area,
        "categoria_sel": categoria,
        "estados": Ticket.Estado.choices,
        "querystring": parametros.urlencode(),
    }

    if es_admin:
        contexto["areas"] = Area.objects.all()
        contexto["categorias"] = Categoria.objects.all()
        plantilla = "tickets/panel_admin.html"
    else:
        plantilla = "tickets/mis_tickets.html"

    return render(request, plantilla, contexto)


@login_required
def detalle_ticket(request, pk):
    ticket = get_object_or_404(_tickets_visibles(request.user), pk=pk)

    es_admin = request.user.es_admin

    form_gestion = TicketGestionForm(instance=ticket) if es_admin else None

    if request.method == "POST" and "guardar_gestion" in request.POST:
        if not es_admin:
            raise PermissionDenied

        antes = services.snapshot(ticket)

        instancia = Ticket.objects.get(pk=ticket.pk)

        form_gestion = TicketGestionForm(request.POST, instance=instancia)

        if form_gestion.is_valid():
            with transaction.atomic():
                form_gestion.save()
                instancia.refresh_from_db()
                services.registrar_gestion(instancia, request.user, antes)

            if instancia.estado == Ticket.Estado.POR_CONFIRMAR:
                messages.success(
                    request,
                    "Ticket marcado como resuelto. Se le pidió al usuario "
                    "que confirme el cierre.",
                )
            else:
                messages.success(request, "Ticket actualizado.")

            return redirect("detalle_ticket", pk=pk)

    return render(
        request,
        "tickets/detalle_ticket.html",
        {
            "ticket": ticket,
            "historial": ticket.historial.select_related("usuario"),
            "adjuntos": ticket.adjuntos.defer("contenido"),
            "form_gestion": form_gestion,
            "puede_responder_cierre": (
                ticket.esperando_confirmacion
                and ticket.creado_por_id == request.user.pk
            ),
        },
    )


@login_required
def nuevo_ticket(request):
    if request.method == "POST":
        form = TicketForm(request.POST, request.FILES)

        if form.is_valid():
            try:
                with transaction.atomic():
                    ticket = form.save(commit=False)
                    ticket.creado_por = request.user
                    ticket.area = request.user.area
                    ticket.save()

                    services.guardar_adjuntos(
                        ticket,
                        form.cleaned_data["imagenes"],
                        request.user,
                    )
                    services.registrar_creacion(ticket, request.user)

            except ImagenInvalida as error:
                form.add_error("imagenes", str(error))

            else:
                messages.success(request, "Ticket creado correctamente.")
                return redirect("detalle_ticket", pk=ticket.pk)

    else:
        form = TicketForm()

    return render(request, "tickets/nuevo_ticket.html", {"form": form})


@login_required
def ver_adjunto(request, pk):
    adjunto = get_object_or_404(AdjuntoTicket, pk=pk)

    get_object_or_404(_tickets_visibles(request.user), pk=adjunto.ticket_id)

    respuesta = HttpResponse(
        bytes(adjunto.contenido),
        content_type=adjunto.tipo_contenido,
    )
    respuesta["X-Content-Type-Options"] = "nosniff"
    respuesta["Cache-Control"] = "private, max-age=3600"
    return respuesta

def _aplicar_respuesta(ticket_pk, actor, accion, motivo):
    with transaction.atomic():
        ticket = Ticket.objects.select_for_update().get(pk=ticket_pk)

        if ticket.estado != Ticket.Estado.POR_CONFIRMAR:
            return "ya_respondido"

        if accion == "confirmar":
            services.confirmar_cierre(ticket, actor)
            return "confirmado"

        if accion == "rechazar":
            services.rechazar_cierre(ticket, actor, motivo)
            return "rechazado"

        return "invalida"


def _motivo(request):
    return request.POST.get("motivo", "").strip()[:1000]


@login_required
@require_POST
def responder_cierre(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk, creado_por=request.user)

    resultado = _aplicar_respuesta(
        ticket.pk,
        request.user,
        request.POST.get("accion"),
        _motivo(request),
    )

    mensajes = {
        "confirmado": (messages.success, "Gracias, el ticket quedó cerrado."),
        "rechazado": (messages.success, "Listo, el ticket volvió a «En proceso»."),
        "ya_respondido": (messages.info, "Este ticket ya no está esperando confirmación."),
        "invalida": (messages.error, "Acción no válida."),
    }
    nivel, texto = mensajes[resultado]
    nivel(request, texto)

    return redirect("detalle_ticket", pk=pk)


def confirmar_cierre(request, token):
    ticket = services.ticket_desde_token(token)

    if ticket is None:
        return render(
            request,
            "tickets/confirmar_cierre.html",
            {"invalido": True},
            status=400,
        )

    if request.method == "POST":
        resultado = _aplicar_respuesta(
            ticket.pk,
            ticket.creado_por,
            request.POST.get("accion"),
            _motivo(request),
        )
        if resultado == "invalida":
            return render(request, "tickets/confirmar_cierre.html", {"ticket": ticket})
        return render(
            request,
            "tickets/confirmar_cierre.html",
            {"ticket": ticket, "resultado": resultado},
        )

    return render(request, "tickets/confirmar_cierre.html", {"ticket": ticket})

def acceso_directo(request, token):
    usuario, ticket_pk = acceso.datos_desde_token(token)

    if usuario is None or ticket_pk is None:
        messages.info(request, "El enlace venció. Inicia sesión para continuar.")
        return redirect("login")

    if request.user.pk != usuario.pk:
        login(request, usuario, backend="django.contrib.auth.backends.ModelBackend")

    return redirect("detalle_ticket", pk=ticket_pk)

def marcar_en_proceso(request, token):
    ticket, admin = services.ticket_y_admin_desde_token(token)

    if ticket is None:
        return render(
            request,
            "tickets/en_proceso.html",
            {"invalido": True},
            status=400,
        )

    if request.user.pk != admin.pk:
        login(request, admin, backend="django.contrib.auth.backends.ModelBackend")

    if ticket.estado != Ticket.Estado.ABIERTO:
        return render(
            request,
            "tickets/en_proceso.html",
            {"ticket": ticket, "resultado": "ya_atendido"},
        )

    if request.method == "POST":
        with transaction.atomic():
            ticket = Ticket.objects.select_for_update().get(pk=ticket.pk)
            if ticket.estado == Ticket.Estado.ABIERTO:
                services.poner_en_proceso(ticket, admin)
                resultado = "hecho"
            else:
                resultado = "ya_atendido"
        return render(
            request,
            "tickets/en_proceso.html",
            {"ticket": ticket, "resultado": resultado},
        )

    return render(request, "tickets/en_proceso.html", {"ticket": ticket})


@admin_required
@require_POST
def forzar_cierre(request, pk):
    with transaction.atomic():
        ticket = get_object_or_404(Ticket.objects.select_for_update(), pk=pk)

        if ticket.estado == Ticket.Estado.POR_CONFIRMAR:
            services.forzar_cierre(ticket, request.user)
            messages.success(request, "Ticket cerrado sin confirmación del usuario.")
        else:
            messages.error(
                request, "Solo se puede cerrar así un ticket que está por confirmar."
            )

    return redirect("detalle_ticket", pk=pk)


@login_required
def lista_notificaciones(request):
    notificaciones = request.user.notificaciones.select_related("ticket")[:50]

    return render(
        request,
        "tickets/notificaciones.html",
        {"notificaciones": notificaciones},
    )


@login_required
@require_POST
def abrir_notificacion(request, pk):
    notificacion = get_object_or_404(request.user.notificaciones, pk=pk)

    notificacion.marcar_leida()

    if notificacion.ticket_id is None:
        return redirect("lista_notificaciones")

    return redirect("detalle_ticket", pk=notificacion.ticket_id)


@login_required
@require_POST
def marcar_notificacion_leida(request, pk):
    notificacion = get_object_or_404(request.user.notificaciones, pk=pk)

    notificacion.marcar_leida()

    return redirect("lista_notificaciones")


@login_required
@require_POST
def notificaciones_leer_todas(request):
    request.user.notificaciones.filter(leida=False).update(
        leida=True,
        leida_en=timezone.now(),
    )

    return redirect("lista_notificaciones")