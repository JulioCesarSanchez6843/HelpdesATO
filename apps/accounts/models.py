from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.db.models.functions import Lower


class UsuarioManager(BaseUserManager):
    """Manager personalizado: Django necesita este código para saber
    cómo crear usuarios normales y superusuarios usando 'correo' en vez
    de 'username'."""

    def get_by_natural_key(self, correo):
        # El login no distingue mayúsculas/minúsculas en el correo.
        return self.get(correo__iexact=correo)

    def create_user(self, correo, nombre, password=None, **extra_fields):
        correo = (correo or "").strip()
        if not correo:
            raise ValueError("El correo es obligatorio")
        correo = self.normalize_email(correo)
        usuario = self.model(correo=correo, nombre=nombre, **extra_fields)
        usuario.set_password(password)
        usuario.save(using=self._db)
        return usuario

    def create_superuser(self, correo, nombre, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("rol", "SUPERADMIN")
        return self.create_user(correo, nombre, password, **extra_fields)


class Usuario(AbstractBaseUser, PermissionsMixin):
    class Rol(models.TextChoices):
        SUPERADMIN = "SUPERADMIN", "Super administrador"
        ENCARGADO = "ENCARGADO", "Encargado"
        BECARIO = "BECARIO", "Becario"
        USUARIO = "USUARIO", "Usuario"

    nombre = models.CharField(max_length=150)
    correo = models.EmailField(unique=True)
    rol = models.CharField(max_length=12, choices=Rol.choices, default=Rol.USUARIO)
    puesto = models.ForeignKey(
        "catalog.Puesto", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="usuarios"
    )
    area = models.ForeignKey(
        "catalog.Area", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="usuarios"
    )
    sucursal = models.ForeignKey(
        "catalog.Sucursal", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="usuarios"
    )
    activo = models.BooleanField(default=True)
    debe_cambiar_password = models.BooleanField(default=False)
    creado_en = models.DateTimeField(auto_now_add=True)

    is_staff = models.BooleanField(default=False)

    USERNAME_FIELD = "correo"
    REQUIRED_FIELDS = ["nombre"]

    objects = UsuarioManager()

    class Meta:
        ordering = ["nombre"]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(correo=""),
                name="usuario_correo_no_vacio",
            ),
            models.UniqueConstraint(
                Lower("correo"),
                name="usuario_correo_unico_sin_mayusculas",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(rol="SUPERADMIN")
                    | models.Q(is_superuser=True)
                    | models.Q(sucursal__isnull=False)
                    | models.Q(activo=False)
                ),
                name="usuario_sucursal_obligatoria",
            ),
        ]

    def __str__(self):
        return self.nombre

    @property
    def is_active(self):
        return self.activo

    @property
    def es_superadmin(self):
        return self.is_superuser or self.rol == self.Rol.SUPERADMIN

    @property
    def es_maestro(self):
        return self.is_superuser

    @property
    def es_encargado(self):
        return self.rol == self.Rol.ENCARGADO

    @property
    def es_becario(self):
        return self.rol == self.Rol.BECARIO

    @property
    def es_admin(self):
        return self.es_superadmin or self.es_encargado

    @property
    def es_personal(self):
        return self.es_admin or self.es_becario


class SolicitudCambioPassword(models.Model):

    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        APROBADA = "APROBADA", "Aprobada"
        RECHAZADA = "RECHAZADA", "Rechazada"
        REEMPLAZADA = "REEMPLAZADA", "Reemplazada por otra solicitud"

    # El administrador al que le quieren cambiar la contraseña.
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="solicitudes_password",
    )
    # El administrador que pidió el cambio.
    solicitante = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="+",
    )
    password_hash = models.CharField(max_length=256)
    estado = models.CharField(
        max_length=12, choices=Estado.choices, default=Estado.PENDIENTE
    )
    creada_en = models.DateTimeField(auto_now_add=True)
    resuelta_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-creada_en", "-id"]
        verbose_name = "Solicitud de cambio de contraseña"
        verbose_name_plural = "Solicitudes de cambio de contraseña"
        constraints = [
            # Solo puede haber una solicitud pendiente por administrador.
            models.UniqueConstraint(
                fields=["usuario"],
                condition=models.Q(estado="PENDIENTE"),
                name="solicitud_password_una_pendiente_por_usuario",
            ),
        ]

    def __str__(self):
        return (
            f"Cambio de contraseña de {self.usuario} pedido por "
            f"{self.solicitante} ({self.get_estado_display()})"
        )
class FotoPerfil(models.Model):
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="foto_perfil",
    )
    contenido = models.BinaryField()
    actualizada_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Foto de {self.usuario}"