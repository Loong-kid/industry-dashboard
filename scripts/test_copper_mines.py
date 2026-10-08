"""Guard accounting scopes, units and provenance in the mine register."""
import copy
import json
import unittest
from pathlib import Path

from aggregate_copper_mines import build, LB_TO_T

ROOT = Path(__file__).resolve().parents[1]


class CopperMineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = json.loads((ROOT / 'manual/copper_mines.json').read_text(encoding='utf-8'))
        cls.doc = build(cls.source)
        cls.rows = {r['id']: r for r in cls.doc['rows']}

    def test_checked_in_output_and_review_date(self):
        output = json.loads((ROOT / 'data/commodities/comm_copper_mines.json').read_text(encoding='utf-8'))
        self.assertEqual(self.doc, output)
        self.assertNotIn('coverage', self.source)  # build must not mutate the editable register
        self.assertEqual(self.doc['updated'], self.source['reviewed'])
        self.assertFalse(self.doc['coverage']['complete_global_census'])

    def test_metal_ore_and_equity_are_not_conflated(self):
        morenci = self.rows['morenci']
        self.assertAlmostEqual(morenci['production'][-1]['cu_tonnes'], 497e6 * LB_TO_T, places=3)
        self.assertIn('72%', morenci['production'][-1]['basis'])
        self.assertIn('100%', morenci['reserves']['basis'])
        self.assertIsNone(self.rows['los_pelambres']['reserves']['cu_tonnes'])
        self.assertEqual(self.rows['zaldivar']['production'][-1]['value'], 36.7)
        self.assertIn('50%', self.rows['zaldivar']['production'][-1]['basis'])
        self.assertEqual(self.rows['escondida']['production'][-1]['period'], 'fiscal')

    def test_lifetime_requires_complete_history(self):
        total = self.rows['kamoa_kakula']['period_total']
        self.assertEqual(total['cu_tonnes'], 1658834)
        self.assertTrue(total['lifetime'])
        self.assertEqual((total['from_year'], total['to_year']), (2021, 2025))
        self.assertFalse(self.rows['morenci']['period_total']['lifetime'])
        self.assertIsNone(self.rows['cobre_panama']['period_total'])
        self.assertEqual(self.rows['panguna']['cumulative']['cu_tonnes'], 3e6)

    def test_no_sum_across_mixed_scopes_or_missing_years(self):
        for mixed in ['basis', 'period', 'gap']:
            source = copy.deepcopy(self.source)
            row = next(r for r in source['rows'] if r['id'] == 'kamoa_kakula')
            row.pop('history_complete')
            if mixed == 'gap':
                row['production'].pop(1)
            else:
                row['production'][0][mixed] = 'fiscal' if mixed == 'period' else '지분 생산'
            result = build(source)
            self.assertIsNone(next(r for r in result['rows'] if r['id'] == row['id'])['period_total'])

    def test_invalid_records_fail_closed(self):
        for change in ['source', 'equity', 'duplicate', 'future', 'unit', 'incomplete']:
            source = copy.deepcopy(self.source)
            row = source['rows'][0]
            if change == 'source':
                row['production'][0]['sources'] = ['missing_source']
            elif change == 'equity':
                row['owners'][0]['pct'] = 101
            elif change == 'duplicate':
                source['rows'].append(copy.deepcopy(row))
            elif change == 'future':
                row['production'][0]['date'] = '2099-12-31'
            elif change == 'unit':
                row['production'][0]['unit'] = 'tonnes concentrate'
            else:
                row['history_complete'] = True
            with self.subTest(change=change), self.assertRaises(AssertionError):
                build(source)

    def test_changed_owners_and_no_combined_production_allocation(self):
        self.assertEqual(self.rows['khoemacau']['owners'][0]['pct'], 55)
        self.assertEqual(self.rows['copper_mountain']['owners'][0]['pct'], 100)
        for key in ['kamoto', 'mutanda', 'tenke_fungurume', 'kisanfu', 'olympic_dam']:
            self.assertEqual(self.rows[key]['production'], [])
        self.assertEqual(self.rows['malanjkhand']['ore_mined']['unit'], 'kt ore')


if __name__ == '__main__':
    unittest.main()
