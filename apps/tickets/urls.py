from django.urls import path

from . import views


urlpatterns = [
    path("", views.lista_tickets, name="lista_tickets"),

    path("nuevo/", views.nuevo_ticket, name="nuevo_ticket"),

    path("adjuntos/<int:pk>/", views.ver_adjunto, name="ver_adjunto"),

    path("<int:pk>/", views.detalle_ticket, name="detalle_ticket"),
]