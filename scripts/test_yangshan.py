import unittest
from import_yangshan import validate


class PremiumTests(unittest.TestCase):
    def test_negative_premiums_and_source_disagreement(self):
        row = dict(date='2025-01-01', unit='USD/metric tonne', low=-20, high=-10, midpoint=-15)
        self.assertTrue(validate(row))
        self.assertFalse(validate(dict(row, midpoint=-13)))
        self.assertFalse(validate(dict(row, midpoint=0)))
        for change in [dict(low=float('nan')), dict(midpoint=True), dict(unit='CNY/tonne')]:
            with self.assertRaises(ValueError):
                validate(dict(row, **change))


if __name__ == '__main__':
    unittest.main()
