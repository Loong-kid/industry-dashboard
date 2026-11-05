"""Original reporting scope, quarter fidelity and separate net/gross PPE cash flows."""
import copy,unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import requests
from fetch_cpu_companies import load,parse_facts,today
from fetch_semicon_osat import ROOT,META,STATE,CACHE,build,build_ase,collect
from osat_sources import parse_ase_release,ase_annual
from fetch_rings import validate

FIX=ROOT/'scripts/fixtures/semicon_osat'
ENTRY=dict(filed='2026-10-29',accn='0000950103-26-016324',url='https://www.sec.gov/Archives/edgar/data/1122411/000095010326016324/dp255760_6k.htm')

class SourceAccounts(unittest.TestCase):
    def test_original_ase_quarter_and_net_cash_are_not_usd_equipment_capex(self):
        raw=(FIX/'ase-2026q3.html').read_text(encoding='utf8')
        rows=parse_ase_release(raw,ENTRY);self.assertEqual(len(rows),3)
        latest=next(r for r in rows if r['date']=='2026-09-30')
        self.assertEqual([latest[k] for k in ('revenue','profit','net_ppe_cash')],[244161,33142,125852])
        self.assertNotIn('capex',latest)
        self.assertNotEqual(latest['net_ppe_cash'],2104) # USD equipment CAPEX in prose.
        self.assertIn('NET',latest['refs']['net_ppe_cash']['calculation'])
        self.assertEqual(parse_ase_release(raw.replace('NT$ million','US$ million'),ENTRY),[])
        self.assertEqual(parse_ase_release(raw.replace('ASE','OTHER'),ENTRY),[])
        self.assertTrue(all(r['refs']['revenue']['filed']>=r['date'] for r in rows))

    def test_ase_annual_native_ifrs_units_and_amkor_ytd_cash(self):
        meta=load(META,{})
        rows=ase_annual(load(FIX/'ase_recent.json',{}),meta['global_companies']['ase'],'2026-11-06')
        last=rows[-1]
        self.assertEqual(last['date'],'2025-12-31')
        self.assertEqual(last['revenue'],645387.710)
        self.assertEqual(last['capex'],164642.502)
        self.assertTrue(last['refs']['capex']['tag'].startswith('ifrs-full:'))
        payload=load(FIX/'amkor_recent.json',{})
        rows=parse_facts(payload,meta['global_companies']['amkor'],'2026-11-06')
        last=rows[-1];self.assertEqual(last['date'],'2026-09-30')
        self.assertEqual(last['revenue'],1990.557)
        self.assertEqual(len(last['refs']['capex']['components']),2)
        a,b=last['refs']['capex']['components'];self.assertEqual(a['start'],b['start'])
        with self.assertRaises(ValueError):parse_facts(payload,dict(meta['global_companies']['amkor'],cik=1122411),'2026-11-06')

class PublishedAccounts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.meta=load(META,{});cls.state=load(STATE,{})

    def test_company_scope_and_catalog_routes(self):
        self.assertEqual(set(self.meta['companies']),{'tesna','hana','sfa','lb','nepes','nepesark'})
        self.assertEqual(set(self.meta['global_companies']),{'amkor','ase'})
        self.assertEqual(self.meta['companies']['tesna']['ticker'],'131970')
        self.assertIn('연결',self.meta['companies']['nepes']['note'])
        semicon=next(i for i in load(ROOT/'data/catalog.json',{})['industries'] if i['id']=='semicon')
        self.assertEqual(next(c for c in semicon['material_categories'] if c['id']=='osat')['default_tab'],'osat_summary')
        self.assertEqual({t['id'] for t in semicon['tabs'] if t.get('category')=='osat'},{'osat_summary','osat_korea','osat_global'})
        expected={'osat_summary':25,'osat_korea':18,'osat_global':7}
        for tab,count in expected.items():
            sections=[s for s in semicon['sections'] if s.get('tab')==tab]
            ids=[i for s in sections for i in s['indicators']]
            self.assertEqual(len(ids),count);self.assertEqual(len(ids),len(set(ids)))
            for id in ids:self.assertTrue((ROOT/'data/semicon'/(id+'.json')).exists(),id)

    def test_history_coverage_and_published_views(self):
        expected={**self.meta['companies'],**self.meta['global_companies']}
        self.assertEqual(set(self.state['companies']),set(expected))
        docs=build(self.meta,self.state);self.assertEqual(len(docs),25)
        for key,spec in expected.items():
            co=self.state['companies'][key]
            self.assertTrue(co['rows']);self.assertTrue(co['annual'])
            if key in self.meta['companies']:validate(co,today())
            if key not in ['ase','nepesark']:self.assertEqual(co['annual'][0]['year'],2014,key)
            if key=='nepesark':self.assertGreaterEqual(co['rows'][0]['date'],'2019-04-01')
            if key=='ase':self.assertGreaterEqual(co['rows'][0]['date'],'2018-04-01')
            for metric in ['revenue','profit','capex']:
                doc=docs[f'company_osat_{key}_{metric}']
                self.assertEqual(doc,load(ROOT/'data/semicon'/(doc['id']+'.json'),{}))
                self.assertEqual(doc['unit'],spec.get('currency','KRW')+' 백만')
                self.assertFalse(doc['span_gaps'])
                for view in doc['series_views'].values():
                    for points in view['series'].values():
                        self.assertTrue(any(v is not None for _,v in points))
                        self.assertEqual([d for d,_ in points],sorted({d for d,_ in points}))
                        self.assertLessEqual(points[-1][0],today())
        gross=docs['company_osat_ase_capex'];net=docs['company_osat_ase_net_ppe_cash']
        self.assertEqual(set(gross['series_views']),{'annual'})
        self.assertEqual(gross['default_view'],'annual')
        self.assertEqual(set(net['series_views']),{'quarter'})
        self.assertIn('순현금지출',net['name'])
        self.assertIn('2018',self.meta['global_companies']['ase']['note'])

    def test_failed_refresh_retains_successful_periods_and_flags_source(self):
        with TemporaryDirectory() as directory:
            state=Path(directory)/'state.json';state.write_text(STATE.read_text(encoding='utf8'),encoding='utf8')
            real_load=load
            # Save outputs in a temporary directory; source/issuer failures must
            # never replace an existing history with empty or fabricated values.
            with patch('fetch_semicon_osat.STATE',state),patch('fetch_semicon_osat.OUT',Path(directory)),patch('fetch_semicon_osat.collect_dart',side_effect=ValueError('offline')),patch('fetch_semicon_osat.requests.Session.get',side_effect=requests.ConnectionError('offline')):
                refreshed=collect(refresh=True)
            for key,prior in self.state['companies'].items():
                actual=refreshed['companies'][key]
                self.assertEqual(actual['rows'],prior['rows'])
                self.assertEqual(actual['annual'],prior['annual'])
                self.assertFalse(actual['ok'])

if __name__=='__main__':unittest.main()
