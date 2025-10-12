from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


@register.filter(name="currency_br")
def currency_br(value) -> str:
    """Format value as Brazilian currency (2.270,00)."""
    if value in (None, ""):
        return "0,00"

    if isinstance(value, Decimal):
        amount = value
    else:
        try:
            amount = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            return str(value)

    quantized = amount.quantize(Decimal("0.01"))
    sinal = "-" if quantized < 0 else ""
    quantized = abs(quantized)
    quantized_str = f"{quantized:.2f}"
    inteiro_str, decimal_str = quantized_str.split(".")
    inteiro_formatado = f"{int(inteiro_str):,}".replace(",", ".")
    return f"{sinal}{inteiro_formatado},{decimal_str}"
