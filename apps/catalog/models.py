from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone


class CatalogoQuerySet(models.QuerySet):
    def visibles_para(self, usuario):
        if usuario.es_superadmin:
            return self.all()
        return self.de_sucursal(usuario.sucursal_id)

    def de_sucursal(self, sucursal_id):
        return self.filter(Q(sucursal__isnull=True) | Q(sucursal_id=sucursal_id))


class CatalogoBase(models.Model):
    nombre = models.CharField(max_length=100)
    sucursal = models.ForeignKey(
        "catalog.Sucursal",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    creado_en = models.DateTimeField(default=timezone.now, editable=False)

    objects = CatalogoQuerySet.as_manager()

    class Meta:
        abstract = True
        ordering = ["nombre"]
        constraints = [
            models.UniqueConstraint(
                Lower("nombre"),
                "sucursal",
                name="%(app_label)s_%(class)s_nombre_sucursal_unico",
            ),
        ]

    def __str__(self):
        return self.nombre


class Area(CatalogoBase):
    pass


class Categoria(CatalogoBase):
    class Meta(CatalogoBase.Meta):
        verbose_name_plural = "Categorías"


class Puesto(CatalogoBase):
    pass

class Sucursal(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    codigo_distribuidor = models.CharField(
        "Código de distribuidor",
        max_length=3,
        unique=True,
        null=True,
        blank=True,
        validators=[RegexValidator(r"^\d{3}$", "Debe tener exactamente 3 dígitos.")],
    )
    color_primario = models.CharField(
        max_length=7,
        default="#c8102e",
        validators=[RegexValidator(r"^#[0-9a-fA-F]{6}$", "Color no válido.")],
    )
    color_barra = models.CharField(
        max_length=7,
        default="#2f2f2f",
        validators=[RegexValidator(r"^#[0-9a-fA-F]{6}$", "Color no válido.")],
    )
    logo = models.BinaryField(null=True, blank=True, editable=False)
    logo_actualizado_en = models.DateTimeField(null=True, blank=True, editable=False)
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "Sucursales"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre