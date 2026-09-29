"""Offline regression checks for coverage, identity and annual-scale semantics."""
import csv
import json
import unittest
from institution_registry import ROOT, institution_key, load_institutions


class InstitutionRegistryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.entries, cls.aliases = load_institutions()
        cls.by_id = {i['id']: i for i in cls.entries}

    def test_all_named_domestic_managers_in_both_dart_tables_are_covered(self):
        # Independent coverage rule, not a copy of the registry candidate regex.
        for file, field in [('대량보유DB.csv','flr_nm'), ('대량보유상세DB.csv','repror')]:
            with (ROOT/'data/_dart'/file).open(encoding='utf-8-sig') as f:
                names = {r[field] for r in csv.DictReader(f) if '운용' in r[field] or '투자자문' in r[field]}
            for name in names:
                self.assertIn(institution_key(name), self.aliases, name)

    def test_watchlist_does_not_expand_with_registry(self):
        self.assertEqual({i['id'] for i in self.entries if i['watchlist']},
                         {'miri','kabouter','grandeur_peak','wasatch','kopernik','vip','life','must'})
        self.assertGreater(len(self.entries), 500)
        self.assertEqual(len(self.entries), len(self.by_id))

    def test_legal_forms_merge_but_affiliates_do_not(self):
        self.assertEqual(institution_key('㈜ 브이아이피자산운용'),institution_key('브이아이피자산운용 주식회사'))
        self.assertNotEqual(institution_key('안다자산운용'),institution_key('안다에이치자산운용'))
        self.assertNotEqual(institution_key('JPMorganAssetManagement(UK)Limited'),institution_key('JPMorganAssetManagement(AsiaPacific)Limited'))
        self.assertEqual(self.aliases[institution_key('KB자산운용')],self.aliases[institution_key('케이비자산운용')])

    def test_annual_points_and_basis_separation(self):
        for id in ('vip','life','must'):
            points=[p for p in self.by_id[id]['aum_history'] if p['series']=='kofia_principal']
            self.assertEqual([p['date'][:4] for p in points],['2022','2023','2024','2025','2026'])
            self.assertEqual([p['period'] for p in points],['year_end']*4+['ytd'])
        life=self.by_id['life']['aum_history']
        self.assertEqual(len({p['series'] for p in life}),2)
        self.assertIn(4_104_400_000_000,[p['value'] for p in life])
        self.assertIn(5_380_300_000_000,[p['value'] for p in life])

    def test_snapshot_totals_and_absent_values(self):
        for inst in self.entries:
            points=inst['aum_history']
            self.assertEqual(len(points),len({(p['series'],p['date']) for p in points}))
            for p in points:
                self.assertTrue(p['source'].startswith('https://'))
                if p['series']=='kofia_principal' and p['value'] is not None:
                    self.assertLessEqual(abs((p['funds'] or 0)+(p['discretionary'] or 0)-p['value']),100_000_000)

    def test_generated_data_matches_registry(self):
        for name in ('major_holdings','holdings_traj'):
            data=json.loads((ROOT/f'data/institution/{name}.json').read_text(encoding='utf-8'))
            self.assertEqual(data['institutions'],self.entries)
            ids=({o['institution_id'] for o in data['orders']} if name=='major_holdings' else set(data['reporter_institutions'].values()))
            self.assertFalse(ids-set(self.by_id)-{''})


if __name__=='__main__':
    unittest.main()
