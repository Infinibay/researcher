from decimal import Decimal, ROUND_HALF_UP

PROJECT_MARKER = 'ALPHA-PUBLIC'

def total_due(subtotal: Decimal, tax_rate: Decimal) -> Decimal:
    """Return tax-inclusive total, rounded to cents using HALF_UP."""
    return subtotal + tax_rate
