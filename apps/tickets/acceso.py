from django.conf import settings
from django.core import signing
from django.urls import reverse

from apps.accounts.models import Usuario

_SAL_ACCESO = "tickets.acceso-directo"


def url_con_acceso(usuario, ticket):
    token = signing.dumps({"u": usuario.pk, "t": ticket.pk}, salt=_SAL_ACCESO)
    return settings.SITE_URL + reverse("acceso_directo", args=[token])


def datos_desde_token(token):
    try:
        datos = signing.loads(
            token, salt=_SAL_ACCESO, max_age=settings.ACCESO_TOKEN_MAX_AGE
        )
    except signing.BadSignature:
        return None, None

    usuario = Usuario.objects.filter(pk=datos.get("u"), activo=True).first()
    return usuario, datos.get("t")