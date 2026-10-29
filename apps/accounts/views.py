from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.tokens import default_token_generator
from django.core.cache import cache
from django.db.models import Count, F, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import (
    url_has_allowed_host_and_scheme,
    urlsafe_base64_decode,
    urlsafe_base64_encode,
)
from django.views.decorators.http import require_POST

from django.contrib.auth.decorators import login_required

from datetime import timedelta

from django.utils import timezone

from apps.actividad.models import Evento
from apps.actividad.registro import registrar as registrar_evento
from apps.tickets import emails as correos
from apps.tickets.models import ConfiguracionSistema, CorreoPendiente, Notificacion, Ticket
from apps.tickets.views import _tickets_visibles

from .decorators import admin_required
from .forms import (
    CambiarPasswordForm,
    FotoPerfilForm,
    PreferenciasForm,
    RecuperarPasswordForm,
    UsuarioCrearForm,
    UsuarioEditarForm,
)
from .models import FotoPerfil, PreferenciasUsuario, Usuario
from .permisos import (
    puede_cambiar_password,
    quienes_pueden_cambiar,
    usuarios_gestionables as _usuarios_gestionables,
)
from apps.catalog.models import Sucursal

def login_view(request):
    if request.user.is_authenticated:
        return redirect(PreferenciasUsuario.de(request.user).url_inicio)

    siguiente = request.POST.get("next") or request.GET.get("next") or ""
    contexto = {"next": siguiente}

    if request.method == "POST":
        user = authenticate(
            request,
            username=request.POST.get("correo", "").strip(),
            password=request.POST.get("password", ""),
        )
        if user is not None:
            login(request, user)
            destino_seguro = url_has_allowed_host_and_scheme(
                siguiente, allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            )
            if siguiente and destino_seguro:
                return redirect(siguiente)
            return redirect(PreferenciasUsuario.de(request.user).url_inicio)
        contexto["error"] = "Correo o contraseña incorrectos."

    return render(request, "accounts/login.html", contexto)


@require_POST
def logout_view(request):
    logout(request)
    return redirect("login")

@admin_required
def lista_usuarios(request):
    q = request.GET.get("q", "").strip()
    sucursal = request.GET.get("sucursal", "")
    usuarios = _usuarios_gestionables(request.user)
    if q:
        usuarios = usuarios.filter(Q(nombre__icontains=q) | Q(correo__icontains=q))
    if request.user.es_superadmin and sucursal.isdigit():
        usuarios = usuarios.filter(sucursal_id=int(sucursal))
    else:
        sucursal = ""
    return render(request, "accounts/usuarios.html", {
        "usuarios": usuarios,
        "q": q,
        "sucursal_sel": sucursal,
        "sucursales": Sucursal.objects.all(),
    })


@admin_required
def nuevo_usuario(request):
    if request.method == "POST":
        form = UsuarioCrearForm(request.POST, solicitante=request.user)
        if form.is_valid():
            usuario = form.save()
            registrar_evento(
                Evento.Tipo.USUARIO_CREADO,
                request.user,
                afectado=usuario,
                detalle=f"Cuenta creada con rol {usuario.get_rol_display()}.",
            )
            messages.success(request, f"Usuario «{usuario.nombre}» creado.")
            return redirect("lista_usuarios")
    else:
        form = UsuarioCrearForm(solicitante=request.user)
    return render(request, "accounts/usuario_form.html", {"form": form, "titulo": "Nuevo usuario"})


@admin_required
def editar_usuario(request, pk):
    usuario = get_object_or_404(_usuarios_gestionables(request.user), pk=pk)
    es_el_mismo = usuario.pk == request.user.pk
    rol_anterior = usuario.rol
    puede_password = puede_cambiar_password(request.user, usuario)

    if request.method == "POST":
        form = UsuarioEditarForm(
            request.POST, instance=usuario,
            editando_a_si_mismo=es_el_mismo, solicitante=request.user,
        )
        if form.is_valid():
            usuario = form.save()
            nueva = form.nueva_password
            if nueva:
                usuario.set_password(nueva)
                usuario.debe_cambiar_password = True
                usuario.save(update_fields=["password", "debe_cambiar_password"])
                registrar_evento(
                    Evento.Tipo.PASSWORD_CAMBIADO,
                    request.user,
                    afectado=usuario,
                    detalle=f"{request.user.nombre} cambió la contraseña de {usuario.nombre}.",
                )
                messages.success(request, f"Usuario «{usuario.nombre}» actualizado. Se cambió su contraseña.")
            else:
                messages.success(request, f"Usuario «{usuario.nombre}» actualizado.")
            if usuario.rol != rol_anterior:
                registrar_evento(
                    Evento.Tipo.ROL_CAMBIADO,
                    request.user,
                    afectado=usuario,
                    detalle=(
                        f"Rol cambiado de «{Usuario.Rol(rol_anterior).label}» "
                        f"a «{usuario.get_rol_display()}»."
                    ),
                )
            return redirect("lista_usuarios")
    else:
        form = UsuarioEditarForm(
            instance=usuario, editando_a_si_mismo=es_el_mismo, solicitante=request.user,
        )
    return render(request, "accounts/usuario_form.html", {
        "form": form, "titulo": f"Editar usuario — {usuario.nombre}",
        "es_el_mismo": es_el_mismo,
        "sin_permiso_password": not es_el_mismo and not puede_password,
    })


@admin_required
@require_POST
def cambiar_estado_usuario(request, pk):
    usuario = get_object_or_404(_usuarios_gestionables(request.user), pk=pk)
    if usuario.pk == request.user.pk:
        messages.error(request, "No puedes desactivar tu propia cuenta.")
    elif not usuario.activo and usuario.sucursal_id is None and not usuario.es_superadmin:
        messages.error(
            request,
            "Este usuario no tiene sucursal. Edítalo y asígnale una antes de activarlo.",
        )
    elif not usuario.activo and usuario.sucursal_id and not usuario.sucursal.activa:
        messages.error(
            request,
            "La sucursal de este usuario está desactivada. Actívala antes de activar al usuario.",
        )
    else:
        usuario.activo = not usuario.activo
        usuario.save(update_fields=["activo"])
        estado = "activado" if usuario.activo else "desactivado"
        registrar_evento(
            Evento.Tipo.USUARIO_ESTADO,
            request.user,
            afectado=usuario,
            detalle=f"Cuenta {estado}.",
        )
        messages.success(request, f"Usuario «{usuario.nombre}» {estado}.")
    return redirect("lista_usuarios")

@login_required
def mi_perfil(request):
    if request.method == "POST":
        if request.POST.get("accion") == "eliminar":
            FotoPerfil.objects.filter(usuario=request.user).delete()
            messages.success(request, "Foto de perfil eliminada.")
            return redirect("mi_perfil")
        form = FotoPerfilForm(request.POST, request.FILES)
        if form.is_valid():
            FotoPerfil.objects.update_or_create(
                usuario=request.user,
                defaults={"contenido": form.cleaned_data["foto"]},
            )
            messages.success(request, "Foto de perfil actualizada.")
            return redirect("mi_perfil")
    else:
        form = FotoPerfilForm()
    logos_sucursales = []
    if request.user.es_superadmin:
        logos_sucursales = list(
            Sucursal.objects.defer("logo").filter(
                activa=True, logo_actualizado_en__isnull=False
            )
        )
    return render(request, "accounts/perfil.html", {
        "form": form,
        "logos_sucursales": logos_sucursales,
    })

@login_required
def ajustes(request):
    preferencias = PreferenciasUsuario.de(request.user)
    if request.method == "POST":
        if request.POST.get("accion") == "restablecer":
            PreferenciasUsuario.objects.filter(usuario=request.user).delete()
            messages.success(request, "Ajustes restablecidos a los valores originales.")
            return redirect("ajustes")
        form = PreferenciasForm(request.POST, instance=preferencias)
        if form.is_valid():
            guardada = form.save(commit=False)
            guardada.usuario = request.user
            guardada.save()
            messages.success(request, "Ajustes guardados.")
            return redirect("ajustes")
    else:
        form = PreferenciasForm(instance=preferencias)
    return render(request, "accounts/ajustes.html", {"form": form})


@login_required
def inicio(request):
    return redirect(PreferenciasUsuario.de(request.user).url_inicio)

def _inicio_encargado(usuario, ahora):
    estado = Ticket.Estado
    vivos = [estado.ABIERTO, estado.EN_PROCESO, estado.EN_ESPERA]
    abiertos = vivos + [estado.POR_CONFIRMAR]
    equipo = (
        Usuario.objects.filter(
            activo=True,
            sucursal_id=usuario.sucursal_id,
            rol__in=[Usuario.Rol.BECARIO, Usuario.Rol.ENCARGADO],
        )
        .annotate(
            activos=Count(
                "tickets_asignados",
                filter=Q(tickets_asignados__estado__in=abiertos),
            ),
            vencidos=Count(
                "tickets_asignados",
                filter=Q(
                    tickets_asignados__estado__in=vivos,
                    tickets_asignados__sla_vence_en__lt=ahora,
                ),
            ),
        )
        .order_by("-activos", "nombre")
    )
    return {
        "equipo": equipo,
        "actividad": Evento.objects.filter(sucursal_id=usuario.sucursal_id)[:6],
    }


def _inicio_superadmin(ahora):
    estado = Ticket.Estado
    vivos = [estado.ABIERTO, estado.EN_PROCESO, estado.EN_ESPERA]
    abiertos = vivos + [estado.POR_CONFIRMAR]
    por_sucursal = (
        Sucursal.objects.defer("logo")
        .filter(activa=True)
        .annotate(
            activos=Count("tickets", filter=Q(tickets__estado__in=abiertos)),
            sin_asignar=Count(
                "tickets",
                filter=Q(
                    tickets__estado=estado.ABIERTO,
                    tickets__asignado_a__isnull=True,
                ),
            ),
            vencidos=Count(
                "tickets",
                filter=Q(
                    tickets__estado__in=vivos,
                    tickets__sla_vence_en__lt=ahora,
                ),
            ),
        )
        .order_by("-vencidos", "-sin_asignar", "nombre")
    )
    personas = Usuario.objects.filter(activo=True).aggregate(
        total=Count("id"),
        encargados=Count("id", filter=Q(rol=Usuario.Rol.ENCARGADO)),
        becarios=Count("id", filter=Q(rol=Usuario.Rol.BECARIO)),
        usuarios=Count("id", filter=Q(rol=Usuario.Rol.USUARIO)),
    )
    correos = CorreoPendiente.objects.aggregate(
        pendientes=Count("id", filter=Q(estado=CorreoPendiente.Estado.PENDIENTE)),
        errores=Count("id", filter=Q(estado=CorreoPendiente.Estado.ERROR)),
    )
    return {
        "por_sucursal": por_sucursal,
        "personas": personas,
        "correos": correos,
        "sistema": ConfiguracionSistema.actual(),
        "actividad": Evento.objects.select_related("sucursal")[:6],
    }

@login_required
def panel_inicio(request):
    usuario = request.user
    ahora = timezone.now()
    estado = Ticket.Estado
    tickets = _tickets_visibles(usuario)
    sin_cerrar = ~Q(estado=estado.CERRADO)
    vivos = [estado.ABIERTO, estado.EN_PROCESO, estado.EN_ESPERA]
    local = timezone.localtime(ahora)
    inicio_dia = local.replace(hour=0, minute=0, second=0, microsecond=0)
    inicio_mes = inicio_dia.replace(day=1)

    conteos = tickets.aggregate(
        activos=Count("id", filter=sin_cerrar),
        abiertos=Count("id", filter=Q(estado=estado.ABIERTO)),
        en_proceso=Count("id", filter=Q(estado=estado.EN_PROCESO)),
        por_confirmar=Count("id", filter=Q(estado=estado.POR_CONFIRMAR)),
        sin_asignar=Count(
            "id", filter=Q(estado=estado.ABIERTO, asignado_a__isnull=True)
        ),
        mios=Count("id", filter=sin_cerrar & Q(asignado_a=usuario)),
        vencidos=Count(
            "id", filter=Q(estado__in=vivos, sla_vence_en__lt=ahora)
        ),
        por_vencer=Count(
            "id",
            filter=Q(
                estado__in=vivos,
                sla_vence_en__gte=ahora,
                sla_vence_en__lte=ahora + timedelta(hours=4),
            ),
        ),
        sin_prioridad=Count("id", filter=Q(estado__in=vivos, prioridad="")),
        creados_hoy=Count("id", filter=Q(creado_en__gte=inicio_dia)),
        resueltos_mes=Count("id", filter=Q(resuelto_en__gte=inicio_mes)),
    )

    if usuario.es_superadmin:
        vista = "superadmin"
    elif usuario.es_encargado:
        vista = "encargado"
    elif usuario.es_becario:
        vista = "becario"
    else:
        vista = "usuario"

    if local.hour < 12:
        saludo = "Buenos días"
    elif local.hour < 19:
        saludo = "Buenas tardes"
    else:
        saludo = "Buenas noches"

    contexto = {
        "vista": vista,
        "saludo": saludo,
        "conteos": conteos,
        "pendientes": usuario.notificaciones.filter(leida=False).order_by("-creada_en")[:5],
        "sla": [
            (Ticket.Prioridad(clave).label, horas)
            for clave, horas in settings.SLA_HORAS.items()
        ],
        "reabrir_dias": settings.REABRIR_TICKET_DIAS,
    }

    if vista == "encargado":
        contexto.update(_inicio_encargado(usuario, ahora))
    elif vista == "superadmin":
        contexto.update(_inicio_superadmin(ahora))

    return render(request, "accounts/inicio.html", contexto)

@login_required
def foto_usuario(request, pk):
    foto = get_object_or_404(FotoPerfil, usuario_id=pk)
    respuesta = HttpResponse(bytes(foto.contenido), content_type="image/jpeg")
    respuesta["X-Content-Type-Options"] = "nosniff"
    respuesta["Cache-Control"] = "private, max-age=3600"
    return respuesta

@login_required
def cambiar_password(request):
    if request.method == "POST":
        form = CambiarPasswordForm(request.user, request.POST)
        if form.is_valid():
            era_obligatorio = request.user.debe_cambiar_password
            usuario = form.save()
            usuario.debe_cambiar_password = False
            usuario.save(update_fields=["debe_cambiar_password"])
            update_session_auth_hash(request, usuario)
            registrar_evento(
                Evento.Tipo.PASSWORD_PROPIO,
                usuario,
                afectado=usuario,
                detalle="Cambió su propia contraseña.",
            )
            messages.success(request, "Contraseña actualizada.")
            return redirect("mi_perfil" if era_obligatorio else "lista_tickets")
    else:
        form = CambiarPasswordForm(request.user)
    return render(request, "accounts/cambiar_password.html", {"form": form})

@login_required
@require_POST
def solicitar_cambio_password(request):
    solicitante = request.user
    reciente = Evento.objects.filter(
        tipo=Evento.Tipo.PASSWORD_SOLICITADO,
        actor=solicitante,
        creado_en__gte=timezone.now() - timedelta(hours=1),
    ).exists()
    destinatarios = list(quienes_pueden_cambiar(solicitante))

    if reciente:
        messages.info(request, "Ya enviaste una solicitud hace poco. Espera a que te atiendan.")
    elif not destinatarios:
        messages.error(request, "No hay a quién enviarle la solicitud.")
    else:
        registrar_evento(
            Evento.Tipo.PASSWORD_SOLICITADO,
            solicitante,
            afectado=solicitante,
            detalle="Solicitó que le cambien la contraseña.",
        )
        Notificacion.objects.bulk_create([
            Notificacion(
                usuario=destino,
                tipo=Notificacion.Tipo.SOLICITUD_PASSWORD,
                mensaje=f"{solicitante.nombre} solicitó un cambio de contraseña.",
            )
            for destino in destinatarios
        ])
        messages.success(request, "Solicitud enviada.")
    return redirect("mi_perfil")

def _enviar_enlace_recuperacion(usuario):
    uid = urlsafe_base64_encode(force_bytes(usuario.pk))
    token = default_token_generator.make_token(usuario)
    url = settings.SITE_URL + reverse("restablecer_password", args=[uid, token])
    mensajes = correos.construir(
        [usuario],
        "Restablece tu contraseña",
        "restablecer_password",
        {
            "nombre": usuario.nombre,
            "url_restablecer": url,
            "horas": settings.PASSWORD_RESET_TIMEOUT // 3600,
        },
        carpeta="emails",
    )
    correos.enviar_tras_commit(mensajes)


def recuperar_password(request):
    if request.method == "POST":
        form = RecuperarPasswordForm(request.POST)
        if form.is_valid():
            correo = form.cleaned_data["correo"].strip()
            if cache.add(f"recuperar:{correo.lower()}", 1, 300):
                usuario = Usuario.objects.filter(
                    correo__iexact=correo, activo=True
                ).first()
                if usuario:
                    _enviar_enlace_recuperacion(usuario)
            messages.info(
                request,
                "Si el correo está registrado, te enviamos un enlace para restablecer "
                "tu contraseña. Revisa también tu carpeta de spam; si no llega, "
                "inténtalo de nuevo en unos minutos.",
            )
            return redirect("login")
    else:
        form = RecuperarPasswordForm()
    return render(request, "accounts/recuperar_password.html", {"form": form})


def restablecer_password(request, uidb64, token):
    try:
        pk = urlsafe_base64_decode(uidb64).decode()
        usuario = Usuario.objects.get(pk=pk, activo=True)
    except (TypeError, ValueError, OverflowError, Usuario.DoesNotExist):
        usuario = None

    if usuario is None or not default_token_generator.check_token(usuario, token):
        return render(request, "accounts/restablecer_password.html", {"valido": False})

    if request.method == "POST":
        form = CambiarPasswordForm(usuario, request.POST)
        if form.is_valid():
            usuario = form.save()
            usuario.debe_cambiar_password = False
            usuario.save(update_fields=["debe_cambiar_password"])
            registrar_evento(
                Evento.Tipo.PASSWORD_PROPIO,
                usuario,
                afectado=usuario,
                detalle="Restableció su contraseña desde el enlace enviado por correo.",
            )
            messages.success(request, "Contraseña restablecida. Ya puedes iniciar sesión.")
            return redirect("login")
    else:
        form = CambiarPasswordForm(usuario)
    return render(
        request,
        "accounts/restablecer_password.html",
        {"valido": True, "form": form},
    )