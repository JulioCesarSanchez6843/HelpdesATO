from django.contrib import messages
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.decorators import admin_required
from .forms import AreaForm, CategoriaForm, PuestoForm
from .models import Area, Categoria, Puesto

CATALOGOS = {
    "areas": {
        "modelo": Area, "form": AreaForm, "titulo": "Áreas", "singular": "área",
        "descripcion": "Gestiona las áreas de la organización.",
        "relaciones": ("usuarios",),
    },
    "categorias": {
        "modelo": Categoria, "form": CategoriaForm, "titulo": "Categorías", "singular": "categoría",
        "descripcion": "Gestiona las categorías de incidencias técnicas.",
        "relaciones": (),
    },
    "puestos": {
        "modelo": Puesto, "form": PuestoForm, "titulo": "Puestos", "singular": "puesto",
        "descripcion": "Gestiona los puestos de los usuarios.",
        "relaciones": ("usuarios",),
    },
}


def _errores(form):
    return " ".join(e for lista in form.errors.values() for e in lista)


@admin_required
def lista(request, clave):
    cfg = CATALOGOS[clave]

    if request.method == "POST":
        form = cfg["form"](request.POST)
        if form.is_valid():
            registro = form.save()
            messages.success(request, f"{cfg['singular'].capitalize()} «{registro.nombre}» creado.")
        else:
            messages.error(request, _errores(form))
        return redirect(f"lista_{clave}")

    consulta = cfg["modelo"].objects.all()
    for rel in cfg["relaciones"]:
        consulta = consulta.annotate(**{f"n_{rel}": Count(rel, distinct=True)})
    registros = list(consulta)
    for registro in registros:
        registro.en_uso = sum(getattr(registro, f"n_{rel}") for rel in cfg["relaciones"])

    return render(request, "catalog/catalogo.html", {
        "registros": registros,
        "titulo": cfg["titulo"],
        "singular": cfg["singular"],
        "descripcion": cfg["descripcion"],
        "url_lista": f"lista_{clave}",
        "url_editar": f"editar_{clave}",
        "url_eliminar": f"eliminar_{clave}",
    })


@admin_required
@require_POST
def editar(request, clave, pk):
    cfg = CATALOGOS[clave]
    registro = get_object_or_404(cfg["modelo"], pk=pk)
    form = cfg["form"](request.POST, instance=registro)
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
    registro = get_object_or_404(cfg["modelo"], pk=pk)
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