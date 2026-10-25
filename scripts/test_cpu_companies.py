import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import fetch_cpu_companies as cpu

ROOT=Path(__file__).resolve().parents[1]


def fact(start,end,value,filed='2026-07-24',accn='0000050863-26-000157',form='10-Q'):
    return dict(start=start,end=end,val=value*1e6,filed=filed,accn=accn,form=form)


def fixture():
    facts={}
    for metric,tags in cpu.TAGS.items():
        value=10 if metric=='revenue' else -2 if metric=='profit' else 0
        facts[tags[0]]=dict(units={'USD':[fact('2025-12-28','2026-03-28',value),fact('2025-12-28','2026-06-27',value+7)]})
    return dict(cik=50863,facts={'us-gaap':facts})


class CpuCompanies(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state=cpu.load(ROOT/'data/semicon/cpu_state.json',{})

    def test_fiscal_ytd_difference_preserves_zero_and_loss(self):
        rows=cpu.parse_facts(fixture(),cpu.COMPANIES['intel'],'2026-10-25')
        self.assertEqual([(r['quarter'],r['revenue'],r['profit'],r['capex']) for r in rows],[(1,10,-2,0),(2,7,7,7)])
        self.assertEqual(rows[-1]['refs']['capex']['components'][1]['start'],'2025-12-28')

    def test_annual_restatement_does_not_change_original_q4_difference(self):
        payload=fixture()
        for tag,meta in payload['facts']['us-gaap'].items():
            meta['units']['USD']=[fact('2025-01-01','2025-09-30',30,filed='2025-10-25'),
                fact('2025-01-01','2025-12-31',40,filed='2026-01-25',form='10-K'),
                fact('2025-01-01','2025-12-31',100,filed='2026-03-25',form='10-K/A')]
        rows=cpu.parse_facts(payload,cpu.COMPANIES['intel'],'2026-10-25')
        self.assertEqual(rows[-1]['revenue'],10)
        self.assertEqual(rows[-1]['refs']['revenue']['filed'],'2026-01-25')

    def test_different_fiscal_year_is_never_subtracted(self):
        payload=fixture()
        capex=payload['facts']['us-gaap'][cpu.TAGS['capex'][0]]['units']['USD']
        capex[0]['start']='2024-12-29'
        with self.assertRaises(ValueError):
            cpu.parse_facts(payload,cpu.COMPANIES['intel'],'2026-10-25')

    def test_reported_annual_uses_latest_filing_and_excludes_partial_year(self):
        payload=fixture()
        for meta in payload['facts']['us-gaap'].values():
            meta['units']['USD']=[
                fact('2025-01-01','2025-12-31',40,filed='2026-01-25',form='10-K'),
                fact('2025-01-01','2025-12-31',42,filed='2026-03-25',form='10-K/A'),
                fact('2026-01-01','2026-09-30',35,filed='2026-10-25'),
                fact('2026-01-01','2026-12-31',99,filed='2027-01-25',form='10-K')]
        rows=cpu.parse_annual(payload,cpu.COMPANIES['intel'],'2026-10-25')
        self.assertEqual([(r['year'],r['revenue']) for r in rows],[(2025,42)])
        self.assertEqual(rows[0]['refs']['revenue']['filed'],'2026-03-25')

    def test_wrong_entity_and_future_filing_are_rejected(self):
        payload=fixture()
        with self.assertRaises(ValueError):cpu.parse_facts(payload,cpu.COMPANIES['amd'],'2026-10-25')
        with self.assertRaises(ValueError):cpu.parse_facts(payload,cpu.COMPANIES['intel'],'2026-07-23')

    def test_real_issuer_financial_anchors_and_history(self):
        expected={'intel':(50,'2014-03-29',16128,1796,2556),
                  'amd':(50,'2014-03-29',11536,1990,808),
                  'arm':(16,'2022-09-30',1289,91,197),
                  'qualcomm':(50,'2014-03-30',9947,1626,496),
                  'apple':(50,'2014-03-29',109417,35695,2455)}
        for key,(count,first,revenue,profit,capex) in expected.items():
            rows=self.state['companies'][key]['rows']
            self.assertGreaterEqual(len(rows),count)
            self.assertEqual(rows[0]['date'],first)
            end={'arm':'2026-06-30','qualcomm':'2026-06-28'}.get(key,'2026-06-27')
            anchor=next(r for r in rows if r['date']==end)
            self.assertEqual((anchor['revenue'],anchor['profit'],anchor['capex']),(revenue,profit,capex))
            self.assertEqual(len(rows),len({(r['year'],r['quarter']) for r in rows}))
        intel=next(r for r in self.state['companies']['intel']['rows'] if r['date']=='2016-12-31')
        self.assertEqual((intel['quarter'],intel['revenue'],intel['profit'],intel['capex']),(4,16374,4526,3530))

    def test_documents_and_navigation_preserve_scope_and_fiscal_labels(self):
        catalog=cpu.load(ROOT/'data/catalog.json',{})
        semicon=next(i for i in catalog['industries'] if i['id']=='semicon')
        self.assertEqual([g['id'] for g in semicon['groups']],['memory','foundry','cpu','gpu','ai_asic','ssd','materials'])
        linked={id for section in semicon['sections'] if section.get('tab')=='cpu' and section.get('type')!='table' for id in section['indicators']}
        docs={}
        for key,cohort in self.state['companies'].items():docs.update(cpu.build_company(key,cohort))
        docs.update(cpu.build_business_history(self.state['business'],cpu.load(ROOT/'manual/cpu_segments.json',{})))
        self.assertEqual(set(docs),linked)
        self.assertEqual(len(docs),21)
        for id,doc in docs.items():
            self.assertEqual(doc,cpu.load(ROOT/f'data/semicon/{id}.json',{}))
            self.assertFalse(doc['span_gaps'])
        arm=docs['company_arm_revenue']
        self.assertEqual(arm['period_labels']['2026-06-30'],'FY2027 Q1')
        self.assertEqual(arm['comparison_dates']['2026-06-30']['quarter_ago'],'2026-03-31')
        self.assertIn('GPU',docs['company_amd_business']['description'])
        self.assertTrue(all(v is not None for d,v in docs['company_intel_business']['series']['CCPG · 클라이언트·Physical AI']))
        apple=docs['company_apple_revenue']
        self.assertEqual(apple['period_labels']['2025-12-27'],'FY2026 Q1')
        self.assertEqual(apple['comparison_dates']['2025-12-27']['quarter_ago'],'2025-09-27')
        self.assertIn('Apple Silicon 별도 실적 미공개',apple['description'])
        self.assertIn('Apple Silicon 칩의 별도',docs['company_apple_business']['description'])
        self.assertIn('회사 공시 CAPEX',docs['company_qualcomm_capex']['series'])
        self.assertIn('PC용 Snapdragon 매출로 해석하지 않습니다',docs['company_qualcomm_business']['description'])

    def test_qualcomm_uses_issuer_capex_tag_instead_of_unrelated_ppe(self):
        payload=fixture();payload['cik']=804328
        for meta in payload['facts']['us-gaap'].values():
            for i,r in enumerate(meta['units']['USD']):
                r['start']='2025-09-29'
                r['end']='2025-12-28' if i==0 else '2026-03-29'
        payload['facts']['us-gaap']['PaymentsToAcquireProductiveAssets']=dict(units={'USD':[
            fact('2025-09-29','2025-12-28',1),fact('2025-09-29','2026-03-29',3)]})
        rows=cpu.parse_facts(payload,cpu.COMPANIES['qualcomm'],'2026-10-25')
        self.assertEqual([r['capex'] for r in rows],[1,2])
        self.assertTrue(all(r['refs']['capex']['tag']=='us-gaap:PaymentsToAcquireProductiveAssets' for r in rows))

    def test_failure_isolated_and_success_date_retained(self):
        real_parse,real_annual=cpu.parse_facts,cpu.parse_annual
        class Response:
            content=b'{}'
            def raise_for_status(self):pass
            def json(self):return {}
        class Session:
            headers={}
            def get(self,*args,**kwargs):return Response()
        def parsed(payload,company,asof,tags_by_metric=None):
            if tags_by_metric:return real_parse(payload,company,asof,tags_by_metric)
            if company['cik']==2488:raise ValueError('changed source')
            key=next(key for key,meta in cpu.COMPANIES.items() if meta['cik']==company['cik'])
            return copy.deepcopy(self.state['companies'][key]['rows'])
        def annual(payload,company,asof,tags_by_metric=None):
            if tags_by_metric:return real_annual(payload,company,asof,tags_by_metric)
            key=next(key for key,meta in cpu.COMPANIES.items() if meta['cik']==company['cik'])
            return copy.deepcopy(self.state['companies'][key]['annual'])
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)/'output'
            prior=copy.deepcopy(self.state)
            prior['companies']['amd']['fetched']='2026-10-24'
            cpu.save(out/'cpu_state.json',prior)
            with patch.object(cpu,'OUT',out),patch.object(cpu,'CACHE',Path(folder)/'cache'),patch.object(cpu,'today',return_value='2026-10-25'),patch.object(cpu.requests,'Session',Session),patch.object(cpu,'parse_facts',side_effect=parsed),patch.object(cpu,'parse_annual',side_effect=annual),patch.object(cpu,'collect_business',return_value=self.state['business']),patch.object(cpu.time,'sleep'):
                cpu.collect()
            result=cpu.load(out/'cpu_state.json',{})
            self.assertFalse(result['companies']['amd']['ok'])
            self.assertEqual(result['companies']['amd']['fetched'],'2026-10-24')
            self.assertEqual(result['companies']['amd']['rows'],prior['companies']['amd']['rows'])
            self.assertTrue(result['companies']['intel']['ok'])
            self.assertFalse(cpu.load(out/'company_amd_revenue.json',{})['collection_status']['ok'])


if __name__=='__main__':unittest.main()
