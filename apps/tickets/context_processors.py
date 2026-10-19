def notificaciones(request):
    if request.user.is_authenticated:
        return {
            "notificaciones_sin_leer": request.user.notificaciones.filter(leida=False).count()
        }
    return {}