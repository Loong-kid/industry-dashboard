import copy
import io
import json
import tempfile
import unittest
import zipfile
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import fetch_fed_reserves as fed

TODAY = date(2026, 10, 5)
LATEST = '2026-09-30'
VALUES = dict(zip(fed.IDS, [6464597, 4564161, 2347, 1898089, 8804,
                          8738, 0, 58, 7, 0, 0, 2881686, 984046, 361883,
                          350344, 11539, 6794886, 3913200, 2482756]))


def data(points=1):
    days = [(date.fromisoformat(LATEST)-timedelta(weeks=i)).isoformat() for i in range(points)]
    return {sid: {d: value for d in days} for sid, value in VALUES.items()}


def package(ids, rows, unit='Millions of U.S. Dollars', basis='Wednesday Level'):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as archive:
        archive.writestr('README.txt', '\n'.join(f'{sid}  Assets: {basis}, {unit}, Weekly\n' for sid in ids))
        archive.writestr('weekly.csv', 'observation_date,'+','.join(ids)+'\n'+'\n'.join(rows))
    return buf.getvalue()


class FedReservesTests(unittest.TestCase):
    def test_real_release_values_need_currency_and_other_factors(self):
        days, values = fed.derive(data())
        self.assertEqual(days,[LATEST])
        self.assertEqual(values['simple'][LATEST],5127472)
        self.assertEqual(values['other_supply'][LATEST],321485)
        self.assertEqual(values['other_drain'][LATEST],84515)
        self.assertEqual(values['reconstructed'][LATEST],2881686)
        self.assertEqual(values['gap'][LATEST],2245786)
        self.assertEqual(fed.billions(values['simple']),[[LATEST,5127.472]])

    def test_estimate_uses_independent_totals_and_rejects_identity_failure(self):
        source = data()
        source['WRBWFRBL'][LATEST] += 6
        with self.assertRaisesRegex(ValueError,'identity'):
            fed.derive(source)
        # More loans and supply increase reserves by the same amount; adding
        # the loan facility components again would fail this identity.
        source = data()
        for sid in ['WLCFLL','WTFSRFL','WRBWFRBL']:
            source[sid][LATEST] += 1000
        self.assertEqual(fed.derive(source)[1]['reconstructed'][LATEST],2882686)

    def test_dates_intersect_without_forward_fill_and_latest_must_match(self):
        source = data(3)
        del source['WDTGAL']['2026-09-23']
        self.assertEqual(fed.derive(source)[0],['2026-09-16',LATEST])
        del source['WDTGAL'][LATEST]
        with self.assertRaisesRegex(ValueError,'latest'):
            fed.derive(source)

    def test_download_checks_units_basis_complete_columns_zero_and_missing(self):
        ids = ['WSHOSHO',fed.BTFP]
        blob = package(ids,['2026-09-23,6464597,0','2026-09-30,6464597,'])
        result = fed.parse_download(blob,ids,TODAY)
        self.assertEqual(result[fed.BTFP],{'2026-09-23':0})
        for invalid in [package(ids,['2026-09-30,1,0'],unit='Billions of US Dollars'),
                        package(ids,['2026-09-30,1,0'],basis='Week Average'),
                        package(ids[:1],['2026-09-30,1']),
                        package(ids,['2026-10-07,1,0']),
                        package(ids,['2026-10-05,1,0']),
                        package(ids,['2026-09-30,nan,0'])]:
            with self.assertRaises(ValueError):
                fed.parse_download(invalid,ids,TODAY)

    def test_folded_readme_title_ignores_update_date_column(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf,'w') as archive:
            archive.writestr('README.txt','WSHOSHO  Assets: Securities: Wednesday  Data Updated: 2026-10-01\n         Level, Millions of U.S. Dollars, Weekly\n')
            archive.writestr('weekly.csv','observation_date,WSHOSHO\n2026-09-30,6464597\n')
        self.assertEqual(fed.parse_download(buf.getvalue(),['WSHOSHO'],TODAY)['WSHOSHO'][LATEST],6464597)

    def test_cards_keep_discontinued_btfp_endpoint_and_component_units(self):
        source = data(500)
        source[fed.BTFP] = {d: v for d,v in source[fed.BTFP].items() if d <= '2026-05-06'}
        docs = {d['id']:d for d in fed.build_docs(source,TODAY)}
        self.assertEqual(len(docs),6)
        facility = docs['fed_facilities']
        self.assertEqual(facility['series']['BTFP(종료)'][-1],['2026-05-06',0])
        self.assertEqual(facility['series']['연준 전체 대출'][-1],[LATEST,8.804])
        self.assertEqual(facility['series']['재할인창구 합계'][-1],[LATEST,8.796])
        self.assertEqual(docs['fed_reserves_estimate']['default_series'][0],'공식 지급준비금')
        source['WSHOTSL'][LATEST] += 6
        with self.assertRaisesRegex(ValueError,'securities components'):
            fed.build_docs(source,TODAY)

    def test_validate_all_cards_before_replacing_any_and_accept_corrections(self):
        source = data(500)
        docs = fed.build_docs(source,TODAY)
        with tempfile.TemporaryDirectory() as tmp, patch.object(fed,'OUT',Path(tmp)/'macro'), \
                patch.object(fed,'CACHE',Path(tmp)/'cache.json'):
            fed.publish(source,docs,TODAY)
            before = {p:p.read_bytes() for p in Path(tmp).rglob('*.json')}
            truncated = copy.deepcopy(docs)
            truncated[-1]['series']['전체 역레포'].pop(0)
            with self.assertRaisesRegex(ValueError,'history regressed'):
                fed.publish(source,truncated,TODAY)
            for p,raw in before.items():
                self.assertEqual(p.read_bytes(),raw)
            corrected = copy.deepcopy(docs)
            corrected[0]['series']['공식 지급준비금'][0][1] += .001
            fed.publish(source,corrected,TODAY)
            out = json.loads((fed.OUT/'fed_reserves_estimate.json').read_text(encoding='utf-8'))
            self.assertEqual(out['series'],corrected[0]['series'])


if __name__ == '__main__':
    unittest.main()
