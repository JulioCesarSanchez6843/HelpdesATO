from django import forms
from django.core.exceptions import ValidationError

from apps.accounts.forms import BootstrapFormMixin
from .models import Area, Categoria, Puesto, Sucursal


class _CatalogoForm(BootstrapFormMixin, forms.ModelForm):
    def clean_nombre(self):
        nombre = " ".join(self.cleaned_data["nombre"].split())
        repetidos = self._meta.model.objects.filter(nombre__iexact=nombre)
        if self.instance.pk:
            repetidos = repetidos.exclude(pk=self.instance.pk)
        if repetidos.exists():
            raise ValidationError("Ya existe un registro con ese nombre.")
        return nombre


class AreaForm(_CatalogoForm):
    class Meta:
        model = Area
        fields = ["nombre"]


class CategoriaForm(_CatalogoForm):
    class Meta:
        model = Categoria
        fields = ["nombre"]


class PuestoForm(_CatalogoForm):
    class Meta:
        model = Puesto
        fields = ["nombre"]

class SucursalForm(_CatalogoForm):
    class Meta:
        model = Sucursal
        fields = ["nombre"]