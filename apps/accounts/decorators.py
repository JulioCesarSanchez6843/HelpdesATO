from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


def admin_required(view_func):

    @login_required
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.es_admin:
            messages.error(request, "No tienes permiso para acceder a esa sección.")
            return redirect("lista_tickets")
        return view_func(request, *args, **kwargs)

    return _wrapped

def superadmin_required(view_func):

    @login_required
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.es_superadmin:
            messages.error(request, "No tienes permiso para acceder a esa sección.")
            return redirect("lista_tickets")
        return view_func(request, *args, **kwargs)

    return _wrapped