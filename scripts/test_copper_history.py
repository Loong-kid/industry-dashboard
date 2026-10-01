import copy
import csv
import datetime as dt
import json
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

import fetch_copper_history as history
from fetch_copper_snapshot import merge_history


class HistoryTests(unittest.TestCase):
    today = dt.date(2026, 10, 1)

    def comex(self, **changes):
        data = dict(labels=['2026-09-29'], total=[100], registered=[60], eligible=[40])
        data.update(changes)
        return 'const chartData = ' + json.dumps(data) + '; const ST_TO_MT = 0.9072;'

    def test_comex_uses_raw_short_tons(self):
        self.assertEqual(history.parse_comex(self.comex(), self.today), [('2026-09-29', 100, 60, 40)])
        for changes in [dict(total=[99]), dict(eligible=[]), dict(total=[float('nan')]),
                        dict(labels=['2026-10-02']), dict(registered=[-1]), dict(total=[True])]:
            with self.assertRaises(ValueError):
                history.parse_comex(self.comex(**changes), self.today)

    def test_lme_column_date_and_missing_stock(self):
        text = '<table><tr><th>date</th><th>LME Copper Cash-Settlement</th><th>LME Copper 3-month</th><th>LME Copper stock</th></tr>'
        text += '<tr><td>30. September 2026</td><td>14,487.00</td><td>14,455.00</td><td>249,400</td></tr>'
        text += '<tr><td>29. September 2026</td><td>14,474.50</td><td>14,448.00</td><td>-</td></tr></table>'
        self.assertEqual(history.parse_lme(text, 2026, self.today), [('2026-09-30', 249400)])
        with self.assertRaises(ValueError):
            history.parse_lme(text, 2025, self.today)
        with self.assertRaises(ValueError):
            history.parse_lme(text.replace('LME Copper stock', 'LME Zinc stock'), 2026, self.today)

    def test_overlap_conflicts_and_snapshot_metadata(self):
        doc = dict(unit='톤', updated='2026-09-30', series={'stock': [['2026-09-30', 100]]})
        incoming = {'stock': [('2026-09-29', 90), ('2026-09-30', 100)]}
        merged = history.merge(copy.deepcopy(doc), incoming, 'source', 'https://example.com', 'history.csv')
        self.assertEqual(len(merged['series']['stock']), 2)
        new = copy.deepcopy(doc)
        self.assertEqual(merge_history(merged, new)['history_source'], 'source')
        for points in [[('2026-09-30', 101)], [('2026-09-28', 100)]]:
            with self.assertRaises(ValueError):
                history.merge(copy.deepcopy(doc), {'stock': points}, 'source', '', '')

    def test_csv_roundtrip_has_no_blank_records(self):
        doc = dict(history_started='2026-09-29', updated='2026-09-29', series={'stock': [['2026-09-29', 100]]})
        with tempfile.TemporaryDirectory() as folder, patch.object(history, 'OUT', Path(folder)):
            history.write(doc, [('2026-09-29', 100)], ['date', 'stock_metric_tonnes'], 'test')
            with (Path(folder) / 'history/test.csv').open(newline='', encoding='utf-8') as f:
                self.assertEqual(list(csv.reader(f)), [['date', 'stock_metric_tonnes'], ['2026-09-29', '100']])


if __name__ == '__main__':
    unittest.main()
