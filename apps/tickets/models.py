from django.conf import settings
from django.db import models
from django.utils import timezone


class Ticket(models.Model):
    class Estado(models.TextChoices):
        ABIERTO = "ABIERTO", "Abierto"
        EN_PROCESO = "EN_PROCESO", "En proceso"
        EN_ESPERA = "EN_ESPERA", "En espera de materiales"
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

    resuelto_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tickets_resueltos",
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
    justificacion_cierre = models.TextField(blank=True)

    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="tickets_creados",
    )

    creado_en = models.DateTimeField(auto_now_add=True)
    primera_respuesta_en = models.DateTimeField(null=True, blank=True)
    resuelto_en = models.DateTimeField(null=True, blank=True)
    cerrado_en = models.DateTimeField(null=True, blank=True)
    recordatorio_cierre_en = models.DateTimeField(null=True, blank=True)

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
        on_delete=models.PROTECT,
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
        on_delete=models.PROTECT,
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
        SOLICITUD_PASSWORD = "SOLICITUD_PASSWORD", "Solicitud de contraseña"
        COMENTARIO = "COMENTARIO", "Nuevo comentario"
        ESPERA_MATERIALES = "ESPERA_MATERIALES", "En espera de materiales"

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

class Comentario(models.Model):
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name="comentarios",
    )
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
    )
    contenido = models.TextField()
    interno = models.BooleanField(default=False)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["creado_en", "id"]
        verbose_name_plural = "Comentarios"

    def __str__(self):
        return f"Comentario de {self.autor} en ticket #{self.ticket_id}"

class ConfiguracionSistema(models.Model):
    cierre_automatico_activo = models.BooleanField(default=False)
    cierre_automatico_dias = models.PositiveSmallIntegerField(default=7)
    recordatorio_activo = models.BooleanField(default=True)
    recordatorio_dias_antes = models.PositiveSmallIntegerField(default=2)
    ultima_ejecucion = models.DateTimeField(null=True, blank=True)
    ultima_ejecucion_cerrados = models.PositiveIntegerField(default=0)
    ultima_ejecucion_recordatorios = models.PositiveIntegerField(default=0)
    ultima_ejecucion_errores = models.PositiveIntegerField(default=0)
    actualizado_en = models.DateTimeField(null=True, blank=True)
    actualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        verbose_name = "Configuración del sistema"
        verbose_name_plural = "Configuración del sistema"

    def __str__(self):
        return "Configuración del sistema"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def actual(cls):
        configuracion, _ = cls.objects.get_or_create(pk=1)
        return configuracion

class CorreoPendiente(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        ENVIADO = "ENVIADO", "Enviado"
        ERROR = "ERROR", "Error"

    destinatarios = models.CharField(max_length=500)
    asunto = models.CharField(max_length=250)
    contenido = models.BinaryField()
    estado = models.CharField(
        max_length=10, choices=Estado.choices, default=Estado.PENDIENTE
    )
    intentos = models.PositiveSmallIntegerField(default=0)
    error = models.CharField(max_length=500, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    proximo_intento = models.DateTimeField(default=timezone.now)
    enviado_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["id"]
        verbose_name = "Correo pendiente"
        verbose_name_plural = "Cola de correos"
        indexes = [models.Index(fields=["estado", "proximo_intento"])]

    def __str__(self):
        return f"{self.asunto} → {self.destinatarios} ({self.get_estado_display()})"