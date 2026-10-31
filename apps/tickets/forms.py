from django import forms
from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from apps.accounts.forms import BootstrapFormMixin
from apps.accounts.models import Usuario
from apps.catalog.models import Categoria
from .models import ConfiguracionSistema, Ticket


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
                "class": "d-none",
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
    motivo_espera = forms.CharField(
        label="Motivo de la espera",
        required=False,
        max_length=1000,
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text=(
            "Obligatorio al elegir «En espera de materiales»: explica qué falta. "
            "El solicitante lo verá en el historial."
        ),
    )

    field_order = [
        "estado",
        "prioridad",
        "motivo_espera",
        "categoria",
        "numero_serie",
        "nota_resolucion",
    ]

    class Meta:
        model = Ticket
        fields = [
            "estado",
            "prioridad",
            "categoria",
            "numero_serie",
            "nota_resolucion",
        ]
        labels = {
            "estado": "Estado",
            "prioridad": "Prioridad (SLA)",
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

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.puede_priorizar = bool(usuario and usuario.es_admin)
        if not self.puede_priorizar:
            del self.fields["prioridad"]
        self.prioridad_original = self.instance.prioridad
        self.fields["categoria"].required = False
        sucursal_id = self.instance.sucursal_id
        self.fields["categoria"].queryset = (
            Categoria.objects.de_sucursal(sucursal_id)
            if sucursal_id
            else Categoria.objects.all()
        )
        self.estado_original = self.instance.estado

        permitidos = {
            Ticket.Estado.ABIERTO,
            Ticket.Estado.EN_PROCESO,
            Ticket.Estado.EN_ESPERA,
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

        motivo = (datos.get("motivo_espera") or "").strip()
        datos["motivo_espera"] = motivo
        if (
            estado == Ticket.Estado.EN_ESPERA
            and self.estado_original != Ticket.Estado.EN_ESPERA
            and not motivo
        ):
            self.add_error(
                "motivo_espera",
                "Explica qué materiales faltan para poner el ticket en espera.",
            )

        if estado == Ticket.Estado.POR_CONFIRMAR and not nota:
            self.add_error(
                "nota_resolucion",
                "Escribe la nota de resolución para pedirle la confirmación al usuario.",
            )

        if self.puede_priorizar:
            prioridad = datos.get("prioridad")
            if (
                estado == Ticket.Estado.EN_PROCESO
                and self.estado_original != Ticket.Estado.EN_PROCESO
                and not prioridad
            ):
                self.add_error(
                    "prioridad",
                    "Elige la prioridad para pasar el ticket a «En proceso».",
                )
            if self.prioridad_original and not prioridad:
                self.add_error(
                    "prioridad",
                    "No se puede quitar la prioridad una vez definida.",
                )

        resuelto = estado in (Ticket.Estado.POR_CONFIRMAR, Ticket.Estado.CERRADO)
        datos["nota_resolucion"] = nota if resuelto else ""
        return datos

    def save(self, commit=True):
        ticket = super().save(commit=False)

        if self.puede_priorizar and ticket.prioridad != self.prioridad_original:
            ticket.recalcular_sla()

        if ticket.estado == Ticket.Estado.POR_CONFIRMAR:
            if self.estado_original != Ticket.Estado.POR_CONFIRMAR:
                ticket.resuelto_en = timezone.now()
            ticket.cerrado_en = None
        elif ticket.estado != Ticket.Estado.CERRADO:
            ticket.resuelto_en = None
            ticket.cerrado_en = None

        if ticket.estado != Ticket.Estado.CERRADO:
            ticket.justificacion_cierre = ""

        if commit:
            ticket.save()

        return ticket

class AsignarTicketForm(BootstrapFormMixin, forms.Form):
    asignado_a = forms.ModelChoiceField(
        label="Asignar a",
        queryset=Usuario.objects.none(),
        required=False,
        empty_label="Sin asignar",
    )
    prioridad = forms.ChoiceField(
        label="Prioridad (SLA)",
        choices=[("", "Elige…")] + Ticket.Prioridad.choices,
        required=True,
    )

    def __init__(self, *args, ticket, **kwargs):
        super().__init__(*args, **kwargs)
        self.ticket = ticket
        self.fields["prioridad"].initial = ticket.prioridad
        campo = self.fields["asignado_a"]
        campo.queryset = Usuario.objects.filter(
            rol__in=[Usuario.Rol.ENCARGADO, Usuario.Rol.BECARIO],
            sucursal_id=ticket.sucursal_id,
            activo=True,
        )
        campo.initial = ticket.asignado_a_id
        campo.label_from_instance = lambda u: f"{u.nombre} ({u.get_rol_display()})"

    def clean(self):
        datos = super().clean()
        if (
            datos.get("asignado_a")
            and not datos.get("prioridad")
            and not self.ticket.prioridad
        ):
            self.add_error("prioridad", "Elige la prioridad al asignar el ticket.")
        return datos

class EscalarTicketForm(BootstrapFormMixin, forms.Form):
    destino = forms.ModelChoiceField(
        label="Escalar a",
        queryset=Usuario.objects.none(),
        empty_label="Elige…",
    )
    motivo = forms.CharField(
        label="Motivo de la escalada",
        min_length=10,
        max_length=1000,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    prioridad = forms.ChoiceField(
        label="Prioridad (SLA)",
        choices=[("", "Elige…")] + Ticket.Prioridad.choices,
        required=True,
    )

    field_order = ["destino", "prioridad", "motivo"]

    def __init__(self, *args, ticket, actor, **kwargs):
        super().__init__(*args, **kwargs)
        self.ticket = ticket
        self.fields["prioridad"].initial = ticket.prioridad
        campo = self.fields["destino"]
        campo.queryset = (
            Usuario.objects.filter(activo=True)
            .filter(Q(rol=Usuario.Rol.SUPERADMIN) | Q(is_superuser=True))
            .exclude(pk=actor.pk)
            .distinct()
        )
        campo.label_from_instance = lambda u: f"{u.nombre} ({u.get_rol_display()})"

    def clean_motivo(self):
        return self.cleaned_data["motivo"].strip()

class ConfiguracionSistemaForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ConfiguracionSistema
        fields = [
            "cierre_automatico_activo",
            "cierre_automatico_dias",
            "recordatorio_activo",
            "recordatorio_dias_antes",
        ]
        labels = {
            "cierre_automatico_activo": "Cerrar automáticamente los tickets sin respuesta",
            "cierre_automatico_dias": "Días en «Por confirmar» antes de cerrar",
            "recordatorio_activo": "Avisar al usuario antes de cerrar",
            "recordatorio_dias_antes": "Días antes del cierre para avisar",
        }
        widgets = {
            "cierre_automatico_dias": forms.NumberInput(attrs={"min": 1, "max": 90}),
            "recordatorio_dias_antes": forms.NumberInput(attrs={"min": 1, "max": 30}),
        }

    def clean(self):
        datos = super().clean()
        dias = datos.get("cierre_automatico_dias")
        antes = datos.get("recordatorio_dias_antes")

        if dias is not None:
            minimo = max(1, -(-settings.CIERRE_TOKEN_MAX_AGE // 86400))
            if dias > 90:
                self.add_error("cierre_automatico_dias", "No puede ser mayor a 90 días.")
            elif dias < minimo:
                self.add_error(
                    "cierre_automatico_dias",
                    f"Debe ser de al menos {minimo} días, que es lo que dura el enlace de confirmación del correo.",
                )

        if antes is not None:
            if antes < 1 or antes > 30:
                self.add_error(
                    "recordatorio_dias_antes", "Debe estar entre 1 y 30 días."
                )
            elif (
                dias is not None
                and datos.get("recordatorio_activo")
                and antes >= dias
            ):
                self.add_error(
                    "recordatorio_dias_antes",
                    "Debe ser menor que los días para cerrar.",
                )
        return datos