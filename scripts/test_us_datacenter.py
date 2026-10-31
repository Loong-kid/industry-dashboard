import copy,json,math,unittest
from pathlib import Path
from xml.etree import ElementTree as ET

from fetch_us_datacenter import ROOT,document,fiscal_payload,merge_business,extra_capex
from us_datacenter_sources import parse_instance,field_for


class HyperscalerTests(unittest.TestCase):
    def setUp(self):
        self.meta=json.loads((ROOT/'manual/us-datacenter/companies.json').read_text(encoding='utf8'))

    def test_native_cloud_facts_exclude_broader_software_and_azure_proxies(self):
        expected={'amzn':(45984000000,17773000000),'msft':(63900000000,None),'googl':(30709000000,11121000000),'orcl':(11607000000,None)}
        for key,(revenue,profit) in expected.items():
            filing=dict(filingDate='2026-10-30',accessionNumber='fixture',form='10-Q',url='https://www.sec.gov/fixture')
            raw=(ROOT/f'scripts/fixtures/us_datacenter/{key}.xml').read_bytes()
            fields=parse_instance(raw,key,self.meta[key],filing,'2026-10-31')
            end='2026-08-31' if key=='orcl' else '2026-09-30'
            r=next(r for r in fields['cloud_revenue'] if r['end']==end and r['start'] in ('2026-07-01','2026-06-01'))
            self.assertEqual(r['val'],revenue)
            if profit is None:self.assertNotIn('cloud_profit',fields)
            else:self.assertTrue(any(r['end']==end and r['val']==profit for r in fields['cloud_profit']))
            wrong=dict(self.meta[key],cik=1)
            with self.assertRaises(ValueError):parse_instance(raw,key,wrong,filing,'2026-10-31')
            self.assertEqual(parse_instance(raw,key,self.meta[key],filing,'2026-10-29'),{})
        self.assertIsNone(field_for('orcl','OperatingIncomeLoss',['orcl:CloudAndSoftwareBusinessMember']))
        self.assertIsNone(field_for('msft','OperatingIncomeLoss',['msft:AgentsAndInfraMember']))
        self.assertIsNone(field_for('msft','RevenueFromContractWithCustomerExcludingAssessedTax',['msft:AzureMember']))
        self.assertEqual(field_for('googl','OperatingIncomeLoss',['goog:GoogleCloudSegmentMember','us-gaap:OperatingSegmentsMember']),'cloud_profit')

    def test_ttm_is_not_a_fiscal_annual_and_cash_lease_basis_is_exact(self):
        annual=dict(start='2025-01-01',end='2025-12-31',val=100)
        ttm=dict(start='2025-04-01',end='2026-03-31',val=200)
        payload={'facts':{'us-gaap':{'PaymentsToAcquirePropertyPlantAndEquipment':{'units':{'USD':[annual,ttm]}}}}}
        filtered=fiscal_payload(payload,self.meta['amzn'])
        self.assertEqual(filtered['facts']['us-gaap']['PaymentsToAcquirePropertyPlantAndEquipment']['units']['USD'],[annual])
        self.assertEqual(len(payload['facts']['us-gaap']['PaymentsToAcquirePropertyPlantAndEquipment']['units']['USD']),2)
        r=dict(capex=10,lease_principal=3,refs={'capex':dict(start='2026-01-01',end='2026-03-31'),'lease_principal':dict(start='2026-01-01',end='2026-06-30')})
        extra_capex([r],self.meta['meta']);self.assertNotIn('capex_extra',r)
        r['refs']['lease_principal']['end']='2026-03-31';extra_capex([r],self.meta['meta']);self.assertEqual(r['capex_extra'],13)

    def test_cloud_ratio_requires_same_period_and_uses_revenue_weighting(self):
        base=dict(start='2025-01-01',date='2025-12-31',revenue=400,refs={'revenue':dict(start='2025-01-01',end='2025-12-31',filed='2026-02-01')})
        cloud=dict(start='2025-01-01',date='2025-12-31',cloud_revenue=130,refs={'cloud_revenue':dict(start='2025-01-01',end='2025-12-31',filed='2026-02-01')})
        self.assertEqual(merge_business([base],[cloud])[0]['cloud_share'],32.5)
        self.assertNotIn('cloud_share',merge_business([base],[dict(cloud,start='2025-04-01')])[0])

    def test_published_history_financial_views_sources_and_capex(self):
        state=json.loads((ROOT/'data/datacenter/us_hyperscalers_state.json').read_text(encoding='utf8'))
        anchors={'amzn':(201944,28076,77259),'msft':(92279,45915,39367),'googl':(127577,40576,51355),'orcl':(19345,6728,28499),'meta':(64601,12988,33942)}
        for key,c in state['companies'].items():
            self.assertEqual(len(c['rows']),len({(r['year'],r['quarter']) for r in c['rows']}))
            self.assertTrue(c['rows'][0]['date'].startswith('2014'))
            # Pin a verified historical period, not the latest row: a newly
            # reported quarter must be able to pass the daily postcheck.
            anchor_date='2026-08-31' if key=='orcl' else '2026-09-30'
            r=next(r for r in c['rows'] if r['date']==anchor_date)
            self.assertEqual(tuple(r[m] for m in ('revenue','profit','capex')),anchors[key])
            self.assertGreaterEqual(c['rows'][-1]['date'],anchor_date)
            for kind in ('rows','annual'):
                for r in c[kind]:
                    self.assertLessEqual(r['date'],c['checked'])
                    if 'cloud_share' in r:self.assertAlmostEqual(r['cloud_share'],r['cloud_revenue']/r['revenue']*100)
                    for metric,ref in r['refs'].items():
                        self.assertLessEqual(ref['filed'],c['checked']);self.assertTrue(ref['url'].startswith('https://www.sec.gov/'))
            for path in (ROOT/'data/datacenter').glob('us_dc_'+key+'_*.json'):
                metric=path.stem[len('us_dc_'+key+'_'):];d=json.loads(path.read_text(encoding='utf8'))
                self.assertEqual(d,document(key,metric,self.meta[key],c))
                if d.get('disclosure_status')=='not_disclosed':
                    self.assertNotIn('series',d);continue
                self.assertIn('annual',d['series_views']);self.assertFalse(d['span_gaps'])
                for view in d['series_views'].values():
                    self.assertTrue(any(v is not None for day,v in next(iter(view['series'].values()))))
        for key,value in [('msft',44559),('meta',34906)]:
            r=next(r for r in state['companies'][key]['rows'] if r['date']=='2026-09-30')
            self.assertEqual(r['capex_extra'],value)
        self.assertTrue(any(r.get('cloud_profit',1)<0 for r in state['companies']['googl']['rows']))

    def test_countries_keep_korea_tables_and_29_us_cards(self):
        catalog=json.loads((ROOT/'data/catalog.json').read_text(encoding='utf8'))
        dc=next(i for i in catalog['industries'] if i['id']=='datacenter')
        self.assertEqual([(t['id'],t['name']) for t in dc['tabs']],[('korea','한국'),('us','미국')])
        korea=[s for s in dc['sections'] if s['tab']=='korea'];us=[s for s in dc['sections'] if s['tab']=='us']
        self.assertEqual(len(korea),5);self.assertEqual({s.get('table_kind') for s in korea if s.get('type')=='table'},{'dc_summary','dc_facilities','dc_changes'})
        self.assertEqual([len(s['indicators']) for s in us],[6,7,6,6,4])
        ids=[i for s in us for i in s['indicators']];self.assertEqual(len(set(ids)),29)
        for id in ids:self.assertTrue((ROOT/f'data/datacenter/{id}.json').exists())


if __name__=='__main__':unittest.main()
