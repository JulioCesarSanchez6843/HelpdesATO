from django.urls import path
from django.views.generic import RedirectView

from . import views

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="lista_tickets", permanent=False)),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("cambiar-password/", views.cambiar_password, name="cambiar_password"),
    path("usuarios/", views.lista_usuarios, name="lista_usuarios"),
    path("usuarios/nuevo/", views.nuevo_usuario, name="nuevo_usuario"),
    path("usuarios/<int:pk>/editar/", views.editar_usuario, name="editar_usuario"),
    path("usuarios/<int:pk>/estado/", views.cambiar_estado_usuario, name="cambiar_estado_usuario"),
    path("perfil/", views.mi_perfil, name="mi_perfil"),
    path("perfil/solicitar-password/", views.solicitar_cambio_password, name="solicitar_cambio_password"),
    path("perfil/foto/<int:pk>/", views.foto_usuario, name="foto_usuario"),
]