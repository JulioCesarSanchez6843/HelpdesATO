from io import BytesIO

from django import forms
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.forms import SetPasswordForm
from django.core.exceptions import ValidationError
from PIL import Image, ImageOps

from apps.catalog.models import Area, Puesto, Sucursal

from .models import Usuario
from .permisos import puede_cambiar_password, roles_asignables

class BootstrapFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            widget = campo.widget
            if isinstance(widget, forms.CheckboxInput):
                clase = "form-check-input"
            elif isinstance(widget, forms.Select):
                clase = "form-select"
            else:
                clase = "form-control"
            widget.attrs["class"] = f'{widget.attrs.get("class", "")} {clase}'.strip()


class _UsuarioBaseForm(BootstrapFormMixin, forms.ModelForm):
    password1 = forms.CharField(
        label="Contraseña", strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    password2 = forms.CharField(
        label="Confirmar contraseña", strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    def __init__(self, *args, solicitante=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.solicitante = solicitante
        self.fields["area"].required = True
        self.fields["puesto"].required = False
        self.fields["sucursal"].required = False
        self.fields["sucursal"].queryset = Sucursal.objects.all()
        self.fields["correo"].required = True
        self.fields["correo"].error_messages["required"] = "El correo es obligatorio."
        self.fields["correo"].error_messages["invalid"] = "Escribe un correo válido, por ejemplo nombre@empresa.com."
        self._limitar_al_solicitante()

    def _limitar_al_solicitante(self):
        solicitante = self.solicitante
        if solicitante is None:
            return
        permitidos = set(roles_asignables(solicitante))
        if self.instance.pk:
            permitidos.add(self.instance.rol)
        self.fields["rol"].choices = [
            (valor, etiqueta)
            for valor, etiqueta in Usuario.Rol.choices
            if valor in permitidos
        ]
        self.fields["area"].queryset = Area.objects.visibles_para(solicitante)
        self.fields["puesto"].queryset = Puesto.objects.visibles_para(solicitante)
        if solicitante.es_superadmin:
            return
        self.fields["sucursal"].queryset = Sucursal.objects.filter(pk=solicitante.sucursal_id)
        self.fields["sucursal"].initial = solicitante.sucursal_id
        self.fields["sucursal"].empty_label = None
        self.fields["sucursal"].required = True

    def clean_correo(self):
        correo = (self.cleaned_data.get("correo") or "").strip()
        if not correo:
            raise ValidationError("El correo es obligatorio.")
        repetidos = Usuario.objects.filter(correo__iexact=correo)
        if self.instance.pk:
            repetidos = repetidos.exclude(pk=self.instance.pk)
        if repetidos.exists():
            raise ValidationError("Ya existe un usuario con ese correo.")
        return correo

    def clean(self):
        datos = super().clean()
        p1, p2 = datos.get("password1"), datos.get("password2")
        if p1 or p2:
            if p1 != p2:
                self.add_error("password2", "Las contraseñas no coinciden.")
            else:
                try:
                    validate_password(p1, self.instance)
                except ValidationError as error:
                    self.add_error("password1", error)
        rol = datos.get("rol")
        es_superior = rol == Usuario.Rol.SUPERADMIN or self.instance.is_superuser
        if not es_superior and not datos.get("sucursal"):
            self.add_error("sucursal", "Selecciona la sucursal del usuario.")
        sucursal = datos.get("sucursal")
        for campo in ("area", "puesto"):
            registro = datos.get(campo)
            if (
                registro
                and registro.sucursal_id
                and sucursal
                and registro.sucursal_id != sucursal.pk
            ):
                self.add_error(campo, "Ese registro pertenece a otra sucursal.")
        return datos


class UsuarioCrearForm(_UsuarioBaseForm):
    class Meta:
        model = Usuario
        fields = ["nombre", "correo", "rol", "sucursal", "area", "puesto"]
        labels = {"area": "Área", "sucursal": "Sucursal"}
        help_texts = {
            "correo": "Con este correo inicia sesión y aquí recibe los avisos de los tickets.",
        }

    def save(self, commit=True):
        usuario = super().save(commit=False)
        usuario.set_password(self.cleaned_data["password1"])
        if commit:
            usuario.save()
        return usuario


class UsuarioEditarForm(_UsuarioBaseForm):
    class Meta:
        model = Usuario
        fields = ["nombre", "correo", "rol", "sucursal", "area", "puesto", "activo"]
        labels = {"area": "Área", "sucursal": "Sucursal"}
        help_texts = {
            "correo": "Con este correo inicia sesión y aquí recibe los avisos de los tickets.",
        }

    def __init__(self, *args, editando_a_si_mismo=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.editando_a_si_mismo = editando_a_si_mismo
        self.nueva_password = None

        if editando_a_si_mismo:
            self.fields["rol"].disabled = True
            self.fields["activo"].disabled = True
            del self.fields["password1"]
            del self.fields["password2"]
        elif not puede_cambiar_password(self.solicitante, self.instance):
            del self.fields["password1"]
            del self.fields["password2"]
        else:
            self.fields["password1"].required = False
            self.fields["password2"].required = False
            self.fields["password1"].label = "Nueva contraseña"
            self.fields["password1"].help_text = "Déjala vacía para conservar la actual."

    def save(self, commit=True):
        usuario = super().save(commit=False)
        self.nueva_password = self.cleaned_data.get("password1") or None
        if commit:
            usuario.save()
        return usuario

class FotoPerfilForm(BootstrapFormMixin, forms.Form):
    foto = forms.ImageField(
        label="Nueva foto",
        help_text="JPG o PNG, máximo 10 MB. Se recorta en cuadrado.",
        widget=forms.ClearableFileInput(attrs={"accept": "image/jpeg,image/png"}),
    )

    def clean_foto(self):
        archivo = self.cleaned_data["foto"]
        if archivo.size > 5 * 1024 * 1024:
            raise ValidationError("La imagen no puede pesar más de 5 MB.")
        try:
            archivo.seek(0)
            imagen = Image.open(archivo)
            imagen = ImageOps.exif_transpose(imagen).convert("RGBA")
            fondo = Image.new("RGB", imagen.size, (255, 255, 255))
            fondo.paste(imagen, mask=imagen.getchannel("A"))
            fondo = ImageOps.fit(fondo, (256, 256), Image.LANCZOS)
            salida = BytesIO()
            fondo.save(salida, format="JPEG", quality=85, optimize=True)
        except Exception:
            raise ValidationError("No se pudo procesar la imagen.")
        return salida.getvalue()

class CambiarPasswordForm(BootstrapFormMixin, SetPasswordForm):
    def clean_new_password1(self):
        nueva = self.cleaned_data.get("new_password1")
        if nueva and self.user.check_password(nueva):
            raise ValidationError("La nueva contraseña debe ser diferente a la actual.")
        return nueva