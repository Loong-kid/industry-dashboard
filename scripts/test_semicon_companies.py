import copy
import datetime as dt
import json
import unittest
from pathlib import Path

from aggregate_semicon_companies import build, validate

ROOT = Path(__file__).resolve().parents[1]


class QuarterlyFinancials(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = json.loads((ROOT/'manual/semicon_companies.json').read_text(encoding='utf-8'))
        cls.docs = build(cls.snapshot)

    def test_annual_revenue_reconciliation(self):
        # Independent FY totals in the official annual-results comparative tables.
        totals = [('hynix',2023,32.766),('hynix',2024,66.194),
                  ('tsmc',2024,2894.30),('micron',2024,25111),('kioxia',2024,1706.5)]
        for company,year,total in totals:
            rows = [r for r in self.snapshot['companies'][company]['quarters'] if r['year']==year]
            self.assertEqual(len(rows),4)
            self.assertAlmostEqual(sum(r['revenue'] for r in rows),total,delta=0.003)

    def test_fiscal_comparisons_survive_53_week_year(self):
        doc = self.docs['company_micron_revenue']
        self.assertEqual(doc['period_labels']['2026-09-03'],'FY2026 Q4')
        self.assertEqual(doc['comparison_dates']['2026-09-03'],
                         dict(year_ago='2025-08-28',quarter_ago='2026-05-28'))
        doc = self.docs['company_sandisk_revenue']
        self.assertEqual(doc['comparison_dates']['2025-10-03']['quarter_ago'],'2025-06-27')
        doc = self.docs['company_kioxia_revenue']
        self.assertEqual(doc['period_labels']['2026-06-30'],'FY2026 Q1')
        self.assertEqual(doc['comparison_dates']['2026-06-30']['quarter_ago'],'2026-03-31')

    def test_capex_does_not_mix_annual_jv_and_own_ppe(self):
        doc = self.docs['company_sandisk_capex']
        gross,cash,own = (dict(points) for points in doc['series'].values())
        self.assertIsNone(gross['2025-06-27'])
        self.assertIsNone(cash['2025-06-27'])
        self.assertEqual(own['2025-06-27'],45)
        self.assertNotIn(890,gross.values())  # FY2025 annual total, never Q4.
        self.assertEqual(gross['2025-10-03'],337+50)
        self.assertEqual(cash['2025-10-03'],-10+50)
        self.assertFalse(doc['span_gaps'])
        self.assertEqual(len(doc['point_sources']['2026-07-03']['supporting_sources']),2)

    def test_scopes_and_losses_remain_distinct(self):
        revenue = self.docs['company_samsung_revenue']
        self.assertEqual(len(revenue['series']),3)
        self.assertEqual(revenue['default_series'][0],'메모리 매출')
        self.assertIn('DS 영업이익',self.docs['company_samsung_profit']['series'])
        self.assertIn('연결',self.docs['company_samsung_capex']['description'])
        self.assertEqual(dict(self.docs['company_sandisk_profit']['series']['연결 영업이익'])['2025-03-28'],-1881)
        self.assertIn('GAAP',self.docs['company_micron_profit']['description'])
        self.assertIn('IFRS',self.docs['company_kioxia_profit']['description'])

    def test_reject_annual_duplicates_future_and_missing_facts(self):
        for field,value in [('period_basis','annual'),('date','2030-03-31'),('revenue',None)]:
            snapshot = copy.deepcopy(self.snapshot)
            snapshot['companies']['tsmc']['quarters'][0][field] = value
            with self.assertRaises(ValueError):validate(snapshot)
        snapshot = copy.deepcopy(self.snapshot)
        snapshot['companies']['tsmc']['quarters'].append(copy.deepcopy(snapshot['companies']['tsmc']['quarters'][0]))
        with self.assertRaises(ValueError):validate(snapshot)

    def test_published_files_match_reviewed_facts_and_sources(self):
        self.assertEqual(len(self.docs),24)
        catalog = json.loads((ROOT/'data/catalog.json').read_text(encoding='utf-8'))
        semicon = next(i for i in catalog['industries'] if i['id']=='semicon')
        linked = {id for s in semicon['sections'] if s.get('tab') in ['memory','foundry','ssd'] for id in s['indicators']}
        self.assertEqual(linked,set(self.docs))
        for id,doc in self.docs.items():
            self.assertEqual(json.loads((ROOT/f'data/semicon/{id}.json').read_text(encoding='utf-8')),doc)
            for points in doc['series'].values():
                self.assertEqual(len(points),len({d for d,v in points}))
                for date,value in points:
                    self.assertLessEqual(dt.date.fromisoformat(date),dt.date.fromisoformat(doc['fetched']))
                    self.assertTrue(doc['point_sources'][date]['url'].startswith('https://'))


if __name__ == '__main__':unittest.main()
