from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from datetime import timedelta

from django.utils import timezone

from apps.actividad.models import Evento
from apps.actividad.registro import registrar as registrar_evento
from apps.tickets.models import Notificacion

from .decorators import admin_required
from .forms import CambiarPasswordForm, FotoPerfilForm, UsuarioCrearForm, UsuarioEditarForm
from .models import FotoPerfil, Usuario
from .permisos import (
    puede_cambiar_password,
    quienes_pueden_cambiar,
    usuarios_gestionables as _usuarios_gestionables,
)
from apps.catalog.models import Sucursal

def login_view(request):
    if request.user.is_authenticated:
        return redirect(settings.LOGIN_REDIRECT_URL)

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
            return redirect(settings.LOGIN_REDIRECT_URL)
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
    return render(request, "accounts/perfil.html", {"form": form})


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
            return redirect("lista_tickets")
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