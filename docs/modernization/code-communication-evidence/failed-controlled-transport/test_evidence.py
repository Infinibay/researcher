"""Assert the frozen numeric-observation mean contract, including actual zeroes."""
import unittest
from evidence import mean_observations

class MeanTests(unittest.TestCase):
    """Separate zero observations, empty input and ordinary means."""
    def test_zero_counts(self):
        """A real zero contributes to both sample size and the requested mean."""
        self.assertEqual(mean_observations([{"value": 0}, {"value": 10}]), 5)
    def test_all_zeroes(self):
        """Zero observations must not become an empty registry."""
        self.assertEqual(mean_observations([{"value": 0}, {"value": 0}]), 0)
    def test_empty(self):
        """Empty input is represented explicitly by None."""
        self.assertIsNone(mean_observations([]))
    def test_nonzero(self):
        """Ordinary input retains its arithmetic mean."""
        self.assertEqual(mean_observations([{"value": 4}, {"value": 6}]), 5)
