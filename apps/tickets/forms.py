from django import forms
from django.conf import settings

from apps.accounts.forms import BootstrapFormMixin
from .models import Ticket


class MultipleFileInput(forms.FileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        if not data:
            return []
        archivos = [a for a in (data if isinstance(data, (list, tuple)) else [data]) if a]

        maximo = settings.ADJUNTOS_MAX_ARCHIVOS
        if len(archivos) > maximo:
            raise forms.ValidationError(f"Puedes adjuntar máximo {maximo} imágenes.")

        limpios = []
        for archivo in archivos:
            if archivo.size > settings.ADJUNTOS_MAX_MB * 1024 * 1024:
                raise forms.ValidationError(
                    f"«{archivo.name}» pesa más de {settings.ADJUNTOS_MAX_MB} MB."
                )
            limpios.append(super().clean(archivo, initial))
        return limpios


class TicketForm(BootstrapFormMixin, forms.ModelForm):
    imagenes = MultipleImageField(
        label="Imágenes o fotos (opcional)",
        required=False,
        help_text=(
            f"Hasta {settings.ADJUNTOS_MAX_ARCHIVOS} imágenes de "
            f"{settings.ADJUNTOS_MAX_MB} MB cada una. Desde el celular puedes tomar la foto."
        ),
    )

    class Meta:
        model = Ticket
        fields = ["titulo", "descripcion"]
        labels = {
            "titulo": "Título",
            "descripcion": "Descripción",
        }
        widgets = {
            "descripcion": forms.Textarea(attrs={"rows": 5}),
        }