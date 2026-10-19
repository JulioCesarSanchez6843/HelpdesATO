from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import Usuario


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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["area"].required = False
        self.fields["puesto"].required = False
        self.fields["correo"].required = True
        self.fields["correo"].error_messages["required"] = "El correo es obligatorio."
        self.fields["correo"].error_messages["invalid"] = "Escribe un correo válido, por ejemplo nombre@empresa.com."

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
        return datos


class UsuarioCrearForm(_UsuarioBaseForm):
    class Meta:
        model = Usuario
        fields = ["nombre", "correo", "rol", "area", "puesto"]
        labels = {"area": "Área"}
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
        fields = ["nombre", "correo", "rol", "area", "puesto", "activo"]
        labels = {"area": "Área"}
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
        elif self.instance.es_admin:
            self.fields["rol"].disabled = True
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