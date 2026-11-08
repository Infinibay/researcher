"""Synthetic copied measurement labels and arithmetic; physical measurement has not been independently checked."""
from decimal import Decimal

MEASUREMENT = {"id": "M7", "revision": 4, "value": "7.5", "unit": "mL"}

def line_total(quantity, price_per_unit):
    """Multiply an explicit quantity and its unit price without adding other charges."""
    return Decimal(str(quantity)) * Decimal(str(price_per_unit))

def millilitres(value, unit):
    """Convert a supplied unit explicitly; the arithmetic does not verify a copied unit label."""
    return Decimal(str(value)) * {"mL": Decimal("1"), "L": Decimal("1000")}[unit]
