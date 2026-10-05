import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from gift_plan_document import parse_plan_document,parse_family,GiftPlanParseError
from fetch_gift_plans import load_db,save_db,run
from aggregate_gift_plans import build_document

FIXTURE=(Path(__file__).parent/'fixtures/gift_plan_gs.xml').read_text(encoding='utf-8')
LISTING={'report_nm':'임원ㆍ주요주주특정증권등거래계획보고서','stock_code':'078930',
         'rcept_no':'20250723000192','rcept_dt':'20250723','corp_name':'GS','corp_cls':'Y'}


class GiftPlansTest(unittest.TestCase):
    def parse(self,text=FIXTURE):
        return parse_plan_document(text,LISTING)

    def test_source_gift_future_table(self):
        event=self.parse()['events'][0]
        self.assertEqual((event['gift_shares'],event['plan_start'],event['plan_end']),(500000,'2025-08-22','2025-09-20'))
        self.assertEqual(event['counterparty'],'허서홍')
        self.assertEqual(event['before_rate'],2.15)
        self.assertEqual(event['after_rate'],1.62)
        self.assertEqual(event['direction'],'증여(줌)')

    def test_past_gift_does_not_make_future_sale_a_gift(self):
        past='<table><tr><tu aunit="MDF_DT">2025.06.01</tu><tu aunit="MDF_MT">증여(-)</tu><te acode="STR_STK_CNT">-900000</te></tr></table>'
        data=FIXTURE.replace('증여(-)','장내매도(-)')+past
        # The purpose still says gift. Only the future method row determines classification.
        self.assertEqual(self.parse(data)['events'],[])
        self.assertEqual(self.parse(FIXTURE+past)['events'][0]['gift_shares'],500000)
        self.assertEqual(self.parse(FIXTURE.replace('증여(-)','증여세 납부를 위한 장내매도(-)'))['events'],[])

    def test_rowspan_counterparties_remain_separate(self):
        from bs4 import BeautifulSoup
        soup=BeautifulSoup(FIXTURE,'html.parser')
        method=soup.find(attrs={'aunit':'MDF_MT'},string='증여(-)')
        row=method.parent
        new=copy.copy(row)
        for tag in new.find_all(attrs={'aunit':True}):
            if tag['aunit'] in ('MDF_STR_DT','MDF_END_DT','TRAN_PROD'): tag.decompose()
        new.find(attrs={'acode':'STR_STK_CNT'}).string='-100,000'
        new.find(attrs={'acode':'RMK'}).string='수증자:홍길동'
        row.insert_after(new)
        events=self.parse(str(soup))['events']
        self.assertEqual([e['gift_shares'] for e in events],[500000,100000])
        self.assertEqual([e['counterparty'] for e in events],['허서홍','홍길동'])
        self.assertEqual(events[1]['plan_start'],'2025-08-22')
        new.find(attrs={'acode':'STR_STK_CNT'}).string='-'
        new.find(attrs={'acode':'RMK'}).string='-'
        self.assertEqual(len(self.parse(str(soup))['events']),1,'Ignore otherwise blank repeated gift template row')

    def test_no_cb_as_stock_or_missing_number_as_zero(self):
        self.assertEqual(self.parse(FIXTURE.replace('보통주','전환사채권'))['events'],[])
        self.assertEqual(self.parse(FIXTURE.replace('-500,000','500,000'))['events'][0]['gift_shares'],500000)
        for bad in ('-', 'NaN','-500000.5'):
            with self.subTest(bad=bad),self.assertRaises(GiftPlanParseError):
                self.parse(FIXTURE.replace('-500,000',bad))
        with self.assertRaises(GiftPlanParseError):
            self.parse(FIXTURE.replace('2025.09.20','2025.07.01'))
        with self.assertRaises(GiftPlanParseError):
            self.parse(FIXTURE.replace('증여(-)','수증(+)'))

    def test_family_only_body_reports_not_other_dropdown(self):
        body='<select id="family"><option value="rcpNo=20250723000192" title="임원 특정증권등 거래계획보고서"></option><option value="rcpNo=20250724000100" title="[기재정정]임원 특정증권등 거래계획보고서"></option><option value="rcpNo=20250725000100" title="[철회]임원 특정증권등 거래계획보고서"></option></select>'
        family=parse_family(body+'<select id="att"><option value="rcpNo=20260723000999">첨부</option></select>','20250723000192')
        self.assertEqual(len(family),3)
        self.assertTrue(family[-1]['withdrawn'])
        with self.assertRaises(GiftPlanParseError): parse_family('<html/>','20250723000192')
        self.family=family

    def test_correction_withdrawal_and_unknown_latest_are_never_executed(self):
        original=LISTING['rcept_no']; corrected='20250724000100'; withdrawal='20250725000100'
        record=dict(self.parse(),listing=LISTING,status='ok',withdrawn=False,
                    family=[{'rcept_no':original},{'rcept_no':corrected}])
        correction=dict(copy.deepcopy(record),listing=dict(LISTING,rcept_no=corrected,rcept_dt='20250724'))
        correction['events'][0]['gift_shares']=400000
        db={'reports':{original:record,corrected:correction}}
        doc=build_document(db)
        self.assertEqual({r['rcept_no']:r['record_status'] for r in doc['orders']},{original:'superseded',corrected:'active'})
        self.assertEqual(len([r for r in doc['orders'] if r['record_status']=='active']),1)
        # A later correction removes gifts altogether; do not keep the original active.
        correction['events']=[]
        self.assertEqual(build_document(db)['orders'][0]['record_status'],'superseded')
        correction['events']=copy.deepcopy(record['events'])
        correction['family'].append({'rcept_no':withdrawal})
        self.assertTrue(all(r['record_status']=='latest_unverified' for r in build_document(db)['orders']))
        db['reports'][withdrawal]={'status':'ok','withdrawn':True,'events':[],'listing':dict(LISTING,rcept_no=withdrawal),'family':correction['family']}
        self.assertTrue(all(r['record_status']=='withdrawn' for r in build_document(db)['orders']))
        self.assertTrue(all('execution_date' not in r for r in build_document(db)['orders']))

    def test_checkpoint_failure_retry_and_atomic_preservation(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'db.json'
            old={'schema_version':1,'reports':{LISTING['rcept_no']:dict(self.parse(),listing=LISTING,status='ok')}}
            save_db(old,path)
            self.assertEqual(load_db(path),old)
            failed=dict(LISTING,rcept_no='20260923000100',rcept_dt='20260923')
            # Transport failure must retain old records and a retryable new listing.
            with patch('fetch_gift_plans.load_db',side_effect=lambda:load_db(path)),patch('fetch_gift_plans.save_db',side_effect=lambda db:save_db(db,path)),patch('fetch_gift_plans.fetch_report',side_effect=RuntimeError('failure')):
                with self.assertRaises(RuntimeError):run('TEST_KEY','20260923','20261005',reports=[failed])
            db=load_db(path)
            self.assertEqual(db['reports'][LISTING['rcept_no']],old['reports'][LISTING['rcept_no']])
            self.assertEqual(db['reports'][failed['rcept_no']]['status'],'error')
            self.assertNotIn('TEST_KEY',path.read_text(encoding='utf-8'))

    def test_official_api_flags_override_old_cached_active_body(self):
        no=LISTING['rcept_no']
        record=dict(self.parse(),listing=dict(LISTING,rm='정'),status='ok',withdrawn=False,
                    family=[{'rcept_no':no}],family_status='api_flags')
        db={'reports':{no:record}}
        self.assertEqual(build_document(db)['orders'][0]['record_status'],'superseded')
        record['listing']['rm']='정철'
        self.assertEqual(build_document(db)['orders'][0]['record_status'],'withdrawn')
        record['listing']['rm']=''
        self.assertEqual(build_document(db)['orders'][0]['record_status'],'active')


if __name__=='__main__':unittest.main()
