import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import fetch_liquidity as liquidity

TODAY = date(2026, 10, 5)


def treasury(account, day, opening, closing):
    return {'data': [{'record_date': day, 'account_type': account,
                      'open_today_bal': opening, 'close_today_bal': closing}],
            'meta': {'dataFormats': {'open_today_bal': '$1,000,000', 'close_today_bal': '$1,000,000'},
                     'total-count': 1, 'total-pages': 1}}


class LiquidityTests(unittest.TestCase):
    def test_treasury_format_change_uses_correct_closing_value_and_scale(self):
        cases = [('Federal Reserve Account', '2005-10-03', '4381', '5448', 5.448),
                 ('Treasury General Account (TGA)', '2022-04-14', '543536', '602292', 602.292),
                 ('Treasury General Account (TGA) Closing Balance', '2026-10-01', '893699', 'null', 893.699)]
        for account, day, opening, closing, expected in cases:
            self.assertEqual(liquidity.parse_tga(treasury(account, day, opening, closing), account, TODAY), {day: expected})

    def test_wrong_account_unit_and_null_are_rejected(self):
        account = 'Treasury General Account (TGA) Closing Balance'
        payload = treasury(account, '2026-10-01', '893699', 'null')
        payload['data'][0]['account_type'] = 'Treasury General Account (TGA) Opening Balance'
        with self.assertRaises(ValueError):
            liquidity.parse_tga(payload, account, TODAY)
        payload['data'][0]['account_type'] = account
        payload['meta']['dataFormats']['open_today_bal'] = '$1'
        with self.assertRaises(ValueError):
            liquidity.parse_tga(payload, account, TODAY)
        with self.assertRaises(ValueError):
            liquidity.parse_tga(treasury(account, '2026-10-01', 'null', '1'), account, TODAY)

    def test_rrp_keeps_zero_and_skips_unpublished_not_converts_billions(self):
        csv = 'observation_date,RRPONTSYD\n2026-09-30,11.539\n2026-10-01,0\n2026-10-02,1.501\n2026-10-03,\n2026-10-04,.\n'
        self.assertEqual(liquidity.parse_rrp(csv, TODAY), [('2026-09-30',11.539), ('2026-10-01',0), ('2026-10-02',1.501)])

    def test_invalid_and_conflicting_rrp_responses_are_rejected(self):
        for csv in ['<html>Error</html>', 'observation_date,RRPONTSYD\n',
                    'observation_date,RRPONTSYD\n2026-10-06,1\n',
                    'observation_date,RRPONTSYD\n2026-10-01,nan\n',
                    'observation_date,RRPONTSYD\n2026-10-01,-1\n',
                    'observation_date,RRPONTSYD\n2026-10-01,1\n2026-10-01,2\n']:
            with self.assertRaises(ValueError):
                liquidity.parse_rrp(csv, TODAY)

    def test_treasury_queries_all_three_exact_accounts_and_checks_pagination(self):
        def response(session, url, params):
            account = params['filter'].split(':eq:')[1]
            idx = list(liquidity.TGA_FIELDS).index(account)
            payload = treasury(account, f'2026-09-{idx+1:02}', '1000', '2000')
            return SimpleNamespace(json=lambda: payload)
        with patch.object(liquidity, 'get', side_effect=response):
            self.assertEqual(liquidity.collect_tga(None, TODAY), [('2026-09-01',2), ('2026-09-02',2), ('2026-09-03',1)])
        payload = treasury('Federal Reserve Account', '2026-09-01', '1000', '2000')
        payload['meta']['total-count'] = 2
        with patch.object(liquidity, 'get', return_value=SimpleNamespace(json=lambda: payload)):
            with self.assertRaisesRegex(ValueError, 'Incomplete'):
                liquidity.collect_tga(None, TODAY)

    def test_failed_or_truncated_refresh_preserves_existing_card(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(liquidity, 'OUT', Path(tmp)):
            original = {'id':'liquidity_tga', 'updated':'2026-10-02', 'series':{'TGA':[['2026-10-01',1],['2026-10-02',2]]}}
            liquidity.save(original)
            path = Path(tmp)/'liquidity_tga.json'
            before = path.read_bytes()
            for points in [[['2026-10-01',1]], [['2026-10-02',2]]]:
                with self.assertRaises(ValueError):
                    liquidity.save({**original,'updated':points[-1][0],'series':{'TGA':points}})
                self.assertEqual(path.read_bytes(),before)
            corrected = {**original,'series':{'TGA':[['2026-10-01',1.5],['2026-10-02',2]]}}
            liquidity.save(corrected)
            self.assertEqual(json.loads(path.read_text(encoding='utf-8')),corrected)

    def test_one_source_failure_keeps_its_card_and_updates_the_other(self):
        rows = ['observation_date,RRPONTSYD'] + [
            f'{TODAY-timedelta(days=250-i)},1.501' for i in range(250)]
        with tempfile.TemporaryDirectory() as tmp, patch.object(liquidity, 'OUT', Path(tmp)), \
                patch.object(liquidity, 'collect_tga', side_effect=ValueError('source unavailable')), \
                patch.object(liquidity, 'get', return_value=SimpleNamespace(text='\n'.join(rows))), \
                patch.object(liquidity, 'datetime', SimpleNamespace(now=lambda tz: SimpleNamespace(date=lambda: TODAY))):
            path = Path(tmp)/'liquidity_tga.json'
            path.write_text('{"existing":"preserve"}',encoding='utf-8')
            before = path.read_bytes()
            self.assertEqual(liquidity.run(),1)
            self.assertEqual(path.read_bytes(),before)
            doc = json.loads((Path(tmp)/'liquidity_rrp.json').read_text(encoding='utf-8'))
            self.assertEqual(len(next(iter(doc['series'].values()))),250)


if __name__ == '__main__':
    unittest.main()
