import copy
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bs4 import BeautifulSoup
import fetch_yangshan as y

TODAY = '2026-10-02'
URL = 'https://youse.mysteel.com/a/26093011/FD4DC4475C47526B.html'


def soup(text):
    return BeautifulSoup(text, 'html.parser')


def smm():
    return soup('<table>' + ''.join(f'<tr><td>洋山铜溢价({k})</td><td>110~128</td><td>119</td><td>0</td><td>美元/吨</td><td>2026-09-30</td></tr>' for k in ('仓单', '提单')) + '</table>')


def article():
    text = '<h1>Mysteel快讯：9月30日上海美金铜市场升贴水</h1><meta name="publish" content="2026-09-30 11:45"><p>美元/吨</p><table><tr><td>最低价</td><td>最高价</td><td>中间价</td></tr>'
    for kind in ('仓单', '提单'):
        for grade in ('火法', '湿法'):
            text += f'<tr><td>{kind}</td><td>{grade}</td><td>-20</td><td>-10</td><td>-15</td><td>0</td><td>QP10</td></tr>'
    return soup(text + '</table>')


class RefreshTests(unittest.TestCase):
    def test_parsers_and_security_gate(self):
        self.assertEqual(len(y.parse_smm(smm(), TODAY)), 2)
        rows = y.parse_mysteel(article(), URL, TODAY)
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0]['midpoint'], -15)
        with self.assertRaises(ValueError):
            y.parse_mysteel(article(), URL, '2026-09-29')
        with self.assertRaises(ValueError):
            y.parse_mysteel(soup(str(article()).replace('9月30日', '9月29日')), URL, TODAY)
        with self.assertRaises(ValueError):
            y.article_links(soup('安全验证'), TODAY)
        self.assertEqual(y.article_links(soup(f'<a href="{URL}">上海美金铜市场升贴水</a><a href="https://example.com/a/26093011/x.html">上海美金铜市场升贴水</a>'), TODAY), [URL])

    def test_merge_preserves_history_and_rejects_revisions(self):
        doc = json.loads((y.OUT / 'comm_copper_yangshan_smm.json').read_text(encoding='utf-8'))
        rows = y.parse_smm(smm(), TODAY)
        # Build a consistent synthetic prior document independent of live values.
        doc['source_records'] = rows
        doc['series'] = {name: [['2026-09-29', 118], ['2026-09-30', 119]] for name in y.CONTRACTS.values()}
        new = y.merge(doc, rows, TODAY)
        self.assertEqual(len(new['series']['창고증권']), 2)
        bad = copy.deepcopy(rows)
        bad[0].update(low=112, high=128, midpoint=120)
        with self.assertRaises(ValueError):
            y.merge(doc, bad, TODAY)
        self.assertEqual(doc['series']['창고증권'][0][1], 118)

    def test_one_provider_failure_preserves_data_and_other_updates(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            before = {}
            for key in [*y.CONTRACTS, 'smm']:
                filename = f'comm_copper_yangshan_{key}.json'
                doc = json.loads((y.OUT / filename).read_text(encoding='utf-8'))
                before[key] = doc
                (out / filename).write_text(json.dumps(doc), encoding='utf-8')
            def get(url):
                if url == y.LIST_URL:
                    return soup('安全验证')
                return smm_actual
            smm_actual = soup('<table>' + ''.join(f"<tr><td>洋山铜溢价({k})</td><td>{r['low']}~{r['high']}</td><td>{r['midpoint']}</td><td>0</td><td>美元/吨</td><td>{r['date']}</td></tr>" for k, r in zip(('仓单', '提单'), sorted(before['smm']['source_records'], key=lambda r: r['contract'], reverse=True))) + '</table>')
            with patch.object(y, 'OUT', out), patch.object(y, 'get', get):
                with self.assertRaisesRegex(RuntimeError, 'Mysteel'):
                    y.run(TODAY)
            for key in y.CONTRACTS:
                after = json.loads((out / f'comm_copper_yangshan_{key}.json').read_text(encoding='utf-8'))
                self.assertEqual(after['series'], before[key]['series'])
                self.assertEqual(after['fetched'], before[key]['fetched'])
                self.assertFalse(after['collection_status']['ok'])
            self.assertTrue(json.loads((out / 'comm_copper_yangshan_smm.json').read_text(encoding='utf-8'))['collection_status']['ok'])


if __name__ == '__main__':
    unittest.main()
