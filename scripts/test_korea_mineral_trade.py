import unittest

from fetch_korea_mineral_trade import annual_rows, number, ranked_rows


def country(**changes):
    return {'ntnCd': 'CL', 'ntnKornNm': '칠레', 'incmAmt': 40, 'incmWeig': 2000,
            'expAmt': 0, 'expWeig': 0, 'sumIncmAmt': 100, 'sumIncmWeig': 5000,
            'sumExpAmt': 0, 'sumExpWeig': 0, **changes}


def payload(rows):
    return {'srchDateS': '20260101', 'srchDateE': '20260831', 'list': rows}


class TradeParserTests(unittest.TestCase):
    def test_source_totals_are_not_reconstructed_from_top_countries(self):
        result = ranked_rows(payload([country()]), '20260101', '20260831', 'I')
        self.assertEqual(result['totals']['incmAmt'], 100)
        self.assertEqual(result['countries'][0]['incmAmt'], 40)
        self.assertEqual(result['totals']['incmWeig'], 5000)

    def test_empty_country_response_is_unavailable_not_zero(self):
        result = ranked_rows(payload([]), '20260101', '20260831', 'I')
        self.assertIsNone(result['totals'])

    def test_missing_country_name_retains_the_code_and_its_weight(self):
        result = ranked_rows(payload([country(ntnCd='ZZ', ntnKornNm=None)]), '20260101', '20260831', 'I')
        self.assertEqual(result['countries'][0]['name'], '국가명 미제공(ZZ)')
        self.assertEqual(result['countries'][0]['incmWeig'], 2000)

    def test_wrong_period_duplicate_country_and_inconsistent_totals_fail(self):
        with self.assertRaises(ValueError):
            ranked_rows(payload([country()]), '20250101', '20250831', 'I')
        for rows in ([country(), country()], [country(), country(ntnCd='US', sumIncmAmt=101)],
                     [country(incmAmt=101)], [country(incmWeig=-1)],
                     [country(incmAmt=1), country(ntnCd='US', incmAmt=2)]):
            with self.assertRaises(ValueError):
                ranked_rows(payload(rows), '20260101', '20260831', 'I')

    def test_annual_values_keep_usd_kg_and_real_zero(self):
        row = {'crtrYmd': '2025', 'totalIncmAmt': 1000000, 'totalIncmWeig': 1234,
               'totalExpAmt': 0, 'totalExpWeig': 0}
        result = annual_rows([row], 2014, 2025)
        self.assertEqual(result['2025']['incmWeig'], 1234)
        self.assertEqual(result['2025']['expAmt'], 0)
        with self.assertRaises(ValueError):
            annual_rows([{**row, 'crtrYmd': '2026'}], 2014, 2025)
        with self.assertRaises(ValueError):
            annual_rows([row, row], 2014, 2025)
        with self.assertRaises(ValueError):
            annual_rows([{**row, 'totalExpAmt': None}], 2014, 2025)

    def test_invalid_values_are_rejected(self):
        self.assertEqual(number(0), 0)
        for value in (None, '', True, -1, 'NaN', 'Infinity'):
            with self.assertRaises(ValueError):
                number(value)


if __name__ == '__main__':
    unittest.main()
