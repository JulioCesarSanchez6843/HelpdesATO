from django.urls import path

from . import views

urlpatterns = []
for clave in views.CATALOGOS:
    urlpatterns += [
        path(f"{clave}/", views.lista, {"clave": clave}, name=f"lista_{clave}"),
        path(f"{clave}/<int:pk>/editar/", views.editar, {"clave": clave}, name=f"editar_{clave}"),
        path(f"{clave}/<int:pk>/eliminar/", views.eliminar, {"clave": clave}, name=f"eliminar_{clave}"),
    ]