from django.shortcuts import redirect
from django.urls import reverse


class CambioPasswordObligatorioMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        usuario = request.user
        if usuario.is_authenticated and usuario.debe_cambiar_password:
            permitidas = {reverse("cambiar_password"), reverse("logout")}
            if request.path not in permitidas:
                return redirect("cambiar_password")
        return self.get_response(request)