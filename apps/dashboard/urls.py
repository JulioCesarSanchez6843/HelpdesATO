from django.urls import path
from . import views

urlpatterns = [
    path("", views.reportes, name="reportes"),
    path("exportar/resueltos/", views.exportar_resueltos, name="exportar_resueltos"),
]