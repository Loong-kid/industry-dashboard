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
        cls.history=json.loads((ROOT/'manual/mocvd_history.json').read_text(encoding='utf-8'))
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
        for company,total in [('lumentum',451.3),('coherent',1102.909)]:
            doc=self.docs[f'mocvd_{company}_capex']
            points=doc['series']['유형자산 취득 현금지출']
            fy26=[v for date,v in points if doc['period_labels'][date].startswith('FY2026')]
            self.assertEqual(len(fy26),4)
            self.assertAlmostEqual(sum(fy26),total,places=2)
        self.assertEqual(dict(self.docs['mocvd_lumentum_capex']['series']['유형자산 취득 현금지출'])['2026-06-27'],166.8)

    def test_history_annual_anchors_and_scope_break(self):
        # Independent 2014 annual-report anchors, million original currency.
        aix=self.docs['mocvd_aix_orders']['series']
        self.assertAlmostEqual(sum(v for d,v in aix['연결 매출'] if d.startswith('2014')),193.8)
        self.assertAlmostEqual(sum(v for d,v in aix['장비 수주 · 2014 구기준']),153.4)
        self.assertTrue(all(d>='2015-01-01' for d,_ in aix['총수주액']))
        self.assertTrue(all(d>='2015-01-01' for d,_ in self.docs['mocvd_aix_btb']['series']['분기 수주/매출']))
        for metric,anchor in [('revenue',683.261),('profit',46.486),('capex',29.220)]:
            doc=self.docs['mocvd_coherent_'+metric]
            points=next(iter(doc['series'].values()))
            vals=[v for date,v in points if doc['period_labels'][date].startswith('FY2014 ')]
            self.assertEqual(len(vals),4)
            self.assertAlmostEqual(sum(vals),anchor,places=3)

    def test_coherent_operating_profit_sign_and_included_charges(self):
        # FY2025 report p.54: sales minus COGS, R&D, SG&A,
        # restructuring and held-for-sale impairment. No EBITDA adjustment.
        doc=self.docs['mocvd_coherent_profit']['series_views']['annual']
        value=dict(next(iter(doc['series'].values())))['2025-06-30']
        self.assertAlmostEqual(value,(5810115-3766793-581924-926451-160081-84988)/1000,places=3)
        ref=doc['point_sources']['2025-06-30']
        self.assertEqual(ref['tag'],'calculated_operating_profit')

    def test_annual_only_history_is_never_fabricated_as_quarters(self):
        lumen=self.docs['mocvd_lumentum_capex']
        self.assertEqual(dict(lumen['series_views']['annual']['series']['유형자산 취득 현금지출'])['2014-06-28'],64.2)
        self.assertNotIn('2014-06-28',dict(lumen['series']['유형자산 취득 현금지출']))
        ifx=self.docs['mocvd_infineon_capex']
        self.assertEqual(ifx['default_view'],'annual')
        self.assertEqual(ifx['frequency'],'yearly')
        self.assertEqual(len(ifx['series_views']['quarter']['series']['유형자산 취득 현금지출']),2)
        self.assertEqual(dict(ifx['series']['유형자산 취득 현금지출'])['2014-09-30'],567)
        self.assertEqual(dict(ifx['series']['Investments · 무형자산·개발비 포함'])['2025-09-30'],2094)

    def test_week_based_fiscal_comparisons(self):
        doc=self.docs['mocvd_lumentum_capex']['series_views']['quarter']
        comparisons=doc['comparison_dates']['2021-10-02']
        self.assertEqual(comparisons['year_ago'],'2020-09-26')
        self.assertEqual(comparisons['quarter_ago'],'2021-07-03')

    def test_disclosure_specific_history_ranges(self):
        veeco=self.docs['mocvd_veeco_revenue']['series']
        self.assertEqual(veeco['연결 매출'][0][0],'2014-03-31')
        self.assertEqual(len(veeco['연결 매출']),50)
        self.assertEqual(veeco['Compound Semiconductor'][0][0],'2023-03-31')

    def test_later_collector_quarters_survive_history_merge(self):
        facts=copy.deepcopy(self.facts)
        facts['coherent'].append(dict(date='2026-09-30',year=2027,quarter=1,
            capex_ytd=123.4,url='https://example.com/new-report',fetched='2026-11-04'))
        manual=copy.deepcopy(self.manual)
        manual['veeco_quarters'].append(dict(date='2026-09-30',revenue=200,compound=30,
            url='https://example.com/new-veeco-report',fetched='2026-11-04'))
        docs=build(facts,manual)
        cohr=docs['mocvd_coherent_capex']['series_views']['quarter']
        self.assertEqual(cohr['series']['유형자산 취득 현금지출'][-1],['2026-09-30',123.4])
        self.assertEqual(cohr['comparison_dates']['2026-09-30']['quarter_ago'],'2026-06-30')
        self.assertEqual(cohr['fetched'],'2026-11-04')
        self.assertEqual(dict(docs['mocvd_veeco_revenue']['series']['연결 매출'])['2026-09-30'],200)

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
