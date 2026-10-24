from io import BytesIO

from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone
from PIL import Image, ImageOps

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


class AreaForm(_CatalogoPorSucursalForm):
    class Meta:
        model = Area
        fields = ["nombre"]


class CategoriaForm(_CatalogoPorSucursalForm):
    class Meta:
        model = Categoria
        fields = ["nombre"]


class PuestoForm(_CatalogoPorSucursalForm):
    class Meta:
        model = Puesto
        fields = ["nombre"]


class SucursalForm(_CatalogoForm):
    logo_archivo = forms.ImageField(
        label="Icono de la sucursal",
        required=False,
        help_text="JPG o PNG, máximo 5 MB. Se recomienda una imagen cuadrada con fondo transparente.",
        widget=forms.FileInput(attrs={"accept": "image/jpeg,image/png"}),
    )
    quitar_logo = forms.BooleanField(label="Quitar el icono actual", required=False)

    class Meta:
        model = Sucursal
        fields = ["nombre", "color_primario"]
        labels = {"color_primario": "Color principal"}
        help_texts = {"color_primario": "Toda la interfaz de esta sucursal se adapta a este color."}
        widgets = {
            "color_primario": forms.TextInput(
                attrs={"type": "color", "class": "form-control-color"}
            ),
        }

    def clean_logo_archivo(self):
        archivo = self.cleaned_data.get("logo_archivo")
        if not archivo:
            return None
        if archivo.size > 5 * 1024 * 1024:
            raise ValidationError("La imagen no puede pesar más de 5 MB.")
        try:
            archivo.seek(0)
            imagen = ImageOps.exif_transpose(Image.open(archivo)).convert("RGBA")
            imagen.thumbnail((256, 256), Image.LANCZOS)
            salida = BytesIO()
            imagen.save(salida, format="PNG", optimize=True)
        except Exception:
            raise ValidationError("No se pudo procesar la imagen.")
        return salida.getvalue()

    def save(self, commit=True):
        sucursal = super().save(commit=False)
        logo = self.cleaned_data.get("logo_archivo")
        if logo:
            sucursal.logo = logo
            sucursal.logo_actualizado_en = timezone.now()
        elif self.cleaned_data.get("quitar_logo"):
            sucursal.logo = None
            sucursal.logo_actualizado_en = None
        if commit:
            sucursal.save()
        return sucursal