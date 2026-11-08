"""Check the requested observation-to-CSV contract on explicitly synthetic records."""
import unittest
from evidence import export_observations

class ExportTests(unittest.TestCase):
    """Exercise exact columns, order, quoting and missing-field behavior."""
    def test_one_record(self):
        """Map each key to its named column."""
        self.assertEqual(export_observations([{"id": "A", "value": 12}]), "id,value\nA,12\n")
    def test_order(self):
        """Preserve input order instead of sorting identifiers."""
        self.assertEqual(export_observations([{"id": "B", "value": 9}, {"id": "A", "value": 12}]), "id,value\nB,9\nA,12\n")
    def test_quoting(self):
        """Escape commas, quotes, accents and line breaks with standard CSV rules."""
        self.assertEqual(export_observations([{"id": 'muestra, "á"', "value": "una\nlínea"}]), 'id,value\n"muestra, ""á""","una\nlínea"\n')
    def test_empty(self):
        """An empty registry still exports its header."""
        self.assertEqual(export_observations([]), "id,value\n")
    def test_missing_id(self):
        """Missing identity is an explicit data error."""
        with self.assertRaises(ValueError):
            export_observations([{"value": 12}])
    def test_missing_value(self):
        """Missing value is not invented or silently filled."""
        with self.assertRaises(ValueError):
            export_observations([{"id": "A"}])
