from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q

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

class _CatalogoPorSucursalForm(_CatalogoForm):
    sucursal_destino = forms.ModelChoiceField(
        label="Sucursal",
        queryset=Sucursal.objects.all(),
        required=False,
        empty_label="General (todas las sucursales)",
    )

    def __init__(self, *args, solicitante, **kwargs):
        super().__init__(*args, **kwargs)
        self.solicitante = solicitante
        if self.instance.pk or not solicitante.es_superadmin:
            del self.fields["sucursal_destino"]

    def _sucursal_id(self):
        if self.instance.pk:
            return self.instance.sucursal_id
        if "sucursal_destino" in self.fields:
            valor = self.data.get("sucursal_destino", "")
            return int(valor) if valor.isdigit() else None
        return self.solicitante.sucursal_id

    def clean_nombre(self):
        nombre = " ".join(self.cleaned_data["nombre"].split())
        sucursal_id = self._sucursal_id()
        repetidos = self._meta.model.objects.filter(nombre__iexact=nombre)
        if sucursal_id is not None:
            repetidos = repetidos.filter(
                Q(sucursal__isnull=True) | Q(sucursal_id=sucursal_id)
            )
        if self.instance.pk:
            repetidos = repetidos.exclude(pk=self.instance.pk)
        if repetidos.exists():
            raise ValidationError("Ya existe un registro con ese nombre.")
        return nombre

    def save(self, commit=True):
        registro = super().save(commit=False)
        if not registro.pk:
            registro.sucursal_id = self._sucursal_id()
        if commit:
            registro.save()
        return registro

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