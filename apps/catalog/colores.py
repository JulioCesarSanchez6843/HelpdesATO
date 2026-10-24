import colorsys

COLOR_POR_DEFECTO = "#c8102e"


def _hex_a_rgb(valor):
    valor = valor.lstrip("#")
    return tuple(int(valor[i:i + 2], 16) for i in (0, 2, 4))


def _hls_a_hex(h, l, s):
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return "#{:02x}{:02x}{:02x}".format(round(r * 255), round(g * 255), round(b * 255))


def _luminancia(rgb):
    def canal(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (canal(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def paleta(valor):
    try:
        rgb = _hex_a_rgb(valor)
    except (ValueError, TypeError):
        rgb = _hex_a_rgb(COLOR_POR_DEFECTO)
    h, l, s = colorsys.rgb_to_hls(*(c / 255 for c in rgb))
    l = min(max(l, 0.22), 0.65)
    primario = _hls_a_hex(h, l, s)
    oscuro = _hls_a_hex(h, l * 0.8, s)
    activo = _hls_a_hex(h, l * 0.62, s)
    fondo = _hls_a_hex(h, 0.15, min(s, 0.35))
    rgb_primario = _hex_a_rgb(primario)
    rgb_oscuro = _hex_a_rgb(oscuro)
    texto = "#212529" if _luminancia(rgb_primario) > 0.2 else "#ffffff"
    return {
        "primario": primario,
        "oscuro": oscuro,
        "activo": activo,
        "fondo": fondo,
        "rgb": ", ".join(str(c) for c in rgb_primario),
        "rgb_oscuro": ", ".join(str(c) for c in rgb_oscuro),
        "texto": texto,
    }