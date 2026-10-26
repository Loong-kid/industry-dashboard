"""Financial scope, original-year accounting and refinery navigation checks."""
import copy
import contextlib
import io
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from refining_sources import statement_facts, reported_accounts

ROOT=Path(__file__).resolve().parents[1]


class RefiningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.state=json.loads((ROOT/'data/oil/refining_state.json').read_bytes())

    def test_four_full_histories_from_2014(self):
        self.assertEqual(set(self.state['companies']),{'vlo','mpc','psx','soil'})
        for key,c in self.state['companies'].items():
            self.assertEqual(c['rows'][0]['date'],'2014-03-31',key)
            self.assertGreaterEqual(len(c['rows']),50,key)
            self.assertEqual(len(c['rows']),len({r['date'] for r in c['rows']}))
            self.assertEqual({a['year'] for a in c['annual']},set(range(2014,max(a['year'] for a in c['annual'])+1)))
            for r in c['rows']+c['annual']:
                self.assertLessEqual(r['date'],self.state['updated'])
                for metric in ('revenue','profit','capex'):
                    self.assertIn(metric,r,(key,r['date'],metric))
                    self.assertTrue(math.isfinite(r[metric]))
                    if metric!='profit':self.assertGreaterEqual(r[metric],0)
                    refs=r['refs'][metric]
                    self.assertTrue(refs['url'].startswith('https://'))
                    self.assertTrue(refs['components'])
                    for ref in refs['components']:self.assertLessEqual(ref['filed'],self.state['updated'])

    def test_quarters_reconcile_to_original_year_annual(self):
        for key,c in self.state['companies'].items():
            for a in c['annual']:
                quarters=[r for r in c['rows'] if r['year']==a['year']]
                self.assertEqual(len(quarters),4,(key,a['year']))
                for metric in ('revenue','profit','capex'):
                    self.assertLessEqual(abs(sum(r[metric] for r in quarters)-a[metric]),4,(key,a['year'],metric))

    def test_original_statement_2025_anchors(self):
        expected={'vlo':(122687,3181,796),'mpc':(132699,8291,3486),'psx':(132376,2275,2233),'soil':(34246957,235631,3906036)}
        for key,values in expected.items():
            r=next(r for r in self.state['companies'][key]['annual'] if r['year']==2025)
            self.assertEqual(tuple(r[m] for m in ('revenue','profit','capex')),values,key)
        # Valero includes the separately reported consolidated VIE cash CAPEX,
        # while deferred turnarounds/catalysts and nonconsolidated JVs stay out.
        self.assertEqual(expected['vlo'][2],719+71+6)
        # PSX excludes non-sales gains/JV earnings in the operating calculation.
        self.assertEqual(expected['psx'][1],132376-131140+1039)

    def test_s_oil_pdf_history_and_taxonomy_transition(self):
        rows=self.state['companies']['soil']['rows']
        first=rows[0]
        self.assertEqual((first['revenue'],first['profit'],first['capex']),(7602458,46938,87111))
        q=next(r for r in rows if r['date']=='2015-12-31')
        self.assertEqual(q['capex'],654448-400794)
        for date,expected in [('2017-09-30',1433457-693490),('2019-09-30',584899-373098)]:
            q=next(r for r in rows if r['date']==date)
            self.assertEqual(q['capex'],expected)
            self.assertIn('source_tag',q['refs']['capex']['components'][0])

    def test_card_scope_currency_and_real_annual_views(self):
        for key in self.state['companies']:
            for metric in ('revenue','profit','capex'):
                d=json.loads((ROOT/f'data/oil/company_{key}_{metric}.json').read_bytes())
                self.assertEqual(d['unit'],'KRW 백만' if key=='soil' else 'USD 백만')
                self.assertIn('전사 연결',d['description'])
                self.assertFalse(d['span_gaps'])
                self.assertEqual(set(d['series_views']),{'quarter','annual'})
                annual=next(iter(d['series_views']['annual']['series'].values()))
                self.assertEqual(len(annual),len(self.state['companies'][key]['annual']))
                self.assertEqual(annual[0][0],'2014-12-31')
                self.assertFalse(any('?' in b['value'] for b in d['basis_details']))
        psx=json.loads((ROOT/'data/oil/company_psx_profit.json').read_bytes())
        self.assertIn('(계산)',psx['name'])
        psx=json.loads((ROOT/'data/oil/company_psx_capex.json').read_bytes())
        self.assertIn('회사 기준',psx['name'])

    def test_catalog_and_independent_refresh(self):
        c=json.loads((ROOT/'data/catalog.json').read_bytes());oil=next(i for i in c['industries'] if i['id']=='oil')
        self.assertEqual(next(t['name'] for t in oil['tabs'] if t['id']=='refining'),'정유')
        sections=[s for s in oil['sections'] if s.get('tab')=='refining']
        self.assertEqual(len(sections),4)
        self.assertEqual(sum(len(s['indicators']) for s in sections),12)
        self.assertTrue(all(s['layout']=='financial' for s in sections))
        js=(ROOT/'assets/refresh.js').read_text(encoding='utf8')
        self.assertIn('subtab === "refining"',js);self.assertIn('update-refining.yml',js)

    def test_source_failure_keeps_last_successful_values_and_dates(self):
        import fetch_refining as fetch
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory);state=out/'refining_state.json'
            state.write_text(json.dumps(self.state),encoding='utf8')
            with patch.object(fetch,'OUT',out),patch.object(fetch,'STATE',state),patch.object(fetch,'download',return_value={}),contextlib.redirect_stdout(io.StringIO()):
                result=fetch.collect()
            for key,previous in self.state['companies'].items():
                self.assertFalse(result['companies'][key]['ok'])
                self.assertEqual(result['companies'][key]['rows'],previous['rows'])
                self.assertEqual(result['companies'][key]['fetched'],previous['fetched'])
                doc=json.loads((out/f'company_{key}_revenue.json').read_bytes())
                self.assertFalse(doc['collection_status']['ok'])
                self.assertEqual(doc['updated'],previous['rows'][-1]['date'])

    def test_main_statement_ignores_variance_and_keeps_vie_capex(self):
        raw=b'''<html><table><tr><td>Year Ended 2025 2024 Change Revenues Income before income tax Earnings per common share</td></tr><tr><td>Revenues</td><td>100</td><td>90</td><td>10</td></tr><tr><td>Operating income</td><td>20</td><td>18</td><td>2</td></tr></table>
        <table><tr><td>Year Ended 2025 2024 2023 Revenues Income before income tax Earnings per common share</td></tr><tr><td>Revenues</td><td>100</td><td>90</td><td>80</td></tr><tr><td>Operating income (loss)</td><td>(20)</td><td>18</td><td>16</td></tr></table>
        <table><tr><td>Cash flows from operating activities Cash flows from financing activities Net Change in Cash</td></tr><tr><td>Capital expenditures (excluding VIEs)</td><td>(7)</td><td>(6)</td><td>(5)</td></tr><tr><td>Capital expenditures of VIEs:</td></tr><tr><td>Diamond Green Diesel Holdings LLC</td><td>(2)</td><td>(2)</td><td>(2)</td></tr><tr><td>Other VIEs</td><td>(1)</td><td>(1)</td><td>(1)</td></tr><tr><td>Deferred turnaround</td><td>(8)</td><td>(8)</td><td>(8)</td></tr></table></html>'''
        m=dict(date='2025-12-31',filed='2026-02-01',form='10-K',accn='original',url='https://example.com/original')
        facts=statement_facts(raw,m,'vlo');json.dumps(facts) # no circular references
        current={f['metric']:f['val']/1e6 for f in facts if f['end']=='2025-12-31'}
        self.assertEqual(current,dict(revenue=100,profit=-20,capex=10))

    def test_mpc_separately_disclosed_related_party_sales_are_included(self):
        raw=b'''<table><tr><td>2019 2018 per share data Income before income taxes</td></tr><tr><td>Sales and other operating revenues</td><td>28081</td><td>18694</td></tr><tr><td>Sales to related parties</td><td>186</td><td>172</td></tr><tr><td>Income from operations</td><td>669</td><td>440</td></tr></table>'''
        meta=dict(date='2019-03-31',filed='2019-05-09',form='10-Q',accn='original',url='https://example.com/original')
        facts=statement_facts(raw,meta,'mpc');json.dumps(facts)
        current=next(f for f in facts if f['metric']=='revenue' and f['end']=='2019-03-31')
        self.assertEqual(current['val']/1e6,28267)
        self.assertEqual(len(current['inputs']),2)

    def test_cumulative_cash_and_reclassified_income_do_not_use_annual_divided_by_four(self):
        facts=[]
        def add(metric,start,end,value,filed,form='10-Q'):
            facts.append(dict(metric=metric,start=start,end=end,val=value*1e6,filed=filed,form=form,accn=filed,source_url='https://example.com/'+filed,source_tag=metric))
        for q,end in [(1,'03-31'),(2,'06-30'),(3,'09-30')]:
            add('capex','2020-01-01','2020-'+end,[10,35,75][q-1],f'2020-{q*3+2:02d}-01')
            add('revenue',f'2020-{(q-1)*3+1:02d}-01','2020-'+end,[100,200,30][q-1],f'2020-{q*3+2:02d}-01')
        add('revenue','2020-01-01','2020-09-30',60,'2020-11-01')
        add('revenue','2020-01-01','2020-03-31',10,'2021-05-01')
        add('revenue','2020-04-01','2020-06-30',20,'2021-08-01')
        add('revenue','2020-01-01','2020-12-31',100,'2021-02-01','10-K')
        add('capex','2020-01-01','2020-12-31',120,'2021-02-01','10-K')
        # A later annual-only restatement must not replace the original basis.
        add('capex','2020-01-01','2020-12-31',99,'2023-02-01','10-K')
        rows,annual=reported_accounts(facts,1,'2026-10-27')
        self.assertEqual([r['capex'] for r in rows],[10,25,40,45])
        self.assertEqual([r['revenue'] for r in rows],[10,20,30,40])
        self.assertEqual(annual[0]['capex'],120)


if __name__=='__main__':unittest.main()
