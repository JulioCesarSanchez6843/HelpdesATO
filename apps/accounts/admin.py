from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.shortcuts import redirect

from .models import SolicitudCambioPassword, Usuario

class SucursalObligatoriaMixin:
    def clean(self):
        datos = super().clean()
        es_superior = (
            datos.get("rol") == Usuario.Rol.SUPERADMIN
            or datos.get("is_superuser", self.instance.is_superuser)
        )
        if not es_superior and datos.get("activo", True) and not datos.get("sucursal"):
            self.add_error("sucursal", "Selecciona la sucursal del usuario.")
        return datos


class UsuarioAdminCreationForm(SucursalObligatoriaMixin, UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = Usuario
        fields = ("correo", "nombre")
        field_classes = {}


class UsuarioAdminChangeForm(SucursalObligatoriaMixin, UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = Usuario

class UsuarioAdmin(UserAdmin):
    model = Usuario
    form = UsuarioAdminChangeForm
    add_form = UsuarioAdminCreationForm
    ordering = ("nombre",)
    list_display = ("nombre", "correo", "rol", "activo", "is_staff")
    list_filter = ("rol", "activo", "is_staff")
    search_fields = ("nombre", "correo")

    fieldsets = (
        (None, {"fields": ("correo", "password")}),
        ("Información personal", {"fields": ("nombre", "rol", "sucursal", "puesto", "area")}),
        ("Permisos", {"fields": ("activo", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Fechas importantes", {"fields": ("last_login",)}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("correo", "nombre", "rol", "sucursal", "area", "puesto", "password1", "password2"),
        }),
    )

    filter_horizontal = ("groups", "user_permissions")

    def user_change_password(self, request, id, form_url=""):
        """Las contraseñas no se cambian desde /admin/: se hace en «Usuarios»
        de la aplicación, donde aplican las reglas (usuarios: un administrador;
        administradores: con autorización por correo del propio administrador)."""
        messages.error(
            request,
            "Las contraseñas no se cambian desde aquí. Usa la sección «Usuarios» "
            "de la aplicación.",
        )
        return redirect("admin:accounts_usuario_change", id)


admin.site.register(Usuario, UsuarioAdmin)


@admin.register(SolicitudCambioPassword)
class SolicitudCambioPasswordAdmin(admin.ModelAdmin):
    """Solo consulta: sirve para ver quién pidió cambiar qué contraseña."""

    list_display = ("usuario", "solicitante", "estado", "creada_en", "resuelta_en")
    list_filter = ("estado",)
    exclude = ("password_hash",)
    readonly_fields = ("usuario", "solicitante", "estado", "creada_en", "resuelta_en")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False