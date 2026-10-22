from apps.accounts.models import FotoPerfil


def notificaciones(request):
    if request.user.is_authenticated:
        actualizada = (
            FotoPerfil.objects.filter(usuario=request.user)
            .values_list("actualizada_en", flat=True)
            .first()
        )
        return {
            "notificaciones_sin_leer": request.user.notificaciones.filter(leida=False).count(),
            "foto_version": int(actualizada.timestamp()) if actualizada else None,
        }
    return {}