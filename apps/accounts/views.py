from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .decorators import admin_required
from .forms import UsuarioCrearForm, UsuarioEditarForm
from .models import Usuario


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
    usuarios = Usuario.objects.select_related("area", "puesto")
    if q:
        usuarios = usuarios.filter(Q(nombre__icontains=q) | Q(correo__icontains=q))
    return render(request, "accounts/usuarios.html", {"usuarios": usuarios, "q": q})


@admin_required
def nuevo_usuario(request):
    if request.method == "POST":
        form = UsuarioCrearForm(request.POST)
        if form.is_valid():
            usuario = form.save()
            messages.success(request, f"Usuario «{usuario.nombre}» creado.")
            return redirect("lista_usuarios")
    else:
        form = UsuarioCrearForm()
    return render(request, "accounts/usuario_form.html", {"form": form, "titulo": "Nuevo usuario"})


@admin_required
def editar_usuario(request, pk):
    usuario = get_object_or_404(Usuario, pk=pk)
    es_el_mismo = usuario.pk == request.user.pk

    if request.method == "POST":
        form = UsuarioEditarForm(request.POST, instance=usuario, editando_a_si_mismo=es_el_mismo)
        if form.is_valid():
            usuario = form.save()
            nueva = form.nueva_password
            if nueva:
                usuario.set_password(nueva)
                usuario.save(update_fields=["password"])
                messages.success(request, f"Usuario «{usuario.nombre}» actualizado. Se cambió su contraseña.")
            else:
                messages.success(request, f"Usuario «{usuario.nombre}» actualizado.")
            return redirect("lista_usuarios")
    else:
        form = UsuarioEditarForm(instance=usuario, editando_a_si_mismo=es_el_mismo)
    return render(request, "accounts/usuario_form.html", {
        "form": form, "titulo": f"Editar usuario — {usuario.nombre}",
        "es_el_mismo": es_el_mismo,
    })


@admin_required
@require_POST
def cambiar_estado_usuario(request, pk):
    usuario = get_object_or_404(Usuario, pk=pk)
    if usuario.pk == request.user.pk:
        messages.error(request, "No puedes desactivar tu propia cuenta.")
    else:
        usuario.activo = not usuario.activo
        usuario.save(update_fields=["activo"])
        estado = "activado" if usuario.activo else "desactivado"
        messages.success(request, f"Usuario «{usuario.nombre}» {estado}.")
    return redirect("lista_usuarios")