import os
from io import BytesIO

from PIL import Image, ImageOps

MAX_LADO = 1600


class ImagenInvalida(Exception):
    pass


def procesar(archivo):
    try:
        archivo.seek(0)
        imagen = Image.open(archivo)
        imagen = ImageOps.exif_transpose(imagen)
        con_transparencia = imagen.mode in ("RGBA", "LA") or (
            imagen.mode == "P" and "transparency" in imagen.info
        )
        imagen.thumbnail((MAX_LADO, MAX_LADO))
        salida = BytesIO()
        if con_transparencia:
            imagen.convert("RGBA").save(salida, format="PNG", optimize=True)
            tipo, extension = "image/png", ".png"
        else:
            imagen.convert("RGB").save(salida, format="JPEG", quality=85, optimize=True)
            tipo, extension = "image/jpeg", ".jpg"
    except Exception as error:
        raise ImagenInvalida(f"No se pudo procesar «{archivo.name}».") from error

    base = os.path.splitext(os.path.basename(archivo.name))[0][:100] or "imagen"
    return base + extension, tipo, salida.getvalue()