import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

import fetch_wfe_market_cap as wfe

TODAY = dt.date(2026, 10, 4)
URL = wfe.BASE + '/issue/october-2026/market-statistics'


def report(headers="<th>Jan'26</th><th>Feb'26</th>", values='<td>100</td><td>120</td>'):
    return ('<h3>Equity - Domestic market capitalisation (USD millions)</h3><table>'
            '<tr><th>Exchange Name</th>' + headers + '<th>%change Feb26</th></tr>' +
            ''.join('<tr><td>' + name + '</td>' + values + '<td>99%</td></tr>'
                    for name in ['Total for Americas', 'Total for APAC', 'Total for EMEA', 'NYSE', 'Nasdaq - US']) + '</table>'
            '<h3>Equity - Number of listed companies</h3><table><tr><td>NYSE</td><td>999999</td></tr></table>')


class WfeTests(unittest.TestCase):
    def test_capitalization_units_not_change_columns_or_listed_companies(self):
        parsed = wfe.parse_report(report(), URL, TODAY)
        self.assertEqual(parsed['values']['2026-01']['world'], 300)
        self.assertEqual(parsed['values']['2026-02']['nyse'], 120)
        points, refs = wfe.points_for(wfe.merge_reports({}, [parsed]), ['nyse', 'nasdaq'])
        self.assertEqual(points, [['2026-01-31', .0002], ['2026-02-28', .0002]])
        self.assertEqual(refs['2026-01-31']['issue'], '2026-10')

    def test_duplicate_month_discards_both_columns_does_not_guess_may(self):
        html = report("<th>Jan'26</th><th>Mar'26</th><th>Apr'26</th><th>Mar'26</th><th>Jun'26</th>",
                      '<td>100</td><td>200</td><td>300</td><td>400</td><td>500</td>')
        parsed = wfe.parse_report(html, URL, TODAY)
        self.assertEqual(list(parsed['values']), ['2026-01', '2026-04', '2026-06'])
        self.assertEqual(parsed['skipped_headers'], ['duplicate month label 2026-03'])
        self.assertNotIn('2026-05', parsed['values'])

    def test_rowspan_and_colspan_headers_preserve_explicit_year_transition(self):
        html = ('<h3>Equity - Domestic market capitalisation (USD millions)</h3><table>'
                '<tr><th rowspan="2">Exchange</th><th>2018</th><th>2019</th><th rowspan="2">%change</th></tr>'
                '<tr><th>December</th><th>January</th></tr>' +
                ''.join(f'<tr><td>{region}</td><td></td><td></td><td></td></tr>'
                        '<tr><td>Total region</td><td>100</td><td>200</td><td>100%</td></tr>'
                        for region in ['Americas','Asia - Pacific','Europe - Africa - Middle East']) + '</table>')
        parsed = wfe.parse_report(html, URL, TODAY)
        self.assertEqual(list(parsed['values']), ['2018-12','2019-01'])
        self.assertEqual(parsed['values']['2019-01']['world'], 600)

    def test_bare_months_require_explicit_observation_year(self):
        html = report('<th>Jan</th><th>Feb</th>').replace('%change Feb26', "%change Feb'19/Feb'18 USD")
        self.assertEqual(list(wfe.parse_report(html, URL, TODAY)['values']), ['2019-01','2019-02'])
        with self.assertRaisesRegex(ValueError, 'unambiguous'):
            wfe.parse_report(report('<th>Jan</th><th>Feb</th>'), URL, TODAY)

    def test_rejects_wrong_units_future_month_unordered_header_and_truncated_rows(self):
        for invalid in [report().replace('USD millions','USD billions'),
                        report().replace("Feb'26", "Oct'26"),
                        report().replace("Jan'26", "Mar'26"),
                        report(values='<td>100</td>')]:
            with self.assertRaises(ValueError):
                wfe.parse_report(invalid, URL, TODAY)

    def test_missing_region_prevents_partial_world_and_cross_vintage_totals(self):
        older = wfe.parse_report(report(), URL.replace('october','september'), TODAY)
        newer = wfe.parse_report(report(values='<td>200</td><td>300</td>').replace(
            '<td>Total for EMEA</td><td>200</td><td>300</td>', '<td>Total for EMEA</td><td></td><td>300</td>'), URL, TODAY)
        merged = wfe.merge_reports({}, [newer, older])
        self.assertEqual(merged['2026-01']['world']['value'],300)
        self.assertEqual(merged['2026-01']['americas']['issue'],'2026-09')
        self.assertEqual(merged['2026-02']['world']['value'],900)
        self.assertEqual(merged['2026-02']['world']['issue'],'2026-10')
        merged['2026-02']['nasdaq']['issue'] = '2026-09'
        points, _ = wfe.points_for(merged,['nyse','nasdaq'])
        self.assertNotIn('2026-02-28', dict(points))

    def test_discovery_stays_on_official_host_and_excludes_future_issues(self):
        html = '<a href="/issue/october-2026/market-statistics">current</a><a href="/issue/december-2026/market-statistics">future</a><a href="https://evil.example/issue/october-2026/market-statistics">external</a>'
        self.assertEqual(wfe.discover_issues(html,TODAY),[URL])

    def test_latest_invalid_report_preserves_all_published_files_and_cache(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); cache = root/'cache'; cache.mkdir()
            (root/'market_equity_global_wfe_m.json').write_text('original',encoding='utf-8')
            (cache/'wfe_monthly.json').write_text('{"observations":{}}',encoding='utf-8')
            payload = f'<a href="{URL}">latest</a>'.encode()
            with patch.object(wfe.market,'OUT',root), patch.object(wfe.market,'CACHE',cache), \
                 patch.object(wfe.market,'get',return_value=SimpleNamespace(content=payload)):
                with self.assertRaisesRegex(ValueError,'latest public report failed'):
                    wfe.run()
            self.assertEqual((root/'market_equity_global_wfe_m.json').read_text(encoding='utf-8'),'original')
            self.assertEqual((cache/'wfe_monthly.json').read_text(encoding='utf-8'),'{"observations":{}}')

    def test_regression_of_later_card_preserves_all_seven_cards_and_cache(self):
        source_cache = (wfe.market.CACHE/'wfe_monthly.json').read_text(encoding='utf-8')
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); cache=root/'cache'; cache.mkdir()
            (cache/'wfe_monthly.json').write_text(source_cache,encoding='utf-8')
            originals={}
            for path in wfe.market.OUT.glob('*_wfe_m.json'):
                doc=json.loads(path.read_text(encoding='utf-8'))
                if doc['name'].startswith('일본'):
                    latest=dt.date.fromisoformat(doc['updated'])
                    later=latest+dt.timedelta(days=32)
                    future=later.replace(day=1).isoformat()
                    doc['series']['일본 JPX'].append([future,123])
                    doc['updated']=future
                originals[path.name]=json.dumps(doc,ensure_ascii=False)
                (root/path.name).write_text(originals[path.name],encoding='utf-8')
            link=f'<a href="{URL}">latest</a>'.encode()
            def response(url):
                return SimpleNamespace(content=link if url==wfe.INDEX else (report().encode()+link))
            with patch.object(wfe.market,'OUT',root), patch.object(wfe.market,'CACHE',cache), \
                 patch.object(wfe.market,'get',side_effect=response):
                with self.assertRaisesRegex(ValueError,'regressed'):
                    wfe.run()
            self.assertEqual(len(originals),7)
            for name,original in originals.items():
                self.assertEqual((root/name).read_text(encoding='utf-8'),original)
            self.assertEqual((cache/'wfe_monthly.json').read_text(encoding='utf-8'),source_cache)


if __name__ == '__main__':
    unittest.main()
