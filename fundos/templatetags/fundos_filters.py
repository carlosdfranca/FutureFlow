from django import template
from decimal import Decimal, InvalidOperation
import re

register = template.Library()


@register.filter(name="brl")
def brl(value, decimals=2):
    """
    Formats a numeric value as Brazilian Real without the R$ prefix.
    Usage:
        {{ value|brl }}       → "8.242.523,54"
        {{ value|brl:"8" }}   → "1.000000024,12345678"
    Returns "—" for None or invalid values.
    """
    if value is None or value == "":
        return "—"
    try:
        decimals = int(decimals)
        d = Decimal(str(value))
        formatted = f"{d:,.{decimals}f}"          # uses EN locale: 8,242,523.54
        # swap EN separators to BR: 8.242.523,54
        result = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
        return result
    except (InvalidOperation, ValueError, TypeError):
        return "—"


@register.filter(name="cpf_cnpj")
def cpf_cnpj(value):
    """
    Formats a string of digits as CPF or CNPJ.
    Usage:
        {{ value|cpf_cnpj }}
    CPF  (11 digits): "12345678901"   → "123.456.789-01"
    CNPJ (14 digits): "12345678000190" → "12.345.678/0001-90"
    Returns the original value if it doesn't match either length.
    """
    if not value:
        return value
    digits = re.sub(r'\D', '', str(value))
    if len(digits) == 11:
        return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"
    if len(digits) == 14:
        return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"
    return value
