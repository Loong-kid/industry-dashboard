import copy
import unittest

from fetch_mineral_supply import parse_rows, merge_history


def sample(**overrides):
    return {'crtrYr': '2025', 'ntnEngCd': 'CL', 'ntnKornNm': '칠레',
            'massUnitCd': 'WT003', 'cdVal': 'k ton',
            'prdctnQuty': 5300000, 'burudgQuty': 180000000, **overrides}


class MineralSupplyTests(unittest.TestCase):
    def test_map_quantities_are_already_tons(self):
        countries, _, _ = parse_rows([sample()], 2019, 2025)
        self.assertEqual(countries['CL']['production'], [['2025-12-31', 5300000]])
        self.assertEqual(countries['CL']['reserves'], [['2025-12-31', 180000000]])
        countries, _, _ = parse_rows([sample(massUnitCd='WT001', cdVal='kg',
                                             prdctnQuty=900, burudgQuty=0)], 2019, 2025)
        self.assertEqual(countries['CL']['production'][0][1], 900)
        self.assertEqual(countries['CL']['reserves'], [])

    def test_missing_and_zero_reserves_are_not_zero_observations(self):
        for value in (0, None, '', 'NA', 'W'):
            countries, _, _ = parse_rows([sample(burudgQuty=value)], 2019, 2025)
            self.assertEqual(countries['CL']['reserves'], [])

    def test_rejects_wrong_units_future_years_invalid_numbers_and_duplicates(self):
        for row in (sample(cdVal='kg'), sample(crtrYr='2026'),
                    sample(prdctnQuty=-1), sample(prdctnQuty=float('nan')),
                    sample(ntnEngCd='_TOTAL_')):
            with self.assertRaises(ValueError):
                parse_rows([row], 2019, 2025)
        with self.assertRaises(ValueError):
            parse_rows([sample(), sample()], 2019, 2025)

    def test_revisions_replace_returned_years_and_preserve_older_history(self):
        old = {'CL': {'name': '칠레', 'production': [['2018-12-31', 5700000],
                        ['2025-12-31', 5200000]], 'reserves': [['2025-12-31', 190000000]]}}
        countries, _, _ = parse_rows([sample()], 2019, 2025)
        merged = merge_history(countries, old, [sample()])
        self.assertEqual(merged['CL']['production'], [['2018-12-31', 5700000], ['2025-12-31', 5300000]])
        self.assertEqual(merged['CL']['reserves'][0][1], 180000000)

    def test_explicit_withdrawal_is_not_carried_forward(self):
        old = {'CL': {'name': '칠레', 'production': [], 'reserves': [['2025-12-31', 190000000]]}}
        row = sample(burudgQuty=0)
        countries, _, _ = parse_rows([row], 2019, 2025)
        merged = merge_history(countries, old, [row])
        self.assertEqual(merged['CL']['reserves'], [])

    def test_disappearing_published_country_is_rejected(self):
        old = {'CL': {'name': '칠레', 'production': [['2025-12-31', 5300000]], 'reserves': []}}
        row = sample(ntnEngCd='PE', ntnKornNm='페루')
        countries, _, _ = parse_rows([row], 2019, 2025)
        with self.assertRaises(ValueError):
            merge_history(countries, old, [row])


if __name__ == '__main__':
    unittest.main()
