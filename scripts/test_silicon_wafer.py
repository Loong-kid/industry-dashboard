"""Independent macro/financial anchors and safeguards for mixed disclosures."""
import copy
import json
import unittest
from pathlib import Path

from fetch_silicon_wafer import build,validate,merge_monthly
from import_wafer_financials import decimal_numbers,gw_monthly

ROOT=Path(__file__).resolve().parents[1]


class WaferTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot=json.loads((ROOT/'manual/silicon_wafer.json').read_text(encoding='utf-8'))
        cls.docs=build(cls.snapshot)

    def test_market_actuals_and_reporting_frequency(self):
        semi=self.snapshot['semi']
        self.assertEqual(len(semi['quarters']),46)
        self.assertEqual(semi['quarters'][-1]['value'],3573)
        self.assertEqual(semi['annuals'][0]['value'],10098)
        self.assertEqual(semi['annuals'][-1]['value'],12973)
        self.assertEqual(semi['annuals'][-1]['revenue'],11.4)
        self.assertEqual(self.docs['wafer_global_revenue']['frequency'],'yearly')
        self.assertFalse(self.docs['wafer_global_growth'].get('quarterly_revenue_summary'))
        self.assertAlmostEqual(self.docs['wafer_global_growth']['series']['YoY'][-1][1],(3573/3327-1)*100,places=3)

    def test_semi_annuals_reconcile_only_to_published_precision(self):
        semi=self.snapshot['semi']
        for a in semi['annuals'][1:]:
            qs=[r['value'] for r in semi['quarters'] if r['year']==a['year']]
            self.assertEqual(len(qs),4)
            self.assertLessEqual(abs(sum(qs)-a['value']),1)
        q2=next(r for r in semi['quarters'] if r['year']==2015 and r['quarter']==2)
        self.assertEqual(q2['value'],7930-2637-2591)
        self.assertIn('minus',q2['refs']['value']['calculation'])

    def test_sumco_consolidated_profit_and_cash_capex(self):
        meta=self.snapshot['companies']['sumco'];rows={r['year']:r for r in meta['annuals']}
        self.assertEqual((rows[2014]['revenue'],rows[2014]['profit'],rows[2014]['capex']),(225319,25642,9962))
        self.assertEqual((rows[2025]['revenue'],rows[2025]['profit'],rows[2025]['capex']),(409670,1342,111033))
        last=meta['quarters'][-1]
        self.assertEqual((last['revenue'],last['profit'],last['acceptance_capex']),(113600,-1100,10000))
        capex=self.docs['wafer_sumco_capex']
        self.assertIn('현금',next(iter(capex['series_views']['annual']['series'])))
        self.assertIn('검수',next(iter(capex['series_views']['quarter']['series'])))
        for a in meta['annuals']:
            for metric in ['revenue','profit']:
                qs=[r[metric] for r in meta['quarters'] if r['year']==a['year']]
                if len(qs)==4:self.assertLessEqual(abs(sum(qs)-a[metric]),400)

    def test_siltronic_investment_is_distinct_from_cash(self):
        meta=self.snapshot['companies']['siltronic'];rows={r['year']:r for r in meta['annuals']}
        self.assertEqual((rows[2014]['revenue'],rows[2014]['profit'],rows[2014]['capex']),(846,-17.1,40.7))
        self.assertEqual(rows[2025]['capex'],369.1)
        self.assertEqual(rows[2025]['cash_capex'],380.1)
        self.assertEqual(rows[2019]['capex'],363)
        self.assertEqual(meta['quarters'][-1]['profit'],-51.9)
        self.assertEqual(rows[2017]['capex'],123.2)
        self.assertTrue(all('capex' not in r for r in meta['quarters'] if r['year']==2017))
        for a in meta['annuals']:
            for metric in ['revenue','profit','capex']:
                qs=[r[metric] for r in meta['quarters'] if r['year']==a['year'] and metric in r]
                if len(qs)==4:self.assertAlmostEqual(sum(qs),a[metric],delta=.21)

    def test_globalwafers_original_statements_and_missing_history(self):
        meta=self.snapshot['companies']['globalwafers'];rows={r['year']:r for r in meta['annuals']}
        self.assertEqual(rows[2018]['profit'],17578.051) # Original PDF comparative, unlike IR summary.
        self.assertAlmostEqual(rows[2017]['profit'],11807.766-4394.224,places=3)
        self.assertNotIn('capex',rows[2014]);self.assertNotIn('capex',rows[2015])
        last=meta['quarters'][-1]
        self.assertEqual((last['revenue'],last['profit']),(15214.310,1422.811))
        self.assertAlmostEqual(last['capex'],5661.847-3460.304,places=3)
        for a in meta['annuals']:
            for metric in ['revenue','profit','capex']:
                qs=[r[metric] for r in meta['quarters'] if r['year']==a['year'] and metric in r]
                if len(qs)==4 and metric in a:self.assertAlmostEqual(sum(qs),a[metric],delta=.0011)

    def test_monthly_calendar_window_and_prior_year_base(self):
        points=self.snapshot['gw_monthly']['points']
        self.assertEqual((points[0][0],points[-1]),('2015-01-31',['2026-09-30',5129]))
        d=self.docs['wafer_globalwafers_monthly']
        self.assertAlmostEqual(d['series']['3개월 이동평균'][-1][1],(4978+4764+5129)/3,places=3)
        self.assertEqual(dict(points)['2019-11-30'],4344)
        yoy=self.docs['wafer_globalwafers_monthly_yoy']['series']['전년 동월 대비'][-1][1]
        self.assertAlmostEqual(yoy,(5129/5904-1)*100,places=3)
        with self.assertRaises(ValueError):gw_monthly('<table></table>','2026-10-24')
        merged=merge_monthly([['2025-01-31',10],['2026-01-31',20]],[['2026-01-31',21],['2026-02-28',22]])
        self.assertEqual(merged,[['2025-01-31',10],['2026-01-31',21],['2026-02-28',22]])
        with self.assertRaises(ValueError):merge_monthly(merged,[['2026-01-31',20]])

    def test_source_completeness_null_gaps_and_original_figures(self):
        for id,doc in self.docs.items():
            for view in [doc]+list(doc.get('series_views',{}).values()):
                for points in view.get('series',{}).values():
                    dates=[d for d,v in points];self.assertEqual(dates,sorted(set(dates)))
                    for d,v in points:
                        if v is not None:self.assertTrue(view['point_sources'][d]['url'].startswith('https://'))
        gap=self.docs['wafer_siltronic_capex']['series']['유형·무형자산 투자액 · 발생 기준']
        self.assertIsNone(dict(gap)['2017-06-30'])
        gallery=self.docs['wafer_customer_evidence']
        self.assertNotIn('series',gallery)
        self.assertEqual(len(gallery['figures']),3)
        for f in gallery['figures']:self.assertTrue((ROOT/f['image']).exists())

    def test_numeric_signs_and_reject_invalid_facts(self):
        self.assertEqual(decimal_numbers('(1.1) 9.4 (5.2)'),[-1.1,9.4,-5.2])
        for bad in [float('nan'),-100]:
            invalid=copy.deepcopy(self.snapshot);invalid['companies']['sumco']['annuals'][0]['capex']=bad
            with self.assertRaises(ValueError):validate(invalid)

    def test_catalog_and_generated_docs(self):
        catalog=json.loads((ROOT/'data/catalog.json').read_text(encoding='utf-8'))
        industry=next(x for x in catalog['industries'] if x['id']=='semicon')
        self.assertIn('wafer',[t['id'] for t in industry['tabs']])
        ids=[id for s in industry['sections'] if s.get('tab')=='wafer' for id in s['indicators']]
        self.assertEqual(set(ids),set(self.docs));self.assertEqual(len(ids),len(set(ids)))
        self.assertEqual(sum('series' in doc for doc in self.docs.values()),16)


if __name__=='__main__':unittest.main()
