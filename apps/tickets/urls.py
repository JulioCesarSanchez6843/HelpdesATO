from django.urls import path

from . import views


urlpatterns = [
    path("", views.lista_tickets, name="lista_tickets"),

    path("nuevo/", views.nuevo_ticket, name="nuevo_ticket"),

    path("adjuntos/<int:pk>/", views.ver_adjunto, name="ver_adjunto"),

    path("confirmar/<str:token>/", views.confirmar_cierre, name="confirmar_cierre"),

    path("notificaciones/", views.lista_notificaciones, name="lista_notificaciones"),

    path(
        "notificaciones/leer-todas/",
        views.notificaciones_leer_todas,
        name="notificaciones_leer_todas",
    ),

    path(
        "notificaciones/<int:pk>/abrir/",
        views.abrir_notificacion,
        name="abrir_notificacion",
    ),

    path(
        "notificaciones/<int:pk>/leer/",
        views.marcar_notificacion_leida,
        name="marcar_notificacion_leida",
    ),

    path("<int:pk>/", views.detalle_ticket, name="detalle_ticket"),

    path("<int:pk>/responder-cierre/", views.responder_cierre, name="responder_cierre"),

    path("<int:pk>/forzar-cierre/", views.forzar_cierre, name="forzar_cierre"),
]