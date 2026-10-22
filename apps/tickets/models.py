from django.conf import settings
from django.db import models
from django.utils import timezone


class Ticket(models.Model):
    class Estado(models.TextChoices):
        ABIERTO = "ABIERTO", "Abierto"
        EN_PROCESO = "EN_PROCESO", "En proceso"
        POR_CONFIRMAR = "POR_CONFIRMAR", "Por confirmar"
        CERRADO = "CERRADO", "Cerrado"

    titulo = models.CharField(max_length=150)
    descripcion = models.TextField()

    numero_serie = models.CharField(
        "Número de serie / Service Tag", max_length=50, blank=True
    )

    area = models.ForeignKey(
        "catalog.Area",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="tickets",
    )

    sucursal = models.ForeignKey(
        "catalog.Sucursal",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="tickets",
    )

    asignado_a = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tickets_asignados",
    )

    categoria = models.ForeignKey(
        "catalog.Categoria",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tickets",
    )

    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.ABIERTO,
    )

    nota_resolucion = models.TextField(blank=True)

    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tickets_creados",
    )

    creado_en = models.DateTimeField(auto_now_add=True)
    resuelto_en = models.DateTimeField(null=True, blank=True)
    cerrado_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-creado_en"]

    def __str__(self):
        return f"Ticket #{self.pk} - {self.titulo}"

    @property
    def esperando_confirmacion(self):
        return self.estado == self.Estado.POR_CONFIRMAR


class AdjuntoTicket(models.Model):
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name="adjuntos",
    )
    nombre = models.CharField(max_length=150)
    tipo_contenido = models.CharField(max_length=50)
    contenido = models.BinaryField()
    tamano = models.PositiveIntegerField(default=0)
    subido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="+",
    )
    subido_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        verbose_name = "Adjunto"
        verbose_name_plural = "Adjuntos"

    def __str__(self):
        return f"{self.nombre} (ticket #{self.ticket_id})"


class Historial(models.Model):
    class Tipo(models.TextChoices):
        CREACION = "CREACION", "Creación"
        CAMBIO_ESTADO = "CAMBIO_ESTADO", "Cambio de estado"
        CATEGORIA = "CATEGORIA", "Cambio de categoría"
        ASIGNACION = "ASIGNACION", "Asignación"

    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name="historial",
    )

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )

    tipo = models.CharField(
        max_length=15,
        choices=Tipo.choices,
        default=Tipo.CAMBIO_ESTADO,
    )

    contenido = models.TextField()

    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["fecha", "id"]
        verbose_name_plural = "Historial"

    def __str__(self):
        return (
            f"{self.get_tipo_display()} "
            f"en Ticket #{self.ticket_id} "
            f"por {self.usuario}"
        )


class Notificacion(models.Model):
    class Tipo(models.TextChoices):
        NUEVO_TICKET = "NUEVO_TICKET", "Nuevo ticket"
        CAMBIO_ESTADO = "CAMBIO_ESTADO", "Cambio de estado"
        POR_CONFIRMAR = "POR_CONFIRMAR", "Cierre por confirmar"
        TICKET_CERRADO = "TICKET_CERRADO", "Ticket cerrado"
        CIERRE_RECHAZADO = "CIERRE_RECHAZADO", "Cierre rechazado"
        TICKET_ASIGNADO = "TICKET_ASIGNADO", "Ticket asignado"

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notificaciones",
    )

    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    tipo = models.CharField(
        max_length=20,
        choices=Tipo.choices,
    )

    mensaje = models.TextField()

    leida = models.BooleanField(default=False)

    creada_en = models.DateTimeField(auto_now_add=True)

    leida_en = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-creada_en", "-id"]
        verbose_name_plural = "Notificaciones"

    def __str__(self):
        return f"{self.get_tipo_display()} para {self.usuario}"

    def marcar_leida(self):
        if not self.leida:
            self.leida = True
            self.leida_en = timezone.now()
            self.save(update_fields=["leida", "leida_en"])