"""Cleaning services scope, revenue tag changes and original financial histories."""
import copy
import json
import unittest
from unittest.mock import patch
import requests
from fetch_semicon_cleaning import ROOT, META, STATE, build, collect
from fetch_cpu_companies import load, parse_facts, today
from fetch_rings import validate


class CleaningAccounts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.meta=load(META,{})
        cls.state=load(STATE,{})

    def test_service_peers_are_distinct_from_wafer_cleaning_equipment(self):
        domestic=self.meta['companies'];overseas=self.meta['global_companies']
        self.assertEqual({c['ticker'] for c in domestic.values()},{'183300','114810','074600'})
        self.assertEqual({c['ticker'] for c in overseas.values()},{'UCTT','NPO'})
        catalog=load(ROOT/'data/catalog.json',{})
        semicon=next(i for i in catalog['industries'] if i['id']=='semicon')
        self.assertEqual(next(c for c in semicon['material_categories'] if c['id']=='cleaning')['default_tab'],'cleaning_summary')
        self.assertEqual(next(c for c in semicon['material_categories'] if c['id']=='equipment')['default_tab'],'equipment_summary')
        sections=[s for s in semicon['sections'] if s['tab']=='cleaning_summary']
        firms={**domestic,**overseas}
        self.assertEqual(sections[0]['valuation_companies'],['cleaning_'+k for k in firms])
        self.assertEqual(len(sections),6)
        for section,(key,spec) in zip(sections[1:],firms.items()):
            self.assertEqual(section['indicators'],[f'company_cleaning_{key}_{m}' for m in ('revenue','profit','capex')])
            self.assertEqual(section['valuation_company'],'cleaning_'+key)
            self.assertIn(spec['scope'],section['supply_note'])
        registry=load(ROOT/'manual/semicon-valuation/companies.json',[])
        for key in firms:
            selected=[c for c in registry if c['id']=='cleaning_'+key]
            self.assertEqual(len(selected),1)
            self.assertEqual(selected[0]['tabs'],['cleaning_summary'])
        self.assertIn('장비',self.meta['selection_basis'])
        self.assertIn('세정 단독',domestic['komico']['note'])

    def test_recent_sec_revenue_tags_do_not_truncate_history(self):
        for key,end,expected in [('uct','2026-09-25',759.0),('enpro','2026-06-30',338.8)]:
            fixture=load(ROOT/f'scripts/fixtures/semicon_cleaning/{key}_recent.json',{})
            rows=parse_facts(fixture,self.meta['global_companies'][key],today())
            self.assertEqual(rows[-1]['date'],end)
            self.assertAlmostEqual(rows[-1]['revenue'],expected)
            self.assertTrue(rows[-1]['refs']['revenue']['tag'].endswith('RevenueFromContractWithCustomerIncludingAssessedTax'))
            self.assertAlmostEqual(rows[-1]['capex'],19.5 if key=='uct' else 15.6)
            ref=rows[-1]['refs']['capex']
            self.assertEqual(len(ref['components']),2)
            self.assertEqual(ref['components'][0]['start'],ref['components'][1]['start'])

    def test_original_history_and_published_period_views(self):
        expected={**self.meta['companies'],**self.meta['global_companies']}
        self.assertEqual(set(self.state['companies']),set(expected))
        docs=build(self.meta,self.state)
        self.assertEqual(len(docs),15)
        for key,spec in expected.items():
            co=self.state['companies'][key]
            self.assertGreaterEqual(len(co['rows']),35)
            self.assertGreaterEqual(len(co['annual']),10)
            if key in self.meta['companies']:validate(co,today())
            for metric in ('revenue','profit','capex'):
                doc=docs[f'company_cleaning_{key}_{metric}']
                self.assertEqual(doc,load(ROOT/'data/semicon'/(doc['id']+'.json'),{}))
                self.assertEqual(doc['unit'],('KRW' if key in self.meta['companies'] else 'USD')+' 백만')
                self.assertEqual(set(doc['series_views']),{'quarter','annual'})
                self.assertTrue(doc['compact_tooltip'])
                for kind,field in [('quarter','rows'),('annual','annual')]:
                    view={**doc,**doc['series_views'][kind]}
                    points=dict(next(iter(view['series'].values())))
                    for row in co[field]:
                        self.assertEqual(points[row['date']],row.get(metric))
                        self.assertLessEqual(row['date'],today())
                        for ref in row.get('refs',{}).get(metric,{}).get('components',[]):
                            self.assertLessEqual(ref['filed'],today())
                            self.assertTrue(ref['url'].startswith(('https://dart.fss.or.kr/','https://www.sec.gov/')))
        self.assertNotIn('crtfc_key',json.dumps(self.state))

    def test_source_outage_preserves_all_verified_rows(self):
        prior=copy.deepcopy(self.state)
        with patch('fetch_semicon_cleaning.collect_originals',return_value={k:{'ok':False} for k in self.meta['companies']}),patch('fetch_semicon_cleaning.requests.Session') as session,patch('fetch_semicon_cleaning.save'):
            session.return_value.get.side_effect=requests.ConnectionError('test source outage')
            updated=collect(refresh=True)
        for key,co in prior['companies'].items():
            self.assertEqual(updated['companies'][key]['rows'],co['rows'])
            self.assertEqual(updated['companies'][key]['annual'],co['annual'])
            self.assertEqual(updated['companies'][key]['fetched'],co['fetched'])
            self.assertFalse(updated['companies'][key]['ok'])


if __name__=='__main__':unittest.main()
