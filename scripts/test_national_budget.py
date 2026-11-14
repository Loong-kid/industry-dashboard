"""Accounting boundaries and publication integrity; no network or cache required."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import fetch_national_budget as fetcher
from national_budget_sources import ROOT, aggregate_accounts, kr_accounts, kr_grid, parse_mts, parse_omb


class NationalBudgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.docs={c:json.loads((ROOT/f'data/national-budget/{c}.json').read_text(encoding='utf8')) for c in ['kr','us']}
        cls.accounts={}
        for country,doc in cls.docs.items():
            rows=[]
            for sector,path in doc['account_files'].items():
                data=json.loads((ROOT/'data/national-budget'/path).read_text(encoding='utf8'))
                assert all(r['sector']==sector for r in data['programs'])
                rows.extend(data['programs'])
            cls.accounts[country]={'programs':rows}

    def test_publication_reconciles_all_years_and_bases(self):
        for country,doc in self.docs.items():
            fetcher.validate(doc,self.accounts[country])

    def test_zero_budget_and_unavailable_future_are_distinct(self):
        doc=self.docs['kr']
        self.assertEqual(len(doc['sectors']),16)
        self.assertIn('통일·외교',[s['name'] for s in doc['sectors']])
        self.assertNotIn('외교·통일',[s['name'] for s in doc['sectors']])
        # A whole unvoted column must never turn into a published zero budget.
        self.assertTrue(all(v>100 for v in doc['totals']['approved'].values()))
        self.assertTrue(any(0 in r['values']['approved'].values() for r in self.accounts['kr']['programs']))
        for year in set(doc['totals']['proposal'])-set(doc['totals']['approved']):
            self.assertTrue(all(year not in r['values']['approved'] for r in self.accounts['kr']['programs']))

    def test_korean_source_units_and_missing_amounts(self):
        row=dict(FIN_DE_EP_NM='일반지출',OFFC_NM='기관',FLD_NM='외교·통일',FSCL_YY='2026',SACTV_NM='사업',Y_YY_DFN_MEDI_KCUR_AMT='1,000,000,000',Y_YY_MEDI_KCUR_AMT='0')
        parsed=kr_accounts([row])[0]
        self.assertEqual(parsed['sector'],'통일·외교')
        self.assertEqual(parsed['approved'],1)
        self.assertEqual(parsed['proposal'],0)
        with self.assertRaises(ValueError):kr_accounts([{**row,'FIN_DE_EP_NM':'내부거래'}])
        with self.assertRaises(ValueError):kr_accounts([{**row,'Y_YY_MEDI_KCUR_AMT':None}])

    def test_public_download_rejects_partial_or_duplicate_pages(self):
        class Client:
            def json(self,*args,**kwargs):return [{'PAGE_TOT_CNT':2,'PAGE_ROW_NUM':1,'FSCL_YY':'2026'}]*2
        with self.assertRaises(ValueError):kr_grid(Client(),2026)

    def test_omb_thousand_dollars_and_negative_offsets(self):
        headers=['Agency Code','Agency Name','Bureau Code','Bureau Name','Account Code','Account Name','Subfunction Code','BEA Category','On- or Off- Budget','2013','2014','2025','2031']
        rows=[headers]
        for i in range(1000):
            rows.append(['001','Agency','01','Bureau',str(i),'Account','951' if i==1 else '051','Mandatory','On-budget',99,(-30000000 if i==1 else 200000000 if i==0 else 0),0,None])
        class Sheet:
            reset=False
            def reset_dimensions(self):self.reset=True
            def iter_rows(self,**kwargs):return iter(rows)
        sheet=Sheet()
        class Book:
            worksheets=[sheet]
            def close(self):pass
        with patch('national_budget_sources.load_workbook',return_value=Book()):parsed,years=parse_omb(b'unused','outlays')
        self.assertTrue(sheet.reset)
        self.assertEqual(years,[2014,2025,2031])
        self.assertEqual(parsed[0]['values'],{'2014':200,'2025':0})
        self.assertEqual(parsed[1]['sector'],'950')
        self.assertEqual(aggregate_accounts(parsed)[0]['2014'],170)

    def test_negative_offsets_reduce_national_total(self):
        totals,sectors=aggregate_accounts([{'sector':'050','values':{'2025':200}}, {'sector':'950','values':{'2025':-30}}])
        self.assertEqual(totals['2025'],170)
        self.assertEqual(sectors['950']['2025'],-30)
        offset=next(s for s in self.docs['us']['sectors'] if s['id']=='950')
        self.assertLess(offset['values']['outlays']['2025'],0)

    def test_treasury_actual_reconciles_and_rejects_missing_function(self):
        from national_budget_sources import FUNCTIONS
        rows=[dict(classification_desc='Net Outlays',parent_id='null',classification_id='N',current_fytd_rcpt_outly_amt='null'),dict(classification_desc='Receipts',parent_id='null',classification_id='R',current_fytd_rcpt_outly_amt='null')]
        for code,(_,name) in FUNCTIONS.items():
            rows.append(dict(classification_desc=name,parent_id='N',classification_id=code,current_fytd_rcpt_outly_amt=str((-1 if code=='950' else 2)*1e9)))
        rows.extend([dict(classification_desc='Total',parent_id='N',current_fytd_rcpt_outly_amt=str(37e9)),dict(classification_desc='Total',parent_id='R',current_fytd_rcpt_outly_amt=str(30e9))])
        totals,sectors=parse_mts(rows)
        self.assertEqual(totals,dict(spending=37,revenue=30,balance=-7))
        self.assertEqual(sectors['950'],-1)
        with self.assertRaises(ValueError):parse_mts(rows[:-3]+rows[-2:])

    def test_treasury_gateway_retry_keeps_exact_fiscal_date(self):
        class Client:
            queries=[]
            def json(self,*args,**kwargs):
                self.queries.append(dict(kwargs['params']))
                if len(self.queries)==1:raise fetcher.requests.HTTPError('503 gateway')
                return {'data':[{'record_date':'2026-09-30'}]}
        client=Client();rows=fetcher.treasury_rows(client,2026)
        self.assertEqual(rows,[{'record_date':'2026-09-30'}])
        self.assertEqual(client.queries[0]['page[number]'],1)
        self.assertEqual(client.queries[1]['filter'],'record_date:gte:2026-09-30,record_date:lte:2026-09-30')
        class WrongDate:
            def json(self,*args,**kwargs):return {'data':[{'record_date':'2026-08-31'}]}
        with self.assertRaisesRegex(ValueError,'date mismatch'):fetcher.treasury_rows(WrongDate(),2026)

    def test_vintages_balance_and_reference_year_not_actual(self):
        for doc in self.docs.values():
            self.assertEqual(len({v['id'] for v in doc['outlooks']}),len(doc['outlooks']))
            for outlook in doc['outlooks']:
                self.assertLessEqual(outlook['publication_date'],fetcher.today())
                series=outlook['series']
                for year,total in series['spending'].items():
                    if year in series['revenue'] and year in series['balance']:
                        self.assertAlmostEqual(series['revenue'][year]-total,series['balance'][year],delta=.11)
                if 'mandatory' in series:
                    for year,total in series['spending'].items():self.assertAlmostEqual(series['mandatory'][year]+series['discretionary'][year],total,delta=.11)
        self.assertLess(int(max(self.docs['kr']['macro']['spending'])),int(fetcher.today()[:4]))
        self.assertGreaterEqual(self.docs['us']['actual_through']['outlays'],self.docs['us']['account_actual_through'])

    def test_failed_refresh_retains_success_date_and_history(self):
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)
            for c,doc in self.docs.items():fetcher.save(out/(c+'.json'),doc)
            with patch.object(fetcher,'OUT',out),patch.object(fetcher,'Client'),patch.object(fetcher,'collect_kr',side_effect=ValueError('source unavailable')),patch.object(fetcher,'collect_us',side_effect=ValueError('source unavailable')):
                fetcher.run()
            for c,original in self.docs.items():
                kept=fetcher.load(out/(c+'.json'))
                self.assertFalse(kept['ok']);self.assertEqual(kept['fetched'],original['fetched']);self.assertEqual(kept['totals'],original['totals'])

    def test_corrupt_totals_fail_before_publication(self):
        doc=copy.deepcopy(self.docs['kr']);doc['totals']['approved']['2026']+=10
        with self.assertRaisesRegex(ValueError,'reconcile'):fetcher.validate(doc,self.accounts['kr'])

    def test_offline_rebuild_does_not_claim_new_success(self):
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)
            for c,doc in self.docs.items():fetcher.save(out/(c+'.json'),dict(doc,fetched='2025-01-02',checked='2025-01-03',ok=False,error='source unavailable'))
            fetcher.save(out/'index.json',{'updated':'2025-01-03T00:00:00+00:00'})
            with patch.object(fetcher,'OUT',out),patch.object(fetcher,'Client'),patch.object(fetcher,'collect_kr',return_value=(copy.deepcopy(self.docs['kr']),{**self.accounts['kr'],'source_url':'https://example.org'})),patch.object(fetcher,'collect_us',return_value=(copy.deepcopy(self.docs['us']),{**self.accounts['us'],'source_url':'https://example.org'})):
                fetcher.run(offline=True)
            for c in self.docs:
                doc=fetcher.load(out/(c+'.json'))
                self.assertEqual(doc['fetched'],'2025-01-02');self.assertEqual(doc['checked'],'2025-01-03');self.assertFalse(doc['ok']);self.assertEqual(doc['error'],'source unavailable')
            self.assertEqual(fetcher.load(out/'index.json')['updated'],'2025-01-03T00:00:00+00:00')


if __name__=='__main__':unittest.main()
