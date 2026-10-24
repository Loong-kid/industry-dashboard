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

    def test_wrong_entity_and_future_filing_are_rejected(self):
        payload=fixture()
        with self.assertRaises(ValueError):cpu.parse_facts(payload,cpu.COMPANIES['amd'],'2026-10-25')
        with self.assertRaises(ValueError):cpu.parse_facts(payload,cpu.COMPANIES['intel'],'2026-07-23')

    def test_real_issuer_financial_anchors_and_history(self):
        expected={'intel':(50,'2014-03-29',16128,1796,2556),
                  'amd':(50,'2014-03-29',11536,1990,808),
                  'arm':(16,'2022-09-30',1289,91,197)}
        for key,(count,first,revenue,profit,capex) in expected.items():
            rows=self.state['companies'][key]['rows']
            self.assertGreaterEqual(len(rows),count)
            self.assertEqual(rows[0]['date'],first)
            anchor=next(r for r in rows if r['date']==('2026-06-30' if key=='arm' else '2026-06-27'))
            self.assertEqual((anchor['revenue'],anchor['profit'],anchor['capex']),(revenue,profit,capex))
            self.assertEqual(len(rows),len({(r['year'],r['quarter']) for r in rows}))
        intel=next(r for r in self.state['companies']['intel']['rows'] if r['date']=='2016-12-31')
        self.assertEqual((intel['quarter'],intel['revenue'],intel['profit'],intel['capex']),(4,16374,4526,3530))

    def test_documents_and_navigation_preserve_scope_and_fiscal_labels(self):
        catalog=cpu.load(ROOT/'data/catalog.json',{})
        semicon=next(i for i in catalog['industries'] if i['id']=='semicon')
        self.assertEqual([g['id'] for g in semicon['groups']],['memory','foundry','cpu','ssd','materials'])
        linked={id for section in semicon['sections'] if section.get('tab')=='cpu' for id in section['indicators']}
        docs={}
        for key,cohort in self.state['companies'].items():docs.update(cpu.build_company(key,cohort))
        docs.update(cpu.build_segments(cpu.load(ROOT/'manual/cpu_segments.json',{})))
        self.assertEqual(set(docs),linked)
        self.assertEqual(len(docs),12)
        for id,doc in docs.items():
            self.assertEqual(doc,cpu.load(ROOT/f'data/semicon/{id}.json',{}))
            self.assertFalse(doc['span_gaps'])
        arm=docs['company_arm_revenue']
        self.assertEqual(arm['period_labels']['2026-06-30'],'FY2027 Q1')
        self.assertEqual(arm['comparison_dates']['2026-06-30']['quarter_ago'],'2026-03-31')
        self.assertIn('GPU',docs['company_amd_business']['description'])
        self.assertTrue(any(v is None for d,v in docs['company_intel_business']['series']['CCPG · 클라이언트·Physical AI']))

    def test_failure_isolated_and_success_date_retained(self):
        class Response:
            content=b'{}'
            def raise_for_status(self):pass
            def json(self):return {}
        class Session:
            headers={}
            def get(self,*args,**kwargs):return Response()
        def parsed(payload,company,asof):
            if company['cik']==2488:raise ValueError('changed source')
            key='intel' if company['cik']==50863 else 'arm'
            return copy.deepcopy(self.state['companies'][key]['rows'])
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)/'output'
            prior=copy.deepcopy(self.state)
            prior['companies']['amd']['fetched']='2026-10-24'
            cpu.save(out/'cpu_state.json',prior)
            with patch.object(cpu,'OUT',out),patch.object(cpu,'CACHE',Path(folder)/'cache'),patch.object(cpu,'today',return_value='2026-10-25'),patch.object(cpu.requests,'Session',Session),patch.object(cpu,'parse_facts',side_effect=parsed),patch.object(cpu.time,'sleep'):
                cpu.collect()
            result=cpu.load(out/'cpu_state.json',{})
            self.assertFalse(result['companies']['amd']['ok'])
            self.assertEqual(result['companies']['amd']['fetched'],'2026-10-24')
            self.assertEqual(result['companies']['amd']['rows'],prior['companies']['amd']['rows'])
            self.assertTrue(result['companies']['intel']['ok'])
            self.assertFalse(cpu.load(out/'company_amd_revenue.json',{})['collection_status']['ok'])


if __name__=='__main__':unittest.main()
