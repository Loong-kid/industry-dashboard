import unittest

from fetch_copper_world_supply import parse_chapter, build_document


def chapter(edition=2026, refinery=True):
    return f'''COPPER
U.S. Geological Survey, Mineral Commodity Summaries, February {edition}
World Mine and Refinery Production and Reserves: Reserves for the United States were revised in 2020.
Mine production
{'Refinery production' if refinery else ''}
Reserves6
{edition - 2}
{edition - 1}e
{str(edition - 2) + chr(10) + str(edition - 1) + 'e' if refinery else ''}
United States
1,050
1,000
Other countries
World total (rounded)
23,000
23,000
{'27,600' + chr(10) + '29,000' if refinery else ''}
980,000
World Resources: unrelated resource quantities 1,500,000.'''


UNIT = '(Data in thousand metric tons, copper content, unless otherwise specified)'


class CopperWorldTests(unittest.TestCase):
    def test_world_mine_and_reserves_not_refinery_or_resources(self):
        row = parse_chapter(chapter(), UNIT, 2026, 77)
        self.assertEqual(row['production'], [['2024-12-31', 23000000], ['2025-12-31', 23000000]])
        self.assertEqual(row['reserves'], [['2025-12-31', 980000000]])
        self.assertEqual(row['page'], 77)

    def test_old_three_column_chapter(self):
        row = parse_chapter(chapter(2020, False), 'thousand metric tons of copper content', 2020, 57)
        self.assertEqual(row['production'][1], ['2019-12-31', 23000000])

    def test_rejects_changed_units_columns_years_or_scope(self):
        for text, unit, edition in [(chapter(), 'metric tons', 2026), (chapter(), UNIT, 2025),
                                    (chapter().replace('Other countries', 'Missing'), UNIT, 2026),
                                    (chapter().replace('29,000', '29,000\n30,000'), UNIT, 2026),
                                    (chapter().replace('2025e', '2023e'), UNIT, 2026),
                                    (chapter().replace('23,000', '-23,000'), UNIT, 2026),
                                    (chapter().replace('980,000', '980,00'), UNIT, 2026),
                                    (chapter().replace('COPPER', 'GOLD'), UNIT, 2026)]:
            with self.subTest(text=text[:40], unit=unit, edition=edition):
                with self.assertRaises(ValueError):
                    parse_chapter(text, unit, edition, 77)

    def test_latest_production_revision_but_reserves_keep_report_vintage(self):
        rows = [parse_chapter(chapter(year), UNIT, year, 57) for year in range(2020, 2027)]
        rows[0]['production'][1][1] = 20000000
        rows[1]['production'][0][1] = 20400000
        rows[0]['reserves'][0][1] = 870000000
        doc = build_document(rows, '2026-10-05')
        self.assertEqual(doc['series']['production'][0][1], 20400000)
        self.assertEqual(doc['series']['reserves'][0][1], 870000000)
        self.assertIn('mcs2021', doc['sources']['production']['2019-12-31'])
        self.assertIn('mcs2020', doc['sources']['reserves']['2019-12-31'])
        self.assertFalse(doc['estimated']['production']['2019-12-31'])
        self.assertTrue(doc['estimated']['production']['2025-12-31'])

    def test_missing_reserves_vintage_is_rejected(self):
        rows = [parse_chapter(chapter(year), UNIT, year, 57) for year in range(2020, 2027) if year != 2023]
        with self.assertRaises(ValueError):
            build_document(rows, '2026-10-05')


if __name__ == '__main__':
    unittest.main()
