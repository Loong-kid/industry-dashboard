import copy
import json
import unittest
from pathlib import Path

from fetch_mining import build_docs, collect_offline, validate_periods
from fetch_cpu_companies import today
from mining_financial_sources import html_statement_fields

ROOT=Path(__file__).resolve().parents[1]
META=json.loads((ROOT/'manual/mining/companies.json').read_bytes())
HISTORY=json.loads((ROOT/'data/commodities/mining_financial_history.json').read_bytes())


class MiningTests(unittest.TestCase):
    def test_rank_and_mix_denominators(self):
        self.assertEqual([c['id'] for c in META['companies']],['bhp','scco','rio','nem','zijin','fcx','grupo','aem','glen','barrick'])
        self.assertEqual([c['rank'] for c in META['companies']],list(range(1,11)))
        self.assertIn('Southern Copper',META['ownership_note'])
        for c in META['companies']:
            mix=c['mix'];self.assertTrue(mix['sources']);self.assertTrue(mix['basis'])
            self.assertAlmostEqual(sum(p['amount'] for p in mix['parts']),mix['denominator'],places=4)
            self.assertAlmostEqual(sum(p['percent'] for p in mix['parts']),100,places=5)
        # Gross-product and segment denominators are deliberately not group sales.
        by={c['id']:c for c in META['companies']}
        self.assertEqual(by['fcx']['mix']['denominator'],25940)
        self.assertEqual(by['glen']['mix']['denominator'],251297)
        self.assertEqual(by['zijin']['currency'],'CNY')

    def test_original_statement_anchors(self):
        expected={
          'bhp':(2026,58760,23869,9849),'scco':(2025,13420,7001.7,1325.3),
          'rio':(2025,57638,14936,12335),'nem':(2025,22669,10961,3035),
          'zijin':(2025,349079.082852,82110.135522,30982.297763),
          'fcx':(2025,25915,6518,4494),'grupo':(2025,18176.711,8641.014,2005.869),
          'aem':(2025,11907.851,6795.056,2418.2),'glen':(2025,247535,3050,5932),
          'barrick':(2025,16956,9032,3821),'ero':(2025,785.844,270.598,262.753)}
        for key,(year,*values) in expected.items():
            row=next(r for r in HISTORY[key]['annual'] if r['year']==year)
            for metric,value in zip(['revenue','profit','capex'],values):
                self.assertAlmostEqual(row[metric],value,places=5,msg=key+' '+metric)
        latest=next(r for r in HISTORY['ero']['rows'] if r['date']=='2026-06-30')
        self.assertAlmostEqual(latest['revenue'],284.313,places=5)
        self.assertAlmostEqual(latest['capex'],80.528,places=5)
        self.assertEqual(HISTORY['glen']['annual'][1]['revenue'],170497)
        fcx=next(r for r in HISTORY['fcx']['rows'] if r['date']=='2026-06-30')
        self.assertEqual(fcx['capex'],1104)

    def test_annual_and_quarter_views_keep_distinct_observations(self):
        docs=build_docs(META,HISTORY)
        for spec in META['companies']+[META['ero']]:
            for metric in ['revenue','profit','capex']:
                doc=docs[f"company_mining_{spec['id']}_{metric}"]
                saved=json.loads((ROOT/'data/commodities'/f"{doc['id']}.json").read_bytes())
                self.assertEqual(doc,saved)
                self.assertEqual(doc['unit'],spec['currency']+' 백만')
                self.assertFalse(doc['span_gaps'])
                self.assertTrue(doc['series_views']['annual']['annual_axis'])
                if spec.get('profit_calculated') and metric=='profit':self.assertIn('(계산)',doc['name'])
                if 'quarter' in doc['series_views']:
                    q=doc['series_views']['quarter'];a=doc['series_views']['annual']
                    self.assertEqual(q['frequency'],'quarterly')
                    self.assertNotEqual(q['series'],a['series'])
                    self.assertTrue(q['quarter_labels']);self.assertFalse(q['annual_axis'])
        self.assertNotIn('quarter',docs['company_mining_bhp_revenue']['series_views'])
        self.assertNotIn('quarter',docs['company_mining_zijin_revenue']['series_views'])

    def test_failure_preserves_values_and_success_date(self):
        failed=collect_offline(META,'2026-10-28',HISTORY,{})
        for key,co in failed.items():
            self.assertFalse(co['ok'])
            for field in ['annual','rows','halves','fetched']:self.assertEqual(co[field],HISTORY[key][field])
        docs=build_docs(META,failed)
        self.assertFalse(docs['company_mining_ero_revenue']['collection_status']['ok'])

    def test_no_future_missing_as_zero_or_duplicate_dates(self):
        for key,co in HISTORY.items():
            validate_periods(co,max(today(),'2026-10-28'))
            self.assertEqual(co['annual'],sorted(co['annual'],key=lambda x:x['date']))
        changed=copy.deepcopy(HISTORY['ero']);changed['annual'][-1]['revenue']=float('nan')
        with self.assertRaises(ValueError):validate_periods(changed,'2026-10-28')

    def test_interim_statement_is_not_mislabeled_as_an_annual(self):
        raw=b'''<html><table><tr><td>Revenues</td><td>284</td><td>163</td><td>547</td><td>288</td></tr>
          <tr><td>Operating profit</td><td>108</td><td>48</td><td>200</td><td>91</td></tr>
          <tr><td>Profit before income tax</td><td>1</td></tr><tr><td>Earnings per share</td><td>1</td></tr></table>
          <table><tr><td>Cash flows from operating activities</td></tr>
          <tr><td>Additions to mineral properties, plant and equipment</td><td>(80)</td><td>(66)</td><td>(136)</td><td>(122)</td></tr>
          <tr><td>Financing activities</td></tr></table></html>'''
        parsed=html_statement_fields(raw,'ero',dict(form='10-Q',date='2026-06-30'))
        self.assertEqual(parsed['revenue'][0]['start'],'2026-04-01')
        self.assertEqual(parsed['revenue'][0]['end'],'2026-06-30')
        self.assertEqual(parsed['capex'][0]['val'],136000)
        self.assertEqual(parsed['capex'][0]['start'],'2026-01-01')


if __name__=='__main__':unittest.main()
