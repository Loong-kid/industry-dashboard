"""Financial reconciliation and missing-period safeguards for MOCVD charts."""
import copy
import json
import unittest
from pathlib import Path

from fetch_mocvd import build, difference

ROOT=Path(__file__).resolve().parents[1]


class MOCVDTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.facts=json.loads((ROOT/'data/_mocvd/facts.json').read_text(encoding='utf-8'))
        cls.manual=json.loads((ROOT/'manual/mocvd.json').read_text(encoding='utf-8'))
        cls.docs=build(copy.deepcopy(cls.facts),copy.deepcopy(cls.manual))

    def test_aix_quarters_reconcile_to_annual(self):
        for annual in self.manual['aix_annual']:
            year=annual['year']
            for id,label,key in [('mocvd_aix_orders','총수주액','orders_ytd'),
                                 ('mocvd_aix_orders','연결 매출','revenue_ytd'),
                                 ('mocvd_aix_profit','EBIT','ebit_ytd'),
                                 ('mocvd_aix_revenue','장비 매출','equipment_ytd')]:
                vals=[v for d,v in self.docs[id]['series'][label] if d.startswith(str(year))]
                self.assertEqual(len(vals),4)
                # Independent one-decimal quarterly disclosures can differ
                # from the rounded YTD table by 0.1m; do not alter source data.
                self.assertAlmostEqual(sum(vals),annual[key],delta=0.21)

    def test_reviewed_aix_quarter_scope(self):
        d=self.docs
        date='2026-06-30'
        self.assertEqual(dict(d['mocvd_aix_backlog']['series']['장비 수주잔고'])[date],456.9)
        self.assertEqual(dict(d['mocvd_aix_advances']['series']['선수금 계약부채'])[date],197.5)
        self.assertEqual(dict(d['mocvd_aix_revenue']['series']['장비 매출'])[date],86.3)
        self.assertEqual(dict(d['mocvd_aix_orders']['series']['총수주액'])[date],214.5)
        self.assertAlmostEqual(dict(d['mocvd_aix_btb']['series']['분기 수주/매출'])[date],214.5/115.1,places=3)

    def test_cash_capex_fiscal_year_conservation(self):
        for company,total in [('lumentum',451.3),('coherent',1102.9)]:
            doc=self.docs[f'mocvd_{company}_capex']
            points=doc['series']['유형자산 취득 현금지출']
            fy26=[v for date,v in points if doc['period_labels'][date].startswith('FY2026')]
            self.assertEqual(len(fy26),4)
            self.assertAlmostEqual(sum(fy26),total,places=2)
        self.assertEqual(dict(self.docs['mocvd_lumentum_capex']['series']['유형자산 취득 현금지출'])['2026-06-27'],166.8)

    def test_missing_quarter_is_not_zero_or_ytd(self):
        rows=[dict(date='2026-06-30',year=2026,quarter=2,capex_ytd=159.8,url='https://example.com')]
        self.assertEqual(difference(rows,'capex_ytd'),[])

    def test_disclosed_and_approximate_application_sales(self):
        doc=self.docs['mocvd_aix_applications']
        self.assertEqual(doc['series']['광전자·통신'][-1][1],101.4)
        self.assertNotIn('2025-12-31',doc['point_annotations'])
        self.assertIn('2024-12-31',doc['point_annotations'])
        for i,a in enumerate(self.manual['aix_annual']):
            self.assertAlmostEqual(sum(v[i][1] for v in doc['series'].values()),a['equipment_ytd'],places=2)

    def test_sources_and_no_invented_unit_series(self):
        for id,doc in self.docs.items():
            for points in doc.get('series',{}).values():
                self.assertTrue(points)
                self.assertEqual([d for d,_ in points],sorted({d for d,_ in points}))
                for date,_ in points:self.assertTrue(doc['point_sources'][date]['url'].startswith('https://'))
            self.assertNotEqual(doc.get('unit'),'대')
        self.assertNotIn('series',self.docs['mocvd_equipment_events'])

    def test_catalog_files_complete(self):
        c=json.loads((ROOT/'data/catalog.json').read_text(encoding='utf-8'))
        ind=next(x for x in c['industries'] if x['id']=='semicon')
        ids=[]
        for section in ind['sections']:
            if section.get('tab')!='mocvd':continue
            ids+=section['indicators']
            for company in section.get('companies',[]):ids+=company['indicators']
        self.assertEqual(set(ids),set(self.docs))
        self.assertEqual(len(ids),len(set(ids)))


if __name__=='__main__':unittest.main()
