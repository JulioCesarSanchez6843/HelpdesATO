from io import BytesIO

from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone
from PIL import Image, ImageOps

from apps.accounts.forms import BootstrapFormMixin
from .models import Area, Categoria, Puesto, Sucursal

def _quitar_fondo_blanco(imagen):
    datos = imagen.tobytes()
    opacos = blancos = 0
    for i in range(0, len(datos), 4):
        if datos[i + 3] > 200:
            opacos += 1
            if min(datos[i], datos[i + 1], datos[i + 2]) >= 235:
                blancos += 1
    if not opacos or blancos / opacos < 0.3:
        return imagen
    salida = bytearray(datos)
    for i in range(0, len(datos), 4):
        t = min(max((min(datos[i], datos[i + 1], datos[i + 2]) - 190) / 60, 0.0), 1.0)
        if t == 0.0:
            continue
        if t == 1.0:
            salida[i:i + 4] = b"\xff\xff\xff\x00"
            continue
        k = 1.0 - t
        for c in range(3):
            salida[i + c] = min(255, max(0, round((datos[i + c] - 255 * t) / k)))
        salida[i + 3] = round(datos[i + 3] * k)
    return Image.frombytes("RGBA", imagen.size, bytes(salida))

def _quitar_fondo_blanco(imagen):
    datos = imagen.tobytes()
    opacos = blancos = 0
    for i in range(0, len(datos), 4):
        if datos[i + 3] > 200:
            opacos += 1
            if min(datos[i], datos[i + 1], datos[i + 2]) >= 235:
                blancos += 1
    if not opacos or blancos / opacos < 0.3:
        return imagen
    salida = bytearray(datos)
    for i in range(0, len(datos), 4):
        t = min(max((min(datos[i], datos[i + 1], datos[i + 2]) - 190) / 60, 0.0), 1.0)
        if t == 0.0:
            continue
        if t == 1.0:
            salida[i:i + 4] = b"\xff\xff\xff\x00"
            continue
        k = 1.0 - t
        for c in range(3):
            salida[i + c] = min(255, max(0, round((datos[i + c] - 255 * t) / k)))
        salida[i + 3] = round(datos[i + 3] * k)
    return Image.frombytes("RGBA", imagen.size, bytes(salida))

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
            queryset=Sucursal.objects.filter(activa=True),
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
        label="Logo de la sucursal",
        required=False,
        widget=forms.FileInput(attrs={"accept": "image/jpeg,image/png", "class": "d-none"}),
    )
    quitar_logo = forms.BooleanField(required=False, widget=forms.HiddenInput())
    field_order = ["nombre", "codigo_distribuidor", "color_barra", "color_primario", "logo_archivo", "quitar_logo"]

    class Meta:
        model = Sucursal
        fields = ["nombre", "codigo_distribuidor", "color_barra", "color_primario"]
        labels = {
            "color_barra": "Color de la barra",
            "color_primario": "Color de iconos y botones",
        }
        help_texts = {
            "color_barra": "Fondo de la barra superior y del menú lateral.",
            "color_primario": "Iconos, botones y detalles de la interfaz.",
        }
        widgets = {
            "codigo_distribuidor": forms.TextInput(attrs={
                "maxlength": "3",
                "inputmode": "numeric",
                "pattern": "[0-9]{3}",
                "placeholder": "Ej. 001",
            }),
            "color_barra": forms.TextInput(attrs={"type": "color", "class": "form-control-color"}),
            "color_primario": forms.TextInput(attrs={"type": "color", "class": "form-control-color"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["codigo_distribuidor"].required = True

    def clean_codigo_distribuidor(self):
        codigo = (self.cleaned_data.get("codigo_distribuidor") or "").strip()
        repetidos = Sucursal.objects.filter(codigo_distribuidor=codigo)
        if self.instance.pk:
            repetidos = repetidos.exclude(pk=self.instance.pk)
        if repetidos.exists():
            raise ValidationError("Ya existe una sucursal con ese código.")
        return codigo

    def clean_logo_archivo(self):
        archivo = self.cleaned_data.get("logo_archivo")
        if not archivo:
            return None
        if archivo.size > 5 * 1024 * 1024:
            raise ValidationError("La imagen no puede pesar más de 5 MB.")
        try:
            archivo.seek(0)
            imagen = ImageOps.exif_transpose(Image.open(archivo)).convert("RGBA")
            imagen.thumbnail((600, 240), Image.LANCZOS)
            imagen = _quitar_fondo_blanco(imagen)
            imagen = _quitar_fondo_blanco(imagen)
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