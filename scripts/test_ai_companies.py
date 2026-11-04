import copy
import json
import unittest
from build_ai_companies import ROOT, SOURCE, OUTPUT, build, validate


class AICompanyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc=json.loads(SOURCE.read_text(encoding='utf-8'))

    def test_reviewed_document_is_reproducible(self):
        self.assertEqual(build(self.doc),json.loads(OUTPUT.read_text(encoding='utf-8')))
        self.assertEqual([len(self.doc[k]) for k in ['sources','arr','projects','events']],[26,11,12,26])
        self.assertTrue(self.doc['manual'])

    def test_monthly_annualization_is_distinct_from_reported_arr(self):
        derived=[r for r in self.doc['arr'] if r['basis']=='monthly_annualized']
        self.assertEqual(len(derived),1)
        self.assertEqual(derived[0]['usd_bn'],2*12)
        self.assertEqual(derived[0]['source_ids'],['oa_funding'])
        self.assertEqual(len([r for r in self.doc['arr'] if r['basis']=='reported']),10)
        may=next(r for r in self.doc['arr'] if r['id']=='an-may26')
        self.assertEqual((may['qualifier'],may['period'],may['announced_on']),('gt','2026-05','2026-05-28'))
        self.assertTrue(all(r['scope']=='company' for r in self.doc['arr']))

    def test_compute_is_not_grid_power_and_unknown_is_not_zero(self):
        self.assertTrue(all(c['grid_total_mw'] is None for c in self.doc['companies']))
        self.assertEqual([r['mw'] for r in self.doc['compute_history']],[200,600,1900])
        self.assertTrue(all(r['basis']=='available_compute' for r in self.doc['compute_history']))
        projects={r['id']:r for r in self.doc['projects']}
        ab=projects['abilene']
        self.assertEqual((ab['planned_mw'],ab['known_mw'],ab['delivery_pct']),(1200,200,75))
        self.assertEqual(ab['known_basis'],'energized_buildings')
        self.assertEqual(ab['known_as_of'],'2026-03-27')
        self.assertIsNone(ab['grid_mw'])
        self.assertEqual(projects['shackelford']['known_basis'],'power_available')
        self.assertIsNone(projects['lordstown']['planned_mw'])
        self.assertIsNone(projects['fluid-tx']['known_mw'])
        self.assertEqual(projects['colossus']['status'],'이용 계약')
        self.assertEqual(projects['colossus']['plan_basis'],'contracted_compute')
        self.assertIsNone(projects['colossus']['known_mw'])

    def test_overlapping_contracts_are_never_additive(self):
        self.assertTrue(all(r['additive'] is False for r in self.doc['events']))
        google=[r for r in self.doc['events'] if r['overlap_group']=='anthropic-google']
        self.assertEqual(len(google),3)
        self.assertEqual(google[-1]['capacity_mw'],5000)
        shared=next(r for r in self.doc['events'] if r['id']=='oa-pair')
        self.assertIsNone(shared['project_id'])
        self.assertEqual(shared['capacity_basis'],'shared_sites_planned')

    def test_validation_rejects_unknown_sources_and_negative_capacity(self):
        bad=copy.deepcopy(self.doc);bad['arr'][0]['source_ids']=['unknown']
        with self.assertRaises(AssertionError):validate(bad)
        bad=copy.deepcopy(self.doc);bad['projects'][0]['known_mw']=-1
        with self.assertRaises(AssertionError):validate(bad)
        bad=copy.deepcopy(self.doc);bad['events'][0]['additive']=True
        with self.assertRaises(AssertionError):validate(bad)

    def test_data_center_navigation_keeps_existing_views(self):
        catalog=json.loads((ROOT/'data/catalog.json').read_text(encoding='utf-8'))
        dc=next(i for i in catalog['industries'] if i['id']=='datacenter')
        section=next(s for s in dc['sections'] if s['tab']=='ai_companies')
        self.assertEqual(section['table_kind'],'ai_companies')
        self.assertEqual(section['indicators'],['dc_ai_companies'])
        self.assertEqual([t['id'] for t in dc['tabs']],['korea','us','ai_overview','ai_companies'])
        self.assertEqual([s['indicators'][0] for s in dc['sections'] if s['tab']=='ai_overview'],['dc_ai_overview','dc_ai_overview2'])


if __name__=='__main__':unittest.main()
