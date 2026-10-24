import colorsys

COLOR_POR_DEFECTO = "#c8102e"
COLOR_BARRA_POR_DEFECTO = "#2f2f2f"


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


def _contraste(a, b):
    la, lb = _luminancia(a), _luminancia(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def _con_contraste(valor_hex, fondo_rgb, minimo=3.0):
    h, l, s = colorsys.rgb_to_hls(*(c / 255 for c in _hex_a_rgb(valor_hex)))
    paso = 0.04 if _luminancia(fondo_rgb) <= 0.2 else -0.04
    actual = valor_hex
    for _ in range(25):
        if _contraste(_hex_a_rgb(actual), fondo_rgb) >= minimo:
            break
        l = min(max(l + paso, 0.0), 1.0)
        actual = _hls_a_hex(h, l, s)
    return actual


def _rgb_texto(valor_hex):
    return ", ".join(str(c) for c in _hex_a_rgb(valor_hex))


def paleta(valor, barra=COLOR_BARRA_POR_DEFECTO):
    try:
        rgb = _hex_a_rgb(valor)
    except (ValueError, TypeError):
        rgb = _hex_a_rgb(COLOR_POR_DEFECTO)
    try:
        rgb_barra = _hex_a_rgb(barra)
    except (ValueError, TypeError):
        rgb_barra = _hex_a_rgb(COLOR_BARRA_POR_DEFECTO)
    h, l, s = colorsys.rgb_to_hls(*(c / 255 for c in rgb))
    l = min(max(l, 0.22), 0.65)
    primario = _hls_a_hex(h, l, s)
    oscuro = _hls_a_hex(h, l * 0.8, s)
    activo = _hls_a_hex(h, l * 0.62, s)
    rgb_primario = _hex_a_rgb(primario)
    rgb_oscuro = _hex_a_rgb(oscuro)
    texto = "#212529" if _luminancia(rgb_primario) > 0.2 else "#ffffff"

    hb, lb, sb = colorsys.rgb_to_hls(*(c / 255 for c in rgb_barra))
    barra_hex = "#{:02x}{:02x}{:02x}".format(*rgb_barra)
    barra_oscura = _hls_a_hex(hb, lb * 0.78, sb)
    barra_clara = _hls_a_hex(hb, min(lb + 0.08, 0.95), sb)
    barra_oscura_fondo = _luminancia(rgb_barra) <= 0.2
    barra_texto = "#ffffff" if barra_oscura_fondo else "#212529"
    icono = _con_contraste(primario, rgb_barra)
    return {
        "primario": primario,
        "oscuro": oscuro,
        "activo": activo,
        "rgb": ", ".join(str(c) for c in rgb_primario),
        "rgb_oscuro": ", ".join(str(c) for c in rgb_oscuro),
        "texto": texto,
        "barra": barra_hex,
        "barra_oscura": barra_oscura,
        "barra_clara": barra_clara,
        "barra_texto": barra_texto,
        "barra_texto_rgb": _rgb_texto(barra_texto),
        "barra_invertir": "1" if barra_oscura_fondo else "0",
        "icono": icono,
        "icono_rgb": _rgb_texto(icono),
    }