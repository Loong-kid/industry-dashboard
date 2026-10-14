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

    def test_historical_coverage_and_micron_capex_basis(self):
        for company in ['samsung','hynix','tsmc','smic','umc']:
            rows=self.snapshot['companies'][company]['quarters']
            self.assertEqual(rows[0]['date'],'2014-03-31')
            self.assertEqual(len(rows),50)
        rows=self.snapshot['companies']['micron']['quarters']
        self.assertEqual(rows[0]['date'],'2013-11-28')
        self.assertEqual(len(rows),52)
        first=next(r for r in rows if (r['year'],r['quarter'])==(2016,1))
        self.assertEqual((first['date'],first['revenue']),('2015-12-03',3350))
        self.assertIsNone(rows[0]['capex'])
        self.assertEqual(rows[0]['capex_gross'],669)
        self.assertEqual(next(r['capex'] for r in rows if (r['year'],r['quarter'])==(2019,4)),1970)
        annual={2014:16358,2015:16192,2016:12399,2017:20322,2018:30391,2019:23406,2020:21435,2021:27705,2022:30758,2023:15540}
        for y,total in annual.items():self.assertAlmostEqual(sum(r['revenue'] for r in rows if r['year']==y),total,delta=2)
        gf=self.snapshot['companies']['globalfoundries']['quarters']
        self.assertEqual((len(gf),gf[0]['date']),(24,'2020-09-30'))
        self.assertEqual(sum(r['revenue'] for r in gf if r['year']==2024),6750)
        self.assertEqual(next(r['profit'] for r in gf if (r['year'],r['quarter'])==(2024,4)),-701)
        smic=next(r for r in self.snapshot['companies']['smic']['quarters'] if (r['year'],r['quarter'])==(2023,1))
        self.assertEqual((smic['date'],smic['revenue']),('2023-03-31',1462.288))

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
        gross,cash,own = (dict(doc['series'][label]) for label in ['총 CAPEX · JV 지분 포함','현금 CAPEX · JV 지분 포함','자체 유형자산 취득 · JV 제외'])
        self.assertIsNone(gross['2025-06-27'])
        self.assertIsNone(cash['2025-06-27'])
        self.assertEqual(own['2025-06-27'],45)
        self.assertNotIn(890,gross.values())  # FY2025 annual total, never Q4.
        self.assertEqual(gross['2025-10-03'],337+50)
        self.assertEqual(cash['2025-10-03'],-10+50)
        self.assertFalse(doc['span_gaps'])
        self.assertEqual(len(doc['point_sources']['2026-07-03']['supporting_sources']),2)

    def test_ssd_predecessor_history_is_separate_and_sourced(self):
        snapshot=copy.deepcopy(self.snapshot)
        self.assertEqual(build(snapshot),build(snapshot))
        sndk=self.docs['company_sandisk_revenue']
        old=dict(sndk['series']['구 SanDisk 연결 매출'])
        self.assertEqual(old['2014-03-30'],1511.945)
        self.assertAlmostEqual(sum(v for d,v in old.items() if d.startswith('2014')),6627.701)
        wd=dict(sndk['series']['WDC Flash 매출 · HDD 제외'])
        self.assertEqual(wd['2018-06-29'],2363)
        self.assertEqual(wd['2024-12-27'],1876)
        self.assertEqual(self.docs['company_sandisk_profit']['series']['구 SanDisk GAAP 영업이익'][0],['2014-03-30',425.174])
        self.assertEqual(self.docs['company_sandisk_capex']['series']['구 SanDisk 자체 PP&E 순취득 · JV 제외'][0],['2014-03-30',34.517])
        old_rows=self.snapshot['companies']['sandisk']['history_groups'][0]['quarters']
        for y,total in [(2014,232.786),(2015,413.828)]:
            self.assertAlmostEqual(sum(r['capex_own_ppe'] for r in old_rows if r['year']==y),total)
        self.assertNotIn('WDC Flash 매출 · HDD 제외',self.docs['company_sandisk_profit']['series'])
        k=self.snapshot['companies']['kioxia']
        for year,revenue,profit in [(2019,987.2,-173.1),(2020,1178.5,6.6),(2021,1526.5,216.2),(2023,1076.6,-252.7)]:
            rows=[r for r in k['quarters'] if r['year']==year]
            self.assertEqual(len(rows),4)
            self.assertAlmostEqual(sum(r['revenue'] for r in rows),revenue,delta=.11)
            self.assertAlmostEqual(sum(r['profit'] for r in rows),profit,delta=.11)
        legacy=self.docs['company_kioxia_revenue']['series']['도시바 Memory 매출 · FY2014 분류']
        self.assertEqual(legacy[0],['2014-06-30',177.7])
        self.assertAlmostEqual(sum(v for d,v in legacy),860.6)
        tm=k['history_groups'][1]['quarters']
        self.assertAlmostEqual(sum(r['profit'] for r in tm if r['year']==2017),479.1)
        cap=dict(self.docs['company_kioxia_capex']['series']['CAPEX'])
        self.assertIsNone(cap['2018-12-31'])
        self.assertEqual(cap['2023-03-31'],184.2)
        self.assertEqual(cap['2023-06-30'],104.5)
        self.assertEqual(self.docs['company_kioxia_revenue']['comparison_dates']['2015-06-30']['year_ago'],None)

    def test_reject_invalid_historical_period_source_and_missing_capex_reason(self):
        for field,value in [('period_basis','annual'),('source_url',''),('revenue',float('nan'))]:
            snap=copy.deepcopy(self.snapshot)
            snap['companies']['sandisk']['history_groups'][0]['quarters'][0][field]=value
            with self.assertRaises(ValueError):validate(snap)
        snap=copy.deepcopy(self.snapshot)
        snap['companies']['kioxia']['quarters'][0].pop('missing_reasons')
        with self.assertRaises(ValueError):validate(snap)

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
        self.assertEqual(len(self.docs),27)
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
