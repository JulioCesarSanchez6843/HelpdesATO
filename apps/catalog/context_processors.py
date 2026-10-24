from .colores import COLOR_BARRA_POR_DEFECTO, COLOR_POR_DEFECTO, paleta
from .models import Sucursal


def tema_sucursal(request):
    sucursal = None
    usuario = getattr(request, "user", None)
    if usuario is not None and usuario.is_authenticated and usuario.sucursal_id:
        sucursal = Sucursal.objects.defer("logo").filter(pk=usuario.sucursal_id).first()
    color = sucursal.color_primario if sucursal else COLOR_POR_DEFECTO
    barra = sucursal.color_barra if sucursal else COLOR_BARRA_POR_DEFECTO
    return {"sucursal_actual": sucursal, "tema": paleta(color, barra)}