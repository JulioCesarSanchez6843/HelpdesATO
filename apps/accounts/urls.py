from django.urls import path

from . import views

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("panel/", views.panel_inicio, name="panel_inicio"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("cambiar-password/", views.cambiar_password, name="cambiar_password"),
    path("recuperar/", views.recuperar_password, name="recuperar_password"),
    path("restablecer/<str:uidb64>/<str:token>/", views.restablecer_password, name="restablecer_password"),
    path("usuarios/", views.lista_usuarios, name="lista_usuarios"),
    path("usuarios/nuevo/", views.nuevo_usuario, name="nuevo_usuario"),
    path("usuarios/<int:pk>/editar/", views.editar_usuario, name="editar_usuario"),
    path("usuarios/<int:pk>/estado/", views.cambiar_estado_usuario, name="cambiar_estado_usuario"),
    path("perfil/", views.mi_perfil, name="mi_perfil"),
    path("ajustes/", views.ajustes, name="ajustes"),
    path("perfil/solicitar-password/", views.solicitar_cambio_password, name="solicitar_cambio_password"),
    path("perfil/foto/<int:pk>/", views.foto_usuario, name="foto_usuario"),
]