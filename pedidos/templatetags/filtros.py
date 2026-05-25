from django import template

register = template.Library()

@register.filter
def guaranies(valor):
    try:
        numero = int(round(float(str(valor))))
        return f"{numero:,}".replace(",", ".") + " Gs."
    except (ValueError, TypeError):
        return f"{valor} Gs."

@register.filter
def guaranies_sin_simbolo(valor):
    try:
        numero = int(round(float(str(valor))))
        return f"{numero:,}".replace(",", ".")
    except (ValueError, TypeError):
        return str(valor)
    
@register.filter
def js_number(valor):
    """Convierte decimal a número JS seguro (sin comas ni puntos de miles)"""
    try:
        return int(round(float(str(valor))))
    except (ValueError, TypeError):
        return 0
    
@register.filter
def get_item(dictionary, key):
    """Obtiene un valor de un diccionario por clave — útil en templates."""
    if not dictionary:
        return None
    return dictionary.get(key)