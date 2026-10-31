def entero_positivo(valor):
    valor = (valor or "").strip()
    if valor.isascii() and valor.isdigit() and len(valor) <= 9:
        return int(valor)
    return None