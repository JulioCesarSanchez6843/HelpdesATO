from django.conf import settings
from django.db import models


class Evento(models.Model):
    class Tipo(models.TextChoices):
        TICKET_CREADO = "TICKET_CREADO", "Ticket creado"
        TICKET_TOMADO = "TICKET_TOMADO", "Ticket tomado"
        TICKET_ASIGNADO = "TICKET_ASIGNADO", "Ticket asignado"
        TICKET_ESTADO = "TICKET_ESTADO", "Cambio de estado"
        TICKET_CATEGORIA = "TICKET_CATEGORIA", "Cambio de categoría"
        TICKET_RESUELTO = "TICKET_RESUELTO", "Ticket resuelto"
        TICKET_COMENTARIO = "TICKET_COMENTARIO", "Comentario en ticket"
        CIERRE_CONFIRMADO = "CIERRE_CONFIRMADO", "Cierre confirmado"
        CIERRE_RECHAZADO = "CIERRE_RECHAZADO", "Cierre rechazado"
        CIERRE_FORZADO = "CIERRE_FORZADO", "Cierre forzado"
        PASSWORD_SOLICITADO = "PASSWORD_SOLICITADO", "Solicitud de contraseña"
        PASSWORD_CAMBIADO = "PASSWORD_CAMBIADO", "Contraseña cambiada"
        PASSWORD_PROPIO = "PASSWORD_PROPIO", "Contraseña propia cambiada"
        USUARIO_CREADO = "USUARIO_CREADO", "Usuario creado"
        USUARIO_ESTADO = "USUARIO_ESTADO", "Usuario activado o desactivado"
        ROL_CAMBIADO = "ROL_CAMBIADO", "Rol cambiado"

    tipo = models.CharField(max_length=24, choices=Tipo.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    actor_nombre = models.CharField(max_length=150, blank=True)
    afectado = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    afectado_nombre = models.CharField(max_length=150, blank=True)
    ticket = models.ForeignKey(
        "tickets.Ticket",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="eventos",
    )
    ticket_numero = models.PositiveIntegerField(null=True, blank=True)
    sucursal = models.ForeignKey(
        "catalog.Sucursal",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    detalle = models.TextField(blank=True)
    creado_en = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-creado_en", "-id"]
        indexes = [models.Index(fields=["sucursal", "-creado_en"])]

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.actor_nombre}"