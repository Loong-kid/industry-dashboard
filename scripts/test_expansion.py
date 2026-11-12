"""Real DART body fixtures, conservative classification and receipt-level amendments."""
import copy
import json
import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

import aggregate_expansion as aggregate
import fetch_expansion as fetch
from expansion_document import InvestmentParseError, classify, main_metadata, parse_document

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / 'scripts/fixtures/expansion'


class ExpansionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixtures = json.loads((FIX / 'manifest.json').read_text(encoding='utf-8'))
        cls.parsed = {r['listing']['rcept_no']: parse_document((FIX/r['filename']).read_bytes(),r['listing']) for r in cls.fixtures}

    def test_real_current_body_fields_and_mixed_purposes(self):
        d = self.parsed['20260120800431']
        self.assertEqual(d['amount_krw'], 99300000000)
        self.assertEqual(d['equity_ratio'], 14.6)
        self.assertEqual(d['end_date'], '2026-12-31')
        self.assertEqual(d['category'], 'expansion')
        self.assertEqual(self.parsed['20261001900652']['category'], 'review')
        self.assertEqual(self.parsed['20261001900652']['amount_krw'], 55000000000)
        self.assertIn('노후', self.parsed['20261001900652']['purpose'])

    def test_amendment_header_does_not_overwrite_the_current_amount(self):
        row = next(r for r in self.fixtures if r['listing']['rcept_dt'] == '20260325')
        d = self.parsed[row['listing']['rcept_no']]
        self.assertEqual(d['amount_krw'], 40313000000)
        self.assertNotEqual(d['amount_krw'], 68949000000)
        self.assertEqual(d['end_date'], '2026-06-30')
        self.assertEqual(d['investor'], '(주)하림산업')
        self.assertTrue(d['is_subsidiary'])

    def test_classification_uses_the_investment_scope(self):
        cases = [('시설증설','공장 생산라인','수요 증가 대응','expansion'),
                 ('신규시설투자','신공장 신축','신규사업 양산','new_facility'),
                 ('시설증설','물류센터','배송 능력 확대','excluded'),
                 ('시설증설','사옥','업무환경 개선','excluded'),
                 ('시설투자','생산라인','노후설비 교체 및 생산능력 확대','review'),
                 ('시설증설','생산라인','노후 전력망 수요에 대응한 생산능력 확대','expansion'),
                 ('시설투자','신공장 신축','공장 이전','review'),
                 ('시설투자','기계장치','경쟁력 강화','review')]
        for kind,target,purpose,category in cases:
            with self.subTest(purpose=purpose): self.assertEqual(classify(kind,target,purpose)[0],category)

    def test_unknown_units_and_broken_documents_are_not_guessed(self):
        row = next(r for r in self.fixtures if r['listing']['rcept_no']=='20260120800431')
        raw_bytes = (FIX/row['filename']).read_bytes()
        try: raw = raw_bytes.decode('utf-8')
        except UnicodeDecodeError: raw = raw_bytes.decode('cp949')
        no_unit = raw.replace('투자금액(원)','투자금액(달러)')
        self.assertNotEqual(raw, no_unit)
        d = parse_document(no_unit,row['listing'])
        self.assertIsNone(d.get('amount_krw'))
        self.assertEqual(d['category'],'review')
        with self.assertRaises(InvestmentParseError): parse_document('<p>access denied</p>',row['listing'])

    def test_official_family_ignores_unrelated_attachment_options(self):
        no='20261001900652'
        html=f'<select id="family"><option value="rcpNo={no}">2026.10.01 신규시설투자등</option></select><select id="att"><option value="rcpNo=20200101000000">이사회의사록</option></select>'
        family,_ = main_metadata(html,no)
        self.assertEqual([r['rcept_no'] for r in family],[no])
        with self.assertRaises(InvestmentParseError):main_metadata(html,'20200101000000')

    def test_withdrawal_disclosed_as_a_text_amendment_is_recognized(self):
        parsed=self.parsed['20260430901615']
        self.assertTrue(parsed['investment_withdrawn'])
        self.assertIsNone(parsed.get('amount_krw'))
        self.assertIn('철회',parsed['correction_reason'])
        self.assertNotIn('투자금액의 원화 단위를 확인하지 못함',parsed['warnings'])

    def fixture_state(self):
        rows=[]
        for r in self.fixtures:
            if r['listing']['stock_code']=='003380':rows.append(r)
        records={}
        family=[dict(r['listing']) for r in rows]
        for r in rows:
            listing=dict(r['listing']);no=listing['rcept_no']
            records[no]=dict(listing=listing,parsed=self.parsed[no],family=family,status='ok')
        return dict(reports=records,fetched='2026-11-13')

    def test_same_project_is_one_row_and_amendments_do_not_add_investments(self):
        state=self.fixture_state();doc=aggregate.build(state)
        self.assertEqual(len(doc['projects']),1)
        self.assertEqual(doc['projects'][0]['amount_krw'],40313000000)
        self.assertEqual(doc['projects'][0]['end_date'],'2026-11-30')
        self.assertEqual(len(doc['changes']),1)
        self.assertEqual(next(d for d in doc['changes'][0]['changes'] if d['field']=='end_date')['after'],'2026-11-30')
        # A company can have separate simultaneous projects. No title/date heuristic merges them.
        extra=copy.deepcopy(next(iter(state['reports'].values())))
        extra['listing']['rcept_no']='20261113000001';extra['family']=[]
        state['reports']['20261113000001']=extra
        self.assertEqual(len(aggregate.build(state)['projects']),2)

    def test_withdrawn_and_failed_latest_receipts_do_not_look_active(self):
        state=self.fixture_state();last=max(state['reports']);entry=state['reports'][last]
        entry['withdrawn']=True;entry['parsed']={}
        doc=aggregate.build(state)
        self.assertEqual(doc['projects'][0]['record_status'],'withdrawn')
        self.assertNotEqual(doc['projects'][0]['facts_rcept_no'],last)
        entry['withdrawn']=False;entry['status']='error'
        doc=aggregate.build(state)
        self.assertEqual(doc['projects'][0]['category'],'review')
        self.assertEqual(doc['coverage']['pending'],1)

    def test_listing_failure_does_not_advance_the_scan_checkpoint(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'state.json'
            fetch.write(path,dict(reports={},scanned_through='20261110'))
            with patch.object(fetch,'STATE',path),patch.object(fetch,'scan_reports',side_effect=RuntimeError('unavailable')):
                with self.assertRaises(RuntimeError):fetch.run('fixture-key',begin='20261111',end='20261113')
            self.assertEqual(json.loads(path.read_text(encoding='utf-8'))['scanned_through'],'20261110')

    def test_market_scan_keeps_amendments_and_filters_other_exchange_reports(self):
        row=dict(rcept_no='20261113000001',report_nm='[기재정정]신규 시설 투자 등',corp_cls='Y',stock_code='001001')
        calls=[]
        def reply(session,url,**params):
            calls.append(params)
            return SimpleNamespace(json=lambda:dict(status='000',total_page=1,list=[row,dict(row,rcept_no='20261113000002',report_nm='분기보고서')]))
        with patch.object(fetch,'request',side_effect=reply):rows=fetch.scan_reports('not-a-real-key','20261001','20261113')
        self.assertEqual([r['rcept_no'] for r in rows],['20261113000001'])
        self.assertEqual({c['corp_cls'] for c in calls},{'Y','K'})
        self.assertTrue(all(c['last_reprt_at']=='N' and c['pblntf_ty']=='I' and c['pblntf_detail_ty']=='I001' for c in calls))
        self.assertTrue(all((fetch.dt.datetime.strptime(c['end_de'],'%Y%m%d')-fetch.dt.datetime.strptime(c['bgn_de'],'%Y%m%d')).days<=30 for c in calls))

    def test_interrupted_original_requests_preserve_the_pending_queue(self):
        listing=dict(self.fixtures[0]['listing'])
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'state.json'
            with patch.object(fetch,'STATE',path),patch.object(fetch,'scan_reports',return_value=[listing]),patch.object(fetch,'fetch_report',side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt):fetch.run('fixture-key',begin='20261101',end='20261113')
            saved=json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(saved['reports'][listing['rcept_no']]['status'],'pending')
            self.assertEqual(saved['scanned_through'],'20261113')
            self.assertEqual(aggregate.build(saved)['coverage']['pending'],1)
            with patch.object(fetch,'STATE',path),patch.object(fetch,'scan_reports',side_effect=AssertionError('must not query the API')),patch.object(fetch,'fetch_report',return_value=dict(listing=listing,status='ok',family=[],parsed=self.parsed[listing['rcept_no']])):
                self.assertEqual(fetch.run(pending_only=True),0)
            self.assertEqual(json.loads(path.read_text(encoding='utf-8'))['reports'][listing['rcept_no']]['status'],'ok')

    def test_published_dataset_is_rebuilt_from_its_source_state(self):
        if not fetch.STATE.exists():self.skipTest('before initial source collection')
        expected=aggregate.build(json.loads(fetch.STATE.read_text(encoding='utf-8')))
        actual=json.loads(aggregate.OUT.read_text(encoding='utf-8'))
        self.assertEqual(actual,expected)
        self.assertEqual(len({p['id'] for p in actual['projects']}),len(actual['projects']))
        self.assertNotIn('crtfc_key',json.dumps(actual))


if __name__=='__main__':unittest.main()
