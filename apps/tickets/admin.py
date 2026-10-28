from django.contrib import admin

from .models import AdjuntoTicket, Comentario, Historial, Notificacion, Ticket
from .models import CorreoPendiente


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "titulo",
        "estado",
        "area",
        "categoria",
        "creado_por",
        "creado_en",
        "cerrado_en",
    )

    list_filter = (
        "estado",
        "area",
        "categoria",
    )

    search_fields = (
        "titulo",
        "descripcion",
        "creado_por__nombre",
    )

    readonly_fields = (
        "creado_en",
        "resuelto_en",
        "cerrado_en",
    )


@admin.register(AdjuntoTicket)
class AdjuntoTicketAdmin(admin.ModelAdmin):
    list_display = ("id", "ticket", "nombre", "tamano", "subido_por", "subido_en")
    readonly_fields = ("tamano", "subido_en")
    exclude = ("contenido",)

    def get_queryset(self, request):
        return super().get_queryset(request).defer("contenido")


admin.site.register(Historial)
admin.site.register(Comentario)

admin.site.register(Notificacion)

@admin.register(CorreoPendiente)
class CorreoPendienteAdmin(admin.ModelAdmin):
    list_display = ("asunto", "destinatarios", "estado", "intentos", "creado_en", "enviado_en")
    list_filter = ("estado",)
    search_fields = ("asunto", "destinatarios")
    readonly_fields = ("contenido",)