from .models import PreferenciasUsuario


def preferencias(request):
    return {"prefs": PreferenciasUsuario.de(getattr(request, "user", None))}