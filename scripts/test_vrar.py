"""XR reporting scopes, original source amounts and quarter derivations."""
import copy,datetime as dt,json,math,unittest
from unittest.mock import patch
import requests
from pathlib import Path
from vrar_sources import reality_labs,parse_htc_text,htc_accounts,htc_links
from fetch_vrar import build,collect_htc

ROOT=Path(__file__).resolve().parents[1];FIX=ROOT/'scripts/fixtures/vrar'
def read(path):return json.loads(path.read_text(encoding='utf-8'))


class OriginalSources(unittest.TestCase):
    def test_htc_original_three_months_and_cash_ytd(self):
        text=(FIX/'htc-2026q3.txt').read_text(encoding='utf-8')
        r=parse_htc_text(text,2026,3,'https://investors.htc.com/original.pdf','2026-11-03')
        self.assertEqual(r['direct'],{'revenue':763.627,'profit':-506.602})
        self.assertEqual(r['values'],{'revenue':2030.455,'profit':-1642.025,'capex':11.646})
        self.assertEqual(r['comparatives'][0]['direct'],{'revenue':716.371,'profit':-853.954})
        with self.assertRaises(ValueError):parse_htc_text(text,2025,3,'url','2026-11-03')
        with self.assertRaises(ValueError):parse_htc_text(text.replace('Thousands of New Taiwan Dollars','Millions of Dollars'),2026,3,'url','2026-11-03')

    def test_htc_q4_and_cashflow_are_differenced_not_quartered(self):
        def report(q,revenue,profit,capex):
            d=f'2025-{q*3:02d}-'+('30' if q==3 else '31')
            return dict(year=2025,quarter=q,date=d,start='2025-01-01',values=dict(revenue=revenue,profit=profit,capex=capex),direct={},refs={m:dict(url='source-'+str(q),start='2025-01-01',end=d) for m in ('revenue','profit','capex')})
        a,b=report(3,90,-20,12),report(4,130,-30,18)
        result=htc_accounts([a,b]);q4=result['rows'][-1]
        self.assertEqual([q4[m] for m in ('revenue','profit','capex')],[40,-10,6])
        self.assertEqual(len(q4['refs']['capex']['components']),2)
        self.assertEqual(result['annual'][0]['revenue'],130)
        self.assertFalse(htc_accounts([b])['rows'])
        # Source revisions or missing compatible YTD must not fabricate a
        # negative capital expenditure or a zero to hide the mismatch.
        b['values']['capex']=11
        self.assertNotIn('capex',htc_accounts([a,b])['rows'][-1])

    def test_htc_report_links_use_official_working_download_host(self):
        html='<tr><td>2026 Q3Financial Results - Consolidated Financial Report (IFRS)</td><td><a href="https://investors-express.htc.com/documents/1575/report.pdf">PDF</a></td></tr>'
        self.assertEqual(htc_links(html,'https://investors.htc.com/')[0]['url'],'https://investors.htc.com/documents/1575/report.pdf?download=1')

    def test_reality_labs_dimensions_and_loss_sign(self):
        filing=read(FIX/'sources.json')['meta'];raw=(FIX/'meta-2026q3.xml').read_bytes();fields=reality_labs(raw,filing)
        quarter=lambda metric:next(r['val']/1e6 for r in fields[metric] if r['start']=='2026-07-01' and r['end']=='2026-09-30')
        self.assertEqual(quarter('revenue'),443)
        self.assertEqual(quarter('profit'),-4129)
        self.assertFalse(reality_labs(raw.replace(b'RealityLabsMember',b'FamilyOfAppsMember'),filing)['revenue'])
        with self.assertRaises(ValueError):reality_labs(raw,filing,1463972)


class PublishedHistory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.meta=read(ROOT/'manual/vrar/companies.json');cls.state=read(ROOT/'data/vrar/state.json')

    def test_six_issuers_and_all_three_accounts(self):
        self.assertEqual(set(self.meta['companies']),{'sapien','raontech','vuzix','kopin','htc','meta'})
        today=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date().isoformat()
        for key,spec in self.meta['companies'].items():
            co=self.state['companies'][key]
            for kind in ['rows','annual']:
                self.assertTrue(co[kind],key)
                self.assertEqual(len(co[kind]),len({r['date'] for r in co[kind]}),key)
                for metric in ['revenue','profit','capex']:self.assertTrue(any(metric in r for r in co[kind]),(key,kind,metric))
                for r in co[kind]:
                    self.assertLessEqual(r['date'],today)
                    for m in ['revenue','profit','capex']:
                        if m not in r:continue
                        self.assertTrue(math.isfinite(r[m]));self.assertTrue(r['refs'][m]['components'])
                        if m!='profit':self.assertGreaterEqual(r[m],0)
            if spec['source_type']=='dart':
                for r in co['rows']+co['annual']:
                    self.assertGreaterEqual(r['refs']['revenue']['components'][0]['start'],spec['minimum_start'])
            else:self.assertEqual(co['annual'][0]['year'],2014,key)

    def test_domestic_audited_2025_units(self):
        a=next(r for r in self.state['companies']['sapien']['annual'] if r['year']==2025)
        b=next(r for r in self.state['companies']['raontech']['annual'] if r['year']==2025)
        self.assertAlmostEqual(a['revenue'],17312.155993);self.assertAlmostEqual(a['profit'],-4565.205241)
        self.assertAlmostEqual(b['revenue'],8746.267801);self.assertAlmostEqual(b['profit'],-5810.442808)

    def test_vuzix_original_2025_totals(self):
        r=next(r for r in self.state['companies']['vuzix']['annual'] if r['year']==2025)
        self.assertAlmostEqual(r['revenue'],6.280611);self.assertAlmostEqual(r['profit'],-32.507894)

    def test_all_cards_have_quarter_and_year_and_rl_is_separate(self):
        docs=build(self.state,self.meta);self.assertEqual(len(docs),21)
        for identifier,d in docs.items():
            self.assertEqual(d['default_view'],'quarter');self.assertEqual(set(d['series_views']),{'quarter','annual'})
            self.assertTrue(d['company_kpi']);self.assertFalse(d['span_gaps'])
            self.assertEqual(read(ROOT/'data/vrar'/(identifier+'.json')),d)
        self.assertNotIn('company_vrar_meta_rl_capex',docs)
        rl=self.state['reality_labs']
        margin=docs['company_vrar_meta_rl_margin']['series_views']['quarter']['series']['Reality Labs 영업이익률']
        for date,value in margin:
            r=next(r for r in rl['rows'] if r['date']==date)
            self.assertAlmostEqual(value,r['profit']/r['revenue']*100)
        core=self.state['companies']['meta']['rows'][-1]
        self.assertGreater(core['revenue'],rl['rows'][-1]['revenue'])

    def test_sector_routes_data_files_and_workflow(self):
        catalog=read(ROOT/'data/catalog.json');sector=next(i for i in catalog['industries'] if i['id']=='vrar')
        self.assertEqual([t['id'] for t in sector['tabs']],['overview','korea','global','meta'])
        for section in sector['sections']:
            for indicator in section['indicators']:self.assertTrue((ROOT/'data/vrar'/(indicator+'.json')).exists())
        self.assertIn('update-vrar',(ROOT/'.github/workflows/publish-data.yml').read_text(encoding='utf-8'))
        self.assertIn('update-vrar.yml',(ROOT/'assets/refresh.js').read_text(encoding='utf-8'))
        serialized=json.dumps(self.state)
        self.assertNotIn('crtfc_key',serialized)

    def test_failed_current_htc_query_keeps_history_and_failure_status(self):
        prior=self.state['companies']['htc']
        def source(url,refresh=False):
            if url.endswith('/quarterly-results/'):return b'<a href="2026-quarterly-results">Learn More</a>'
            if '2026-quarterly-results' in url:return b'<tr><td>2026 Q3 Financial Results - Consolidated Financial Report (IFRS)</td><td><a href="https://investors.htc.com/documents/latest.pdf">PDF</a></td></tr>'
            raise requests.Timeout('source unavailable')
        with patch('fetch_vrar.cached',source):result=collect_htc(prior,'2026-11-03')
        self.assertFalse(result['ok']);self.assertTrue(result['source_errors'])
        self.assertEqual(result['rows'],prior['rows']);self.assertEqual(result['annual'],prior['annual'])


if __name__=='__main__':unittest.main()
