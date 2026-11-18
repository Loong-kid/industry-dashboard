"""Period, unit, source and peer-scope guards for cleanroom/HVAC financials."""
import copy,json,math,tempfile,unittest
from unittest.mock import patch
import requests
from fetch_cleanroom import ROOT,META,STATE,load,build,view,kelington,latest_taiwan,kelington_html,merge_rows,collect
from cleanroom_sources import accounts
from import_cleanroom_ir import parse_pdf

class CleanroomTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.meta=load(META,{});cls.state=load(STATE,{})

    def test_selected_eight_and_routes(self):
        expected={'hanyang','sebo','shinsung','knsol','uis','lk','acter','kelington'}
        self.assertEqual(set(self.state['companies']),expected)
        s=next(i for i in load(ROOT/'data/catalog.json',{})['industries'] if i['id']=='semicon')
        self.assertEqual(next(c for c in s['material_categories'] if c['id']=='cleanroom')['name'],'클린룸/공조')
        sections=[s for s in s['sections'] if s.get('tab')=='cleanroom_summary']
        self.assertEqual(sections[0]['type'],'valuation_summary')
        self.assertFalse(any(s.get('table_kind')=='cleanroom' for s in sections))
        self.assertEqual(len([s for s in sections if s.get('anchor')]),8)
        docs=build(self.meta,self.state)
        for section in sections:
            for identifier in section.get('indicators',[]):self.assertIn(identifier,docs)

    def test_document_values_and_no_ytd_as_quarter(self):
        for doc in build(self.meta,self.state).values():
            if not doc.get('series_views'):continue
            self.assertTrue(doc['compact_tooltip']);self.assertFalse(doc['span_gaps'])
            for kind,v in doc['series_views'].items():
                for values in v['series'].values():
                    dates=[d for d,n in values];self.assertEqual(dates,sorted(set(dates)))
                    for d,n in values:
                        if n is not None:self.assertTrue(math.isfinite(n));self.assertIn(d,v['point_sources'])
                if kind=='ytd':self.assertIn('누적',v['frequency_label']);self.assertEqual(v['change_mode'],'none')
                if kind=='annual':self.assertTrue(all(d.endswith('-12-31') for d in v['period_labels']))
        self.assertNotIn('quarter',build(self.meta,self.state)['company_cleanroom_kelington_capex']['series_views'])
        self.assertNotIn('profit',self.state['companies']['kelington']['rows'][-1])

    def test_history_coverage_and_latest(self):
        for key in ('hanyang','sebo','shinsung','knsol'):
            self.assertGreaterEqual(self.state['companies'][key]['rows'][-1]['date'],'2026-09-30')
        for key in ('uis','acter','kelington'):
            self.assertEqual(self.state['companies'][key]['rows'][0]['date'],'2014-03-31')
        self.assertEqual(next(r for r in self.state['companies']['uis']['annual'] if r['year']==2025)['revenue'],66093.193)
        self.assertEqual(next(r for r in self.state['companies']['lk']['annual'] if r['year']==2025)['revenue'],77484.652)
        for key in ('uis','lk','acter'):
            co=self.state['companies'][key]
            self.assertGreaterEqual(co['rows'][-1]['date'],'2026-09-30')
            latest=next(r for r in co['rows'] if r['date']=='2026-09-30')
            report=next(r for r in co['reports'] if r['year']==2026 and r['quarter']==2)
            ytd=next(r for r in co['ytd'] if r['date']=='2026-09-30')
            for m in ('revenue','profit'):self.assertAlmostEqual(latest[m]+report['fields'][m]['ytd'],ytd[m],places=5)

    def test_missing_cash_quarter_is_not_zero_or_six_months(self):
        r=dict(year=2026,quarter=2,date='2026-06-30',fields={'capex':dict(value=None,ytd=11.612,url='https://example.com/q2',account_name='cash PP&E')})
        co=accounts([r]);self.assertEqual(co['rows'],[])
        q1=dict(year=2026,quarter=1,date='2026-03-31',fields={'capex':dict(value=None,ytd=4,url='https://example.com/q1',account_name='cash PP&E')})
        co=accounts([q1,r]);self.assertAlmostEqual(co['rows'][-1]['capex'],7.612)
        q1['fields']['capex']['ytd']=20;self.assertEqual(len(accounts([q1,r])['rows']),1)

    def test_kelington_failure_retains_success_and_pbt_label(self):
        prior=copy.deepcopy(self.state['companies']['kelington'])
        with patch('fetch_cleanroom.requests.get',side_effect=requests.Timeout):co=kelington(prior,True)
        self.assertFalse(co['ok']);self.assertEqual(co['fetched'],prior['fetched']);self.assertEqual(co['rows'],prior['rows'])
        doc=build(self.meta,self.state)['company_cleanroom_kelington_pbt'];self.assertIn('세전이익',doc['name']);self.assertIn('영업이익으로 표시하지',doc['description'])

    def test_ir_and_latest_api_failure_do_not_shorten_successful_history(self):
        from pathlib import Path
        original=copy.deepcopy(self.state)
        domestic=dict(companies={k:copy.deepcopy(v) for k,v in original['companies'].items() if k in self.meta['companies']})
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp);state_path=out/'state.json';state_path.write_text(json.dumps(original),encoding='utf-8')
            with patch('fetch_cleanroom.STATE',state_path),patch('fetch_cleanroom.OUT',out),patch('fetch_cleanroom.domestic_collect',return_value=domestic),patch('fetch_cleanroom.collect_issuer',side_effect=requests.Timeout),patch('fetch_cleanroom.requests.get',side_effect=requests.Timeout):
                after=collect(True)
            for key in ('uis','lk','acter','kelington'):
                self.assertEqual(after['companies'][key]['rows'],original['companies'][key]['rows'])
                self.assertEqual(after['companies'][key]['annual'],original['companies'][key]['annual'])
                self.assertEqual(after['companies'][key]['fetched'],original['companies'][key]['fetched'])
                self.assertFalse(after['companies'][key]['ok'])

    def test_kelington_parser_keeps_ambiguous_decimal_blank(self):
        head='<table><tr><th></th>'+''.join('<th>'+str(y)+'</th>' for y in (2025,2024,2023,2022))+'</tr><tr><td>Revenue</td><td>1000</td><td>900</td><td>800</td><td>700</td></tr></table>'
        tables=''.join('<table><tr><th>'+label+'</th><th>Q1</th><th>Q2</th><th>Q3</th><th>Q4</th></tr><tr><td>2023</td><td>100</td><td>200</td><td>300</td><td>'+last+'</td></tr></table>' for label,last in [('Revenue','400'),('Profit Before Tax','46.896'),('Profit After Tax','90')])
        co=kelington_html(head+tables);last=co['rows'][-1];self.assertNotIn('pbt',last);self.assertEqual(last['net'],.09)

    def test_pdf_consolidated_and_units_and_cash_sign(self):
        pages=['合併綜合損益表 新台幣千元\n4000 營業收入    2,000 100 1,000 100\n6900 營業利益    200 10 100 10','合併現金流量表\n取得不動產、廠房及設備    (50) (20)']
        r=parse_pdf(pages,2025,4,'https://example.com/annual.pdf');self.assertEqual(r['fields']['revenue']['ytd'],2);self.assertEqual(r['fields']['capex']['ytd'],.05)
        with self.assertRaises(ValueError):parse_pdf([p.replace('合併','個體') for p in pages],2025,4,'https://example.com/annual.pdf')
        with self.assertRaises(ValueError):parse_pdf([p.replace('(50)','50') for p in pages],2025,4,'https://example.com/annual.pdf')

if __name__=='__main__':unittest.main()
