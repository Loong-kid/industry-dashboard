import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from fetch_cpu_companies import load,save
from fetch_neocloud import ROOT,collect,rpo_history
from neocloud_sources import native_cloud,nebius_tables,nebius_rpo
from neocloud_presentations import documents

FIX=ROOT/'scripts/fixtures/neocloud'


class NeocloudTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.specs=load(ROOT/'manual/us-datacenter/neoclouds.json',{})
        cls.state=load(ROOT/'data/datacenter/us_neocloud_state.json',{})

    def test_native_cloud_dimension_does_not_count_mining_or_consolidated(self):
        f=load(FIX/'iren_2026_filing.json',{});raw=(FIX/'iren_2026.xml').read_bytes()
        fields=native_cloud(raw,'iren',self.specs['iren'],f)
        annual=next(r for r in fields['cloud_revenue'] if r['start']=='2025-07-01' and r['end']=='2026-06-30')
        self.assertEqual(annual['val'],128795000)
        with self.assertRaisesRegex(ValueError,'issuer'):
            native_cloud(raw,'iren',dict(self.specs['iren'],cik=1),f)

    def test_nebius_untagged_financials_retain_gaap_losses_and_exact_ai_scope(self):
        f=load(FIX/'nebius_q1_2026_filing.json',{});raw=(FIX/'nebius_q1_2026.html').read_bytes()
        fields=nebius_tables(raw,f)
        current=lambda metric:next(r['val']/1e6 for r in fields[metric] if r['start']=='2026-01-01')
        self.assertEqual(current('revenue'),399.)
        self.assertEqual(current('profit'),-128.)
        self.assertEqual(current('cloud_revenue'),389.7)
        self.assertEqual(current('capex'),2472.9)
        rpo=nebius_rpo(raw,f)['rpo'][0]
        self.assertEqual(rpo['end'],'2026-03-31');self.assertAlmostEqual(rpo['val'],33585300000,delta=.001)
        self.assertTrue(rpo['instant'])

    def test_latest_disclosed_quarters_are_not_estimates_or_adjusted_ebitda(self):
        expected={'crwv':[2575.,-49.,6422.,2575.], 'nbis':[582.3,-175.9,5657.4,574.9], 'iren':[137.225,-620.383,1328.849,70.515]}
        for k,values in expected.items():
            c=self.state['companies'][k];r=next(r for r in c['rows'] if r['date']=='2026-06-30')
            self.assertEqual([r[m] for m in ('revenue','profit','capex','cloud_revenue')],values)
            self.assertIsInstance(c['core_ok'],bool);self.assertIsInstance(c['errors'],list)
            if k!='crwv':self.assertNotIn('cloud_profit',r)
            else:self.assertEqual(r['cloud_profit'],r['profit'])

    def test_nebius_recast_ai_history_and_iren_fiscal_q4(self):
        nb=self.state['companies']['nbis']
        self.assertEqual([(r['date'],r['cloud_revenue']) for r in nb['rows'] if r['date'].startswith('2025')],
                         [('2025-03-31',41.4),('2025-06-30',93.7),('2025-09-30',131.1),('2025-12-31',214.2)])
        self.assertEqual([r['year'] for r in nb['annual']][:3],[2023,2024,2025])
        iren=self.state['companies']['iren'];q4=next(r for r in iren['rows'] if r['date']=='2025-06-30')
        self.assertEqual((q4['year'],q4['quarter']),(2025,4))
        self.assertEqual(q4['cloud_revenue'],6.963)
        for r in iren['annual']:
            self.assertTrue(r['date'].endswith('06-30'))
            self.assertIn('us-gaap',r['refs']['revenue']['tag'])

    def test_rpo_is_quarter_end_asc606_not_backlog_tcv_arr_or_lease_value(self):
        c=self.state['companies']
        for key,expected in [('crwv',103700.),('nbis',37490.6),('iren',5100.)]:
            self.assertEqual(next(r['rpo'] for r in c[key]['rpo']['rows'] if r['date']=='2026-06-30'),expected)
        self.assertNotIn('2025-11-02',[r['date'] for r in c['iren']['rpo']['rows']])
        for key,cohort in c.items():
            self.assertTrue(all(r['refs']['rpo']['instant'] for r in cohort['rpo']['rows']))
            self.assertTrue(all(r['date'].endswith('06-30' if key=='iren' else '12-31') for r in cohort['rpo']['annual']))

    def test_snapshot_filter_does_not_turn_contract_signing_into_quarter_rpo(self):
        def f(date,value):return dict(end=date,val=value,filed='2026-01-01',accn='x',form='10-Q')
        payload={'facts':{'us-gaap':{'RevenueRemainingPerformanceObligation':{'units':{'USD':[f('2025-11-02',9700000000),f('2025-12-31',289411000)]}}}}}
        r=rpo_history(payload,self.specs['iren'],'2026-11-01')
        self.assertEqual([(x['date'],x['rpo']) for x in r['rows']],[('2025-12-31',289.411)])

    def test_publication_views_sources_units_and_unavailable_cloud_profit(self):
        docs=documents(self.specs,self.state['companies']);self.assertEqual(len(docs),20)
        for d in docs:
            self.assertEqual(d,load(ROOT/'data/datacenter'/(d['id']+'.json'),{}))
            self.assertTrue(d['compact_tooltip']);self.assertFalse(d['span_gaps'])
            for kind,view in d['series_views'].items():
                for name,values in view['series'].items():
                    self.assertEqual(len(values),len(dict(values)))
                    for date,value in values:
                        if value is not None:
                            ref=view['series_sources'][name][date]
                            self.assertTrue(ref['url'].startswith('https://www.sec.gov/'))
                            self.assertLessEqual(ref['filed'],self.state['companies'][next(k for k,s in self.specs.items() if s['name']==name)]['checked'] if name in [s['name'] for s in self.specs.values()] else max(c['checked'] for c in self.state['companies'].values()))
        for k in ('nbis','iren'):
            d=next(d for d in docs if d['id']==f'us_nc_{k}_financials')
            self.assertEqual(d['series']['클라우드 영업이익'],[])
            self.assertEqual(d['series_status']['클라우드 영업이익'],'미공개')
        rpo=next(d for d in docs if d['id']=='us_nc_iren_rpo')
        self.assertIn(['2026-06-30',5100.],rpo['series_views']['annual']['series']['IREN'])
        capex=next(d for d in docs if d['id']=='us_nc_compare_capex');self.assertEqual(capex['chart_type'],'bar')

    def test_two_us_views_preserve_hyperscalers_and_korea(self):
        dc=next(i for i in load(ROOT/'data/catalog.json',{})['industries'] if i['id']=='datacenter')
        self.assertEqual([v['id'] for v in dc['tabs'][1]['views']],['hyperscalers','neocloud'])
        groups={view:[s for s in dc['sections'] if s.get('view')==view] for view in ('hyperscalers','neocloud')}
        self.assertEqual(sum(len(s['indicators']) for s in groups['hyperscalers']),31)
        self.assertEqual([len(s['indicators']) for s in groups['neocloud']],[5,5,5,5])
        self.assertEqual(len([s for s in dc['sections'] if s['tab']=='korea']),5)

    def test_refresh_failure_retains_verified_arrays_and_reports_stale(self):
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder);save(out/'us_neocloud_state.json',self.state)
            with patch('fetch_neocloud.OUT',out),patch('fetch_neocloud.CACHE',out/'cache'),patch('fetch_neocloud.SecClient') as client:
                client.return_value.get.side_effect=ConnectionError('test outage')
                result=collect()
            for k,old in self.state['companies'].items():
                c=result['companies'][k]
                self.assertEqual(c['rows'],old['rows']);self.assertEqual(c['annual'],old['annual']);self.assertEqual(c['rpo'],old['rpo'])
                self.assertEqual(c['fetched'],old['fetched']);self.assertFalse(c['core_ok']);self.assertTrue(c['errors'])


if __name__=='__main__':unittest.main()
