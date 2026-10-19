from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from . import services
from .forms import TicketForm
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

    pagina = Paginator(tickets, TICKETS_POR_PAGINA).get_page(request.GET.get("page"))

    parametros = request.GET.copy()
    parametros.pop("page", None)

    contexto = {
        "page_obj": pagina,
        "conteos": conteos,
        "q": q,
        "estado_sel": estado,
        "estados": Ticket.Estado.choices,
        "querystring": parametros.urlencode(),
    }

    return render(request, "tickets/mis_tickets.html", contexto)


@login_required
def detalle_ticket(request, pk):
    ticket = get_object_or_404(_tickets_visibles(request.user), pk=pk)

    return render(
        request,
        "tickets/detalle_ticket.html",
        {
            "ticket": ticket,
            "historial": ticket.historial.select_related("usuario"),
            "adjuntos": ticket.adjuntos.defer("contenido"),
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