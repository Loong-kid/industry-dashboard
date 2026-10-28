import copy
import json
from pathlib import Path
import unittest

from lng_carrier_sources import accounts,annual_facts,source_rows
from fetch_lng_carriers import document,ROOT


class CarrierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources=json.loads((ROOT/'manual/lng-carriers/reports.json').read_text(encoding='utf8'))
        cls.meta=json.loads((ROOT/'manual/lng-carriers/companies.json').read_text(encoding='utf8'))

    def test_latest_uses_actual_quarters_not_ytd_or_parent_net_income(self):
        for company,expected in [('flng',[106.799,59.468,44.851]),('glng',[130.479,64.44,55.835])]:
            rows,_=accounts([s for s in self.sources if s['company']==company],[],'2026-10-28')
            row=next(r for r in rows if r['kind']=='quarter' and r['date']=='2026-06-30')
            for metric,value in zip(['revenue','profit','netincome'],expected):self.assertAlmostEqual(row[metric],value)
            self.assertFalse(any(r['kind']=='quarter' and r['date']=='2026-09-30' for r in rows))

    def test_reported_zero_and_signed_development_losses_are_preserved(self):
        rows,_=accounts([s for s in self.sources if s['company']=='flng'],[],'2026-10-28')
        a=next(r for r in rows if r['kind']=='annual' and r['year']==2014)
        self.assertEqual(a['revenue'],0)
        self.assertLess(a['profit'],0)
        self.assertLess(a['netincome'],0)
        q1=next(r for r in rows if r['kind']=='quarter' and r['date']=='2014-03-31')
        self.assertIn('components',q1['refs']['profit'])

    def test_annual_audit_retains_original_year_scope_and_total_nci(self):
        def f(value,filed,acc):return dict(start='2025-01-01',end='2025-12-31',val=value,form='20-F',filed=filed,accn=acc)
        tags={'RevenueFromContractWithCustomerExcludingAssessedTax':100e6,'OperatingIncomeLoss':10e6,'ProfitLoss':8e6,'NetIncomeLoss':5e6}
        payload=dict(cik=1207179,facts={'us-gaap':{tag:dict(units={'USD':[f(v,'2026-03-26','a'),f(v/2,'2027-03-26','b')]}) for tag,v in tags.items()}})
        r=annual_facts(payload,self.meta['glng'],'2028-01-01')[0]
        self.assertEqual((r['revenue'],r['profit'],r['netincome']),(100,10,8))
        self.assertEqual(r['refs']['netincome']['filed'],'2026-03-26')
        with self.assertRaises(ValueError):annual_facts(payload,self.meta['flng'],'2028-01-01')

    def test_audit_adjustment_is_disclosed_and_not_spread_over_quarters(self):
        own=[s for s in self.sources if s['company']=='glng' and s['year']==2025]
        rows,_=accounts(own,[],'2026-10-28');annual=copy.deepcopy(next(r for r in rows if r['kind']=='annual'))
        annual['netincome']+=7
        fresh,issues=accounts(own,[annual],'2026-10-28')
        self.assertTrue(any(i['metric']=='netincome' for i in issues))
        self.assertEqual([r['netincome'] for r in rows if r['kind']=='quarter'],[r['netincome'] for r in fresh if r['kind']=='quarter'])

    def test_future_filing_and_unreviewed_scale_are_rejected(self):
        source=copy.deepcopy(self.sources[0]);source['filed']='2099-01-01'
        self.assertEqual(source_rows(source,'2026-10-28'),[])
        source['filed']='2026-08-19';source['scale_to_millions']=1
        with self.assertRaises(ValueError):source_rows(source,'2026-10-28')

    def test_six_cards_connected_inside_existing_price_lng_tab(self):
        catalog=json.loads((ROOT/'data/catalog.json').read_text(encoding='utf8'))
        gas=next(i for i in catalog['industries'] if i['id']=='natgas')
        sections=[s for s in gas['sections'] if any(id.startswith('carrier_') for id in s.get('indicators',[]))]
        self.assertEqual(len(sections),2)
        self.assertTrue(all(s['tab']=='overview' and s['layout']=='financial' for s in sections))
        for section in sections:
            for id in section['indicators']:self.assertTrue((ROOT/'data/natgas'/f'{id}.json').exists())
        workflow=(ROOT/'.github/workflows/update-natgas.yml').read_text(encoding='utf8')
        self.assertIn('lng_carriers:',workflow);self.assertNotIn('needs:',workflow)


if __name__=='__main__':unittest.main()
