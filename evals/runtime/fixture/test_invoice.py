import unittest
from decimal import Decimal
from invoice import total_due

class InvoiceTests(unittest.TestCase):
    def test_total(self):
        self.assertEqual(total_due(Decimal("100"), Decimal("0.21")), Decimal("121.00"))
    def test_rounding(self):
        self.assertEqual(total_due(Decimal("0.05"), Decimal("0.10")), Decimal("0.06"))
