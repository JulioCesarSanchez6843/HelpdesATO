from django.db import models


class Area(models.Model):
    """Sistemas, Contabilidad, RH, Ventas, Dirección..."""
    nombre = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Categoria(models.Model):
    """Red, Hardware, Software, Impresoras..."""
    nombre = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name_plural = "Categorías"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Puesto(models.Model):
    """Jefe, Analista, Auxiliar, Gerente..."""
    nombre = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre