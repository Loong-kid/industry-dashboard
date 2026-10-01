import copy
import unittest

from derive_copper_inventory import build, NAME
from fetch_copper_snapshot import TOTAL, LME


def doc(name, rows):
    return dict(unit='톤', fetched='2026-10-01', series={name: rows})


class TotalTests(unittest.TestCase):
    def inputs(self):
        return [doc('SHFE 구리 주간 재고', [['2026-09-24', 10], ['2026-09-30', 20]]),
                doc(TOTAL, [['2026-09-24', 100], ['2026-09-29', 110], ['2026-10-01', 999]]),
                doc(LME, [['2026-09-24', 200], ['2026-09-30', 220]])]

    def test_sum_and_backward_alignment(self):
        result = build(*self.inputs())
        self.assertEqual(result['series'][NAME], [['2026-09-24', 310], ['2026-09-30', 350]])
        self.assertEqual(result['source_dates']['2026-09-30']['COMEX'], '2026-09-29')
        for i, (_, value) in enumerate(result['series'][NAME]):
            self.assertEqual(value, sum(result['series'][s][i][1] for s in ('SHFE', 'COMEX', 'LME')))

    def test_stale_missing_and_units(self):
        inputs = self.inputs()
        inputs[1]['series'][TOTAL] = [['2026-09-24', 100]]
        result = build(*inputs)
        self.assertEqual(len(result['series'][NAME]), 1)
        self.assertIn('2026-09-30', result['omitted_anchor_dates'])
        inputs[1]['unit'] = 'short tons'
        with self.assertRaises(ValueError):
            build(*inputs)
        inputs = self.inputs()
        inputs[1]['series'][TOTAL] = [['2026-10-01', 999]]
        with self.assertRaises(ValueError):
            build(*inputs)


if __name__ == '__main__':
    unittest.main()
