import copy
import json
import unittest
from pathlib import Path

from offshore_drilling import (ROOT, OUT, MANUAL, COMPANIES, build_documents, contract,
    coverage, date_range, parse_sec_financials, parse_market, rig, sec_quarters, snapshot)
from fetch_offshore_drilling import apply_curated

SOURCE={'url':'https://example.com/report.pdf','title':'Issuer report','as_of':'2026-08-05'}


class OffshoreTests(unittest.TestCase):
    def test_date_precision_is_not_invented(self):
        month=date_range('Feb-28');quarter=date_range('Q3-29')
        self.assertEqual((month['min'],month['max'],month['precision']),('2028-02-01','2028-02-29','month'))
        self.assertEqual((quarter['min'],quarter['max'],quarter['precision']),('2029-07-01','2029-09-30','quarter'))
        self.assertIsNone(date_range('Available')['min'])
        self.assertIsNone(date_range('undisclosed')['min'])

    def test_contract_rate_missing_is_not_zero_or_tcv_division(self):
        c=contract('r','client','Brazil','Jan-27','Jan-29',note='TCV $350m',source=SOURCE)
        self.assertIsNone(c['dayrate_usd'])
        with self.assertRaises(ValueError):contract('r',start='Feb-28',end='Jan-27')
        with self.assertRaises(ValueError):contract('r',rate=0)

    def test_options_and_unknown_dates_do_not_inflate_coverage(self):
        r=rig('transocean','Example','drillship',SOURCE,status_reported='Contracted')
        r['contracts']=[contract(r['id'],start='2026-08-05',end='2027-08-05',kind='option')]
        self.assertIsNone(coverage(r,'2026-08-05',12))
        r['contracts'][0]['kind']='firm'
        self.assertEqual(coverage(r,'2026-08-05',12),100)
        r['contracts']+=copy.deepcopy(r['contracts'])
        self.assertEqual(coverage(r,'2026-08-05',12),100)
        r['contracts'][0]['start']=date_range('Aug-26');r['contracts'][1]['start']=date_range('Aug-26')
        self.assertLess(coverage(r,'2026-08-05',12),100)

    def test_snapshot_is_as_of_disclosure_not_todays_actual_work(self):
        r=rig('transocean','Example','drillship',SOURCE,location='USGOM')
        r['contracts']=[contract(r['id'],'A','Brazil','Jan-26','Sep-26',300000),contract(r['id'],'B','Angola','Jan-27','Jan-28',400000)]
        current=snapshot(r,'2026-10-24')
        self.assertEqual(current['current_contract']['customer'],'A')
        self.assertEqual(current['as_of'],'2026-08-05')
        self.assertEqual(current['location'],'Brazil')
        r['retired']=True
        self.assertEqual(snapshot(r,'2026-10-24')['status'],'매각·퇴역')

    def test_quarterly_cumulative_cashflow_and_partial_quarters(self):
        def f(start,end,val,accn='a'):
            return {'start':start,'end':end,'val':val*1e6,'filed':'2026-08-01','accn':accn,'form':'10-Q'}
        payload={'facts':{'us-gaap':{'Cash':{'units':{'USD':[
            f('2026-01-01','2026-03-31',110),f('2026-01-01','2026-06-30',200,'b'),
            f('2026-04-06','2026-06-30',500,'partial')]}}}}}
        rows=sec_quarters(payload,'us-gaap','Cash')
        self.assertEqual(rows['2026-06-30']['value'],90)
        self.assertEqual(rows['2026-06-30']['prior_accn'],'a')

    def test_total_revenue_tag_over_contract_revenue_subtotal(self):
        def fact(v):return {'units':{'USD':[{'start':'2026-04-01','end':'2026-06-30','val':v*1e6,'form':'10-Q','filed':'2026-08-01'}]}}
        payload={'facts':{'us-gaap':{'Revenues':fact(539.2),'RevenueFromContractWithCustomerExcludingAssessedTax':fact(3.1)}}}
        rows=parse_sec_financials(payload)
        self.assertEqual(rows[0]['revenue'],539.2)
        self.assertNotIn('fcf',rows[0])

    def test_market_dates_follow_activity_month_and_public_counts(self):
        statements=[]
        for month in ('July','August'):
            for typ,c,a,s in [('jackup',382,56,52),('semisubmersible',59,13,8),('drillship',80,8,9)]:
                statements.append(f'The global committed {typ} count increased by one to {c} units in {month}. Marketed available and cold-stacked counts now stand at {a} and {s} cold-stacked rigs. Offshore Field')
        # Match the publisher's own available phrase, including number words.
        text=' '.join(statements).replace('Marketed available and cold-stacked counts now stand at','Marketed available and cold-stacked counts now stand at').replace('and 8 cold','and eight cold')
        rows=parse_market(text.encode(),year=2026)
        self.assertEqual(len(rows),6)
        self.assertEqual(rows[-1]['date'],'2026-08-31')
        jack=next(r for r in rows if r['type']=='jackup')
        self.assertEqual(jack['marketed'],438)
        self.assertEqual(jack['total'],490)

    def test_curated_merge_is_idempotent_and_preserves_original_sources(self):
        curated=json.loads((MANUAL/'curated.json').read_text(encoding='utf8'))
        state={'fleets':{k:{'rows':[]} for k in COMPANIES}}
        apply_curated(state,curated);first=copy.deepcopy(state);apply_curated(state,curated)
        self.assertEqual(state,first)
        jv=next(r for r in state['fleets']['borr']['rows'] if r['name']=='Oberon')
        self.assertEqual(jv['ownership_pct'],50)
        self.assertEqual(jv['owner_group'],'BC Ventures')

    def test_published_corpus_is_unique_and_traceable(self):
        fleet=json.loads((OUT/'offshore_fleet.json').read_text(encoding='utf8'))
        rows=fleet['rows'];self.assertEqual(set(COMPANIES),{r['company'] for r in rows})
        self.assertGreater(len(rows),150)
        self.assertEqual(len(rows),len({r['id'] for r in rows}))
        for r in rows:
            self.assertTrue(r['sources'])
            for c in r['contracts']:
                self.assertIn(c['kind'],('firm','option','loa','contingent','maintenance'))
                self.assertIsNotNone(c['source'])
                if c['dayrate_usd'] is not None:self.assertGreater(c['dayrate_usd'],10000)
        kg1=next(r for r in rows if r['name']=='Dhirubhai Deepwater KG1')
        self.assertEqual(kg1['company'],'transocean')
        atlas=next(r for r in rows if r['name']=='Deepwater Atlas')
        self.assertTrue(any(c['kind']=='contingent' for c in atlas['contracts']))
        if atlas['as_of']=='2026-08-05':self.assertEqual(atlas['current_contract']['dayrate_usd'],580000)
        self.assertTrue(next(r for r in rows if r['name']=='VALARIS MS-1')['retired'])

    def test_company_financial_anchors_and_missing_values(self):
        doc=json.loads((OUT/'offshore_financials.json').read_text(encoding='utf8'))
        for c in doc['companies']:
            self.assertEqual(len(c['quarters']),len({r['date'] for r in c['quarters']}))
            latest=next(r for r in c['quarters'] if r['date']=='2026-06-30')
            self.assertAlmostEqual(latest['revenue'],{'transocean':966,'valaris':539.2,'noble':719.688,'seadrill':449,'odfjell':250.6,'borr':232.3}[c['id']],places=3)
            self.assertGreater(latest['ebitda'],0)
            for r in c['quarters']:
                if r.get('fcf') is not None and r.get('capex') is not None:
                    self.assertAlmostEqual(r['fcf'],r['operating_cash']-r['capex'],places=3)

    def test_rebuild_preserves_financial_precision_over_rounded_supplement(self):
        curated=json.loads((MANUAL/'curated.json').read_text(encoding='utf8'))
        state={'financials':{'noble':{'rows':[{'date':'2026-06-30','revenue':719.688}]}},'financial_supplements':curated['financial_supplements']}
        doc=build_documents(state)['offshore_financials']
        last=next(c for c in doc['companies'] if c['id']=='noble')['quarters'][-1]
        self.assertEqual(last['revenue'],719.688)
        self.assertEqual(last['ebitda'],212)

    def test_all_catalog_paths_exist_and_routes_are_separate(self):
        catalog=json.loads((ROOT/'data/catalog.json').read_text(encoding='utf8'))
        industry=next(i for i in catalog['industries'] if i['id']=='oil')
        offshore=next(t for t in industry['tabs'] if t['id']=='offshore')
        self.assertEqual({t['id'] for t in offshore['views']},{'market','fleet','contracts','financials'})
        for section in industry['sections']:
            if section['tab']!='offshore':continue
            self.assertEqual(section['data_industry'],'offshore')
            for indicator in section['indicators']:self.assertTrue((OUT/(indicator+'.json')).is_file())
        self.assertTrue(next(i for i in catalog['industries'] if i['id']=='natgas'))


if __name__=='__main__':unittest.main()
