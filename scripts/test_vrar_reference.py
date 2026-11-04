"""Source fidelity, amendment identity and last-good contract preservation."""
import copy,json,unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from build_vrar_reference import build as sheet_build,SOURCE
from vrar_contracts import build,parse
import fetch_vrar_contracts as fetch

ROOT=Path(__file__).resolve().parents[1]
FIX=ROOT/'scripts/fixtures/vrar/contracts'
def read(path):return json.loads(path.read_text(encoding='utf8'))


class SheetReference(unittest.TestCase):
    def test_snapshot_fidelity_and_continuation_rows(self):
        raw=read(SOURCE);doc=sheet_build(raw)
        self.assertEqual(doc,read(ROOT/'data/vrar/reference_tables.json'))
        self.assertEqual([len(c['rows']) for c in doc['categories']],[13,22,15,40,6])
        vr=doc['categories'][0]['rows'];apple=vr[0]
        self.assertEqual(apple['maker'],'Apple')
        self.assertEqual([c['chip'] for c in apple['components']],['R1','H2'])
        self.assertFalse(any(r['source_row'] in [5,6,8,9] for r in vr))
        self.assertIn('gid=1790536984',apple['source_url'])
        self.assertIn('range=B4:AI6',apple['source_url'])
        self.assertEqual(len(doc['contract_notes']),7)
        self.assertEqual(raw['tabs']['contracts']['range'],'AC9:BE70')
        text=json.dumps(doc,ensure_ascii=False)
        for token in ['2026-3H','2027-2H','?','₩','¥']:self.assertIn(token,text)
        self.assertFalse(any('반드시' in r['model'] or '개발중' in r['model'] for c in doc['categories'] for r in c['rows']))


class OriginalContracts(unittest.TestCase):
    def test_actual_originals_amounts_and_changed_contract_date(self):
        rows=[parse((FIX/(e['rcept_no']+'.html')).read_text(encoding='utf8'),e) for e in read(FIX/'sources.json')]
        first,middle,last=rows
        self.assertEqual(first['amount_usd'],3582820)
        self.assertEqual(middle['amount_krw'],12027751804)
        self.assertEqual(middle['amount_usd'],8617720)
        self.assertEqual(last['amount_usd'],9591720)
        self.assertEqual(last['end'],'2026-12-11')
        self.assertNotEqual(first['deal_date'],middle['deal_date'])
        # Include the intervening amendment to exercise the explicit full chain.
        state=read(ROOT/'data/vrar/contract_source_state.json')
        all_rows=[r for r in state['disclosures'] if r['receipt'] in ['20240826900104','20250314900870','20250829900784','20260527900566','20261014900205']]
        doc=build(all_rows,{'contract_notes':[]},'2026-11-05','2026-11-05')
        self.assertEqual(len(doc['contracts']),1)
        contract=doc['contracts'][0]
        self.assertEqual(len(contract['history']),5)
        self.assertEqual(contract['latest']['end'],'2026-12-11')
        self.assertEqual(contract['changed_fields'],['종료일'])
        self.assertNotIn('raw_html',json.dumps(doc))

    def test_shared_dates_and_counterparty_do_not_merge_unrelated_contracts(self):
        state=read(ROOT/'data/vrar/contract_source_state.json');a=copy.deepcopy(state['disclosures'][0]);b=copy.deepcopy(a)
        b['receipt']='20240621900999';b['amount_usd']=12345
        note=dict(source_row=10,sheet_date=a['filed'],usd_display='unknown')
        doc=build([a,b],{'contract_notes':[note]},'2026-11-05','2026-11-05')
        self.assertEqual(len(doc['contracts']),2)
        self.assertEqual(doc['unmatched_sheet_notes'],[note])
        self.assertTrue(all(not c['sheet_notes'] for c in doc['contracts']))

    def test_latest_terms_memos_and_future_filter(self):
        state=read(ROOT/'data/vrar/contract_source_state.json');sheet=read(ROOT/'data/vrar/reference_tables.json')
        doc=build(state['disclosures'],sheet,'2026-11-05',state['checked'])
        published=read(ROOT/'data/vrar/contract_watch.json')
        rebuilt=build(state['disclosures'],sheet,published['asof'],state['checked'],state.get('errors',[]))
        self.assertEqual(rebuilt,published)
        self.assertEqual(len(doc['contracts']),8)
        self.assertFalse(doc['unmatched_sheet_notes'])
        meta=next(c for c in doc['contracts'] if c['id']=='20240826900104')
        self.assertEqual(meta['sheet_notes'][0]['memo'],'Meta')
        self.assertNotIn('Meta',meta['latest']['counterparty'])
        elapsed=[c for c in doc['contracts'] if c['status_code']=='elapsed']
        self.assertEqual(len(elapsed),3)
        self.assertTrue(all('완료' not in c['status'] for c in elapsed))
        self.assertEqual(sum(c['status_code']=='due' for c in doc['contracts']),2)
        earlier=build(state['disclosures'],sheet,'2026-09-01','2026-09-01')
        old=next(c for c in earlier['contracts'] if c['id']==meta['id'])
        self.assertEqual(old['latest']['end'],'2026-10-16')

    def test_failed_source_retains_last_verified_contracts_and_flags_status(self):
        state=read(ROOT/'data/vrar/contract_source_state.json')
        with TemporaryDirectory() as directory:
            root=Path(directory);cache=root/'cache';cache.mkdir();state_path=root/'state.json'
            state_path.write_text(json.dumps(state),encoding='utf8')
            (cache/'status.json').write_text(json.dumps(dict(checked='2026-11-05',reports=[],errors=[dict(error='offline')])),encoding='utf8')
            with patch.object(fetch,'STATE',state_path),patch.object(fetch,'CACHE',cache),patch.object(fetch,'OUT',root/'watch.json'):
                doc=fetch.refresh('2026-11-05')
            self.assertEqual(len(doc['contracts']),8)
            self.assertFalse(doc['collection_status']['ok'])
            self.assertEqual(len(read(state_path)['disclosures']),len(state['disclosures']))


if __name__=='__main__':unittest.main()
