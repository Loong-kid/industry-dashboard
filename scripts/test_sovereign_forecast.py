import unittest
from unittest.mock import patch

import fetch_sovereign as sovereign


class SovereignForecastMetadataTests(unittest.TestCase):
    def test_collector_persists_forecast_boundary_only_for_imf_charts(self):
        saved = {}
        values = {'USA': {2025: 100, 2026: 110, 2031: 120}}
        with patch.object(sovereign, 'FRED_KEY', 'test'), patch.object(sovereign, 'PROJ_FROM', 2026), \
                patch.object(sovereign, 'imf', return_value=values), \
                patch.object(sovereign, 'fred', return_value=[['2025-10-01', 100]]), \
                patch.object(sovereign, 'china_10y', return_value=[]), patch.object(sovereign.time, 'sleep'), \
                patch.object(sovereign, 'save', side_effect=lambda cid, doc: saved.update({cid: doc})):
            sovereign.run()
        for cid in ('sov_debt_imf', 'sov_debt_usd', 'sov_gdp', 'sov_deficit'):
            doc = saved[cid]
            self.assertEqual(doc['forecast_from'], '2026-01-01')
            self.assertEqual(doc['forecast_label'], 'IMF 전망')
            self.assertTrue(doc['year_labels'])
            self.assertIn('점선', doc['note'])
            self.assertEqual([point[0] for point in doc['series']['미국']], ['2025-01-01', '2026-01-01', '2031-01-01'])
        for cid in ('sov_debt_q', 'sov_yield_10y', 'sov_table'):
            self.assertNotIn('forecast_from', saved[cid])


if __name__ == '__main__':
    unittest.main()
