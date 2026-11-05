import copy
import json
import math
import unittest
from unittest.mock import patch
from pathlib import Path

import pymupdf

from fetch_specialty_minerals import COMPANIES, ROOT, normalize_aa, statement_rows, today

FIXTURES=Path(__file__).parent/'fixtures/specialty'
ASOF='2026-11-06'

class SpecialtyTests(unittest.TestCase):
    def pdf(self,key):
        with pymupdf.open(FIXTURES/(key+'.pdf')) as document:
            return statement_rows(document,key,'https://issuer.example/financials.pdf',ASOF)

    def test_original_pdf_quarter_and_ytd_columns(self):
        expected={'alm':(42989000,16126000,36893000),'vnp':(136387000,18423000,21593000),'afm':(252707639,148408848,10138778)}
        for key,(revenue,profit,capex_ytd) in expected.items():
            rows=self.pdf(key)
            year=2026;month=9 if key=='vnp' else 6;end=f'{year}-{month:02d}-30'
            quarter_start='2026-07-01' if key=='vnp' else '2026-04-01'
            for metric,value in [('revenue',revenue),('profit',profit)]:
                actual=next(f for f in rows[metric] if f['start']==quarter_start and f['end']==end)
                self.assertEqual(actual['val'],value,(key,metric))
                self.assertTrue(actual['source_url'].startswith('https://issuer.example/'))
            ytd=next(f for f in rows['capex'] if f['start']=='2026-01-01' and f['end']==end)
            self.assertEqual(ytd['val'],capex_ytd,key)
            if key=='afm':self.assertTrue(all(f['end']<='2026-06-30' for facts in rows.values() for f in facts))

    def test_approval_date_prevents_future_report(self):
        with pymupdf.open(FIXTURES/'vnp.pdf') as doc:
            with self.assertRaises(ValueError):statement_rows(doc,'vnp','https://issuer.example/report.pdf','2026-10-31')

    def test_currency_change_fails_closed(self):
        with pymupdf.open(FIXTURES/'vnp.pdf') as doc:
            with self.assertRaisesRegex(ValueError,'currency'):statement_rows(doc,'alm','https://issuer.example/report.pdf',ASOF)

    def test_alcoa_subtotal_signs_and_same_accession(self):
        tags=['IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest','InterestExpense','NonoperatingIncomeExpense']
        fact=dict(start='2026-07-01',end='2026-09-30',accn='same',filed='2026-10-29',form='10-Q')
        payload={'facts':{'us-gaap':{t:{'units':{'USD':[dict(fact,val=v)]}} for t,v in zip(tags,[573000000,42000000,32000000])}}}
        result=normalize_aa(copy.deepcopy(payload))['facts']['us-gaap']['SpecialtyOperatingSubtotal']['units']['USD']
        self.assertEqual(result[0]['val'],583000000)
        self.assertEqual(len(result[0]['inputs']),3)
        payload['facts']['us-gaap'][tags[-1]]['units']['USD'][0]['accn']='different'
        self.assertEqual(normalize_aa(payload)['facts']['us-gaap']['SpecialtyOperatingSubtotal']['units']['USD'],[])

    def test_published_accounts_and_currency(self):
        history=json.loads((ROOT/'data/commodities/specialty_financial_history.json').read_text(encoding='utf8'))
        self.assertEqual(set(history['companies']),set(COMPANIES))
        for key,meta in COMPANIES.items():
            rows=history['companies'][key]['rows']
            self.assertEqual(len({(r['year'],r['quarter']) for r in rows}),len(rows))
            for metric in ('revenue','profit','capex'):
                doc=json.loads((ROOT/f'data/commodities/company_specialty_{key}_{metric}.json').read_text(encoding='utf8'))
                self.assertEqual(doc['unit'],meta['currency']+' 백만')
                self.assertEqual(set(doc['series_views']),{'quarter','annual'})
                self.assertFalse(doc['span_gaps'])
                for date,value in next(iter(doc['series'].values())):
                    if value is None:continue
                    self.assertTrue(math.isfinite(value))
                    self.assertIn(date,doc['point_sources'])
                self.assertTrue(all(d<=today() for d in doc['series_views']['annual'].get('period_labels',{})))

    def test_six_valuation_listings_and_source_currencies(self):
        registry=json.loads((ROOT/'manual/specialty-valuation/companies.json').read_text(encoding='utf8'))
        expected={'aa':('AA','USD'),'cenx':('CENX','USD'),'alm':('ALM','USD'),'vnp':('VNP.TO','CAD'),'uamy':('UAMY','USD'),'afm':('AFM.V','CAD')}
        self.assertEqual({r['id']:(r['symbol'],r['currency']) for r in registry},expected)
        index=json.loads((ROOT/'data/commodities/specialty-valuation/specialty_valuation_index.json').read_text(encoding='utf8'))
        self.assertEqual({r['id'] for r in index['companies']},set(expected))
        for row in registry:
            doc=json.loads((ROOT/f'data/commodities/specialty-valuation/{row["id"]}.json').read_text(encoding='utf8'))
            self.assertEqual((doc['symbol'],doc['currency']),expected[row['id']])
            self.assertGreater(len(doc['prices']),100)
            self.assertGreaterEqual(doc['prices'][0][0],row['price_since'])
            self.assertTrue(doc['fundamentals'])
            if row['id'] in ('vnp','afm'):self.assertTrue(doc['fx'])

    def test_network_failure_preserves_observations_and_success_timestamp(self):
        import fetch_specialty_minerals as module
        history=json.loads((ROOT/'data/commodities/specialty_financial_history.json').read_text(encoding='utf8'))
        prior=history['companies']['aa'];state={'companies':{'aa':copy.deepcopy(prior)}}
        with patch.dict(module.COMPANIES,{'aa':COMPANIES['aa']},clear=True),patch.object(module,'load',return_value=state),patch.object(module,'save'),patch.object(module,'today',return_value='2026-11-07'),patch.object(module.requests,'Session') as session:
            session.return_value.get.side_effect=RuntimeError('unavailable')
            docs=module.collect()
        self.assertEqual(state['companies']['aa']['rows'],prior['rows'])
        for doc in docs.values():
            self.assertEqual(doc['fetched'],prior['fetched'])
            self.assertFalse(doc['collection_status']['ok'])
            self.assertEqual(doc['collection_status']['checked'],'2026-11-07')

    def test_operating_snapshots_do_not_sum_prices_or_bridge_missing_quarters(self):
        snapshot=json.loads((ROOT/'manual/specialty-minerals/operating.json').read_text(encoding='utf8'))
        for chart in snapshot['charts']:
            doc=json.loads((ROOT/f'data/commodities/{chart["id"]}.json').read_text(encoding='utf8'))
            self.assertFalse(doc['span_gaps'])
            self.assertNotIn('auto_collect_time',doc)
            self.assertNotIn('series_views',doc)
            self.assertEqual(doc['fetched'],snapshot['reviewed'])

if __name__=='__main__':unittest.main()
