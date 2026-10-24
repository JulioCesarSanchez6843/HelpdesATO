from django.urls import path

from . import views

urlpatterns = []
for clave in views.CATALOGOS:
    urlpatterns += [
        path(f"{clave}/", views.lista, {"clave": clave}, name=f"lista_{clave}"),
        path(f"{clave}/<int:pk>/editar/", views.editar, {"clave": clave}, name=f"editar_{clave}"),
        path(f"{clave}/<int:pk>/eliminar/", views.eliminar, {"clave": clave}, name=f"eliminar_{clave}"),
    ]

urlpatterns += [
    path("sucursales/", views.lista_sucursales, name="lista_sucursales"),
    path("sucursales/nueva/", views.nueva_sucursal, name="nueva_sucursal"),
    path("sucursales/<int:pk>/editar/", views.editar_sucursal, name="editar_sucursal"),
    path("sucursales/<int:pk>/eliminar/", views.eliminar_sucursal, name="eliminar_sucursal"),
    path("sucursales/<int:pk>/logo/", views.logo_sucursal, name="logo_sucursal"),
]