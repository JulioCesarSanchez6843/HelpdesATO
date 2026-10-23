from django.urls import path

from . import views

urlpatterns = [
    path("", views.lista, name="actividad"),
    path("exportar/", views.exportar, name="exportar_actividad"),
]