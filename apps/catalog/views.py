from django.contrib import messages
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.decorators import admin_required, superadmin_required
from .forms import AreaForm, CategoriaForm, PuestoForm, SucursalForm
from .models import Area, Categoria, Puesto, Sucursal

CATALOGOS = {
    "areas": {
        "modelo": Area, "form": AreaForm, "titulo": "Áreas", "singular": "área",
        "descripcion": "Gestiona las áreas de la organización.",
        "relaciones": ("usuarios", "tickets"),
    },
    "categorias": {
        "modelo": Categoria, "form": CategoriaForm, "titulo": "Categorías", "singular": "categoría",
        "descripcion": "Gestiona las categorías de incidencias técnicas.",
        "relaciones": ("tickets",),
    },
    "puestos": {
        "modelo": Puesto, "form": PuestoForm, "titulo": "Puestos", "singular": "puesto",
        "descripcion": "Gestiona los puestos de los usuarios.",
        "relaciones": ("usuarios",),
    },
}


def _errores(form):
    return " ".join(e for lista in form.errors.values() for e in lista)

def _puede_modificar(usuario, registro):
    if usuario.es_superadmin:
        return True
    return registro.sucursal_id is not None and registro.sucursal_id == usuario.sucursal_id


@admin_required
def lista(request, clave):
    cfg = CATALOGOS[clave]

    if request.method == "POST":
        form = cfg["form"](request.POST, solicitante=request.user)
        if form.is_valid():
            registro = form.save()
            messages.success(request, f"{cfg['singular'].capitalize()} «{registro.nombre}» creado.")
        else:
            messages.error(request, _errores(form))
        return redirect(f"lista_{clave}")

    consulta = cfg["modelo"].objects.visibles_para(request.user)
    for rel in cfg["relaciones"]:
        consulta = consulta.annotate(**{f"n_{rel}": Count(rel, distinct=True)})
    registros = list(consulta)
    for registro in registros:
        registro.en_uso = sum(getattr(registro, f"n_{rel}") for rel in cfg["relaciones"])
        registro.editable = _puede_modificar(request.user, registro)

    return render(request, "catalog/catalogo.html", {
        "registros": registros,
        "titulo": cfg["titulo"],
        "singular": cfg["singular"],
        "descripcion": cfg["descripcion"],
        "sucursales": Sucursal.objects.all(),
        "url_lista": f"lista_{clave}",
        "url_editar": f"editar_{clave}",
        "url_eliminar": f"eliminar_{clave}",
    })


@admin_required
@require_POST
def editar(request, clave, pk):
    cfg = CATALOGOS[clave]
    registro = get_object_or_404(cfg["modelo"].objects.visibles_para(request.user), pk=pk)
    if not _puede_modificar(request.user, registro):
        messages.error(request, "No tienes permiso para modificar ese registro.")
        return redirect(f"lista_{clave}")
    form = cfg["form"](request.POST, instance=registro, solicitante=request.user)
    if form.is_valid():
        form.save()
        messages.success(request, f"{cfg['singular'].capitalize()} actualizado.")
    else:
        messages.error(request, _errores(form))
    return redirect(f"lista_{clave}")


@admin_required
@require_POST
def eliminar(request, clave, pk):
    cfg = CATALOGOS[clave]
    registro = get_object_or_404(cfg["modelo"].objects.visibles_para(request.user), pk=pk)
    if not _puede_modificar(request.user, registro):
        messages.error(request, "No tienes permiso para eliminar ese registro.")
        return redirect(f"lista_{clave}")
    en_uso = sum(getattr(registro, rel).count() for rel in cfg["relaciones"])
    if en_uso:
        messages.error(
            request,
            f"No se puede eliminar «{registro.nombre}»: está en uso por {en_uso} registro(s).",
        )
    else:
        registro.delete()
        messages.success(request, f"{cfg['singular'].capitalize()} «{registro.nombre}» eliminado.")
    return redirect(f"lista_{clave}")

@superadmin_required
def lista_sucursales(request):
    sucursales = Sucursal.objects.annotate(
        n_usuarios=Count("usuarios", distinct=True),
        n_tickets=Count("tickets", distinct=True),
    )
    return render(request, "catalog/sucursales.html", {"sucursales": sucursales})


@superadmin_required
def nueva_sucursal(request):
    if request.method == "POST":
        form = SucursalForm(request.POST)
        if form.is_valid():
            sucursal = form.save()
            messages.success(request, f"Sucursal «{sucursal.nombre}» creada.")
            return redirect("lista_sucursales")
    else:
        form = SucursalForm()
    return render(request, "catalog/sucursal_form.html", {
        "form": form,
        "titulo": "Nueva sucursal",
    })


@superadmin_required
def editar_sucursal(request, pk):
    sucursal = get_object_or_404(Sucursal, pk=pk)
    if request.method == "POST":
        form = SucursalForm(request.POST, instance=sucursal)
        if form.is_valid():
            form.save()
            messages.success(request, f"Sucursal «{sucursal.nombre}» actualizada.")
            return redirect("lista_sucursales")
    else:
        form = SucursalForm(instance=sucursal)
    return render(request, "catalog/sucursal_form.html", {
        "form": form,
        "titulo": f"Editar sucursal — {sucursal.nombre}",
    })


@superadmin_required
@require_POST
def eliminar_sucursal(request, pk):
    sucursal = get_object_or_404(Sucursal, pk=pk)
    en_uso = (
        sucursal.usuarios.count()
        + sucursal.tickets.count()
        + sucursal.area_set.count()
        + sucursal.categoria_set.count()
        + sucursal.puesto_set.count()
    )
    if en_uso:
        messages.error(
            request,
            f"No se puede eliminar «{sucursal.nombre}»: está en uso por {en_uso} registro(s).",
        )
    else:
        sucursal.delete()
        messages.success(request, f"Sucursal «{sucursal.nombre}» eliminada.")
    return redirect("lista_sucursales")