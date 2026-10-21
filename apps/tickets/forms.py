from django import forms
from django.conf import settings
from django.utils import timezone

from apps.accounts.forms import BootstrapFormMixin
from .models import Ticket


class MultipleFileInput(forms.FileInput):
    allow_multiple_selected = True


EXTENSIONES_PERMITIDAS = (".jpg", ".jpeg", ".png")
TIPOS_PERMITIDOS = ("image/jpeg", "image/png")


class MultipleImageField(forms.ImageField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        if not data:
            return []
        archivos = [a for a in (data if isinstance(data, (list, tuple)) else [data]) if a]

        maximo = settings.ADJUNTOS_MAX_ARCHIVOS
        if len(archivos) > maximo:
            raise forms.ValidationError(f"Puedes adjuntar máximo {maximo} imágenes.")

        limite = settings.ADJUNTOS_MAX_MB * 1024 * 1024
        limpios = []
        errores = []

        for archivo in archivos:
            if not archivo.name.lower().endswith(EXTENSIONES_PERMITIDAS):
                errores.append(f"«{archivo.name}»: solo se permiten imágenes JPG o PNG.")
                continue

            if archivo.size > limite:
                errores.append(
                    f"«{archivo.name}» pesa más de {settings.ADJUNTOS_MAX_MB} MB."
                )
                continue

            try:
                limpio = super().clean(archivo, initial)
            except forms.ValidationError:
                errores.append(f"«{archivo.name}» no es una imagen válida.")
                continue

            if getattr(limpio, "content_type", None) not in TIPOS_PERMITIDOS:
                errores.append(f"«{archivo.name}»: solo se permiten imágenes JPG o PNG.")
                continue

            limpios.append(limpio)

        if errores:
            raise forms.ValidationError(errores)

        return limpios

class TicketForm(BootstrapFormMixin, forms.ModelForm):
    imagenes = MultipleImageField(
        label="Imágenes o fotos (opcional)",
        required=False,
        widget=MultipleFileInput(
            attrs={
                "accept": ".jpg,.jpeg,.png,image/jpeg,image/png",
                "data-max-mb": settings.ADJUNTOS_MAX_MB,
                "data-max-files": settings.ADJUNTOS_MAX_ARCHIVOS,
            }
        ),
        help_text=(
            f"Solo JPG o PNG. Hasta {settings.ADJUNTOS_MAX_ARCHIVOS} imágenes de "
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

class TicketGestionForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Ticket
        fields = [
            "estado",
            "categoria",
            "numero_serie",
            "nota_resolucion",
        ]
        labels = {
            "estado": "Estado",
            "categoria": "Categoría",
            "numero_serie": "Número de serie / Service Tag",
            "nota_resolucion": "Nota de resolución",
        }
        help_texts = {
            "estado": (
                "«Por confirmar» le envía un correo al usuario para que confirme "
                "que se resolvió; el ticket se cierra cuando él lo confirma."
            ),
            "numero_serie": (
                "Es el mismo dato: el número de serie del equipo o, en equipos "
                "Dell, su Service Tag."
            ),
            "nota_resolucion": (
                "Obligatoria al marcar «Por confirmar». "
                "Si el ticket se vuelve a abrir, se borra."
            ),
        }
        widgets = {
            "nota_resolucion": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["categoria"].required = False
        self.estado_original = self.instance.estado

        permitidos = {
            Ticket.Estado.ABIERTO,
            Ticket.Estado.EN_PROCESO,
            Ticket.Estado.POR_CONFIRMAR,
        }
        if self.estado_original == Ticket.Estado.CERRADO:
            permitidos.add(Ticket.Estado.CERRADO)
        self.fields["estado"].choices = [
            (valor, etiqueta)
            for valor, etiqueta in Ticket.Estado.choices
            if valor in permitidos
        ]

    def clean(self):
        datos = super().clean()
        estado = datos.get("estado")
        nota = (datos.get("nota_resolucion") or "").strip()

        if estado == Ticket.Estado.CERRADO and self.estado_original != Ticket.Estado.CERRADO:
            self.add_error(
                "estado",
                "El ticket se cierra cuando el usuario confirma. "
                "Usa «Por confirmar» para pedirle la confirmación.",
            )

        if estado == Ticket.Estado.POR_CONFIRMAR and not nota:
            self.add_error(
                "nota_resolucion",
                "Escribe la nota de resolución para pedirle la confirmación al usuario.",
            )

        resuelto = estado in (Ticket.Estado.POR_CONFIRMAR, Ticket.Estado.CERRADO)
        datos["nota_resolucion"] = nota if resuelto else ""
        return datos

    def save(self, commit=True):
        ticket = super().save(commit=False)

        if ticket.estado == Ticket.Estado.POR_CONFIRMAR:
            if self.estado_original != Ticket.Estado.POR_CONFIRMAR:
                ticket.resuelto_en = timezone.now()
            ticket.cerrado_en = None
        elif ticket.estado != Ticket.Estado.CERRADO:
            ticket.resuelto_en = None
            ticket.cerrado_en = None

        if commit:
            ticket.save()

        return ticket