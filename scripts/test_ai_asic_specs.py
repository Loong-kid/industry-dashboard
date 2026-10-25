import copy
import json
from pathlib import Path
import unittest
import aggregate_ai_asic_specs as asic

ROOT=Path(__file__).resolve().parents[1]


class ASICSpecs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        read=lambda name:json.loads((ROOT/'manual'/name).read_text(encoding='utf8'))
        cls.raw=read('ai_asic_chip_sheet.json');cls.extra=read('ai_asic_supplements.json')
        cls.doc=asic.build(cls.raw,cls.extra)

    def test_snapshot_and_every_original_cell_are_preserved(self):
        self.assertEqual(self.doc,json.loads((ROOT/'data/semicon/ai_asic_specs.json').read_text(encoding='utf8')))
        self.assertEqual(len(self.doc['rows']),33)
        for row in self.doc['rows']:
            raw=self.raw['values'][row['sheet_row']-1]
            self.assertEqual(row['source_values'],raw+['']*(27-len(raw)))
            self.assertEqual(row['original']['name'],raw[2])
            for cell in row['reviews'].values():
                self.assertIn(cell['source'],self.doc['sources'])
                self.assertTrue(cell['note'])

    def test_corrections_keep_original_and_do_not_infer_foundries(self):
        rows={r['sheet_row']:r for r in self.doc['rows']}
        self.assertEqual(rows[56]['company'],'Microsoft')
        self.assertEqual(rows[56]['original']['company'],'')
        self.assertEqual(rows[55]['company'],'Meta')
        self.assertEqual(rows[41]['reviews']['name']['value'],'TPU7x (Ironwood)')
        self.assertEqual(rows[49]['original']['capacity'],'216')
        self.assertEqual(rows[49]['reviews']['capacity']['value'],'144 GB')
        self.assertEqual(rows[49]['reviews']['date']['value'],'2025-12-02')
        self.assertNotIn('foundry',rows[49]['reviews'])
        self.assertEqual(rows[57]['reviews']['foundry']['value'],'TSMC')
        self.assertEqual(rows[54]['reviews']['capacity']['value'],'64 GB')
        self.assertIn('합쳐진',rows[39]['review_note'])
        self.assertEqual(rows[53]['display_original']['date_basis'],'시트 전망 · 미검증')
        self.assertEqual(rows[53]['original']['date'],'2H25F')
        self.assertFalse(rows[53]['reviews'])

    def test_moved_rows_and_duplicate_cells_fail(self):
        extra=copy.deepcopy(self.extra);extra['cells'][0]['product']='Wrong chip'
        with self.assertRaises(ValueError):asic.build(self.raw,extra)
        extra=copy.deepcopy(self.extra);extra['cells'].append(extra['cells'][0])
        with self.assertRaises(ValueError):asic.build(self.raw,extra)

    def test_catalog_has_separate_spec_tab_and_source_links(self):
        catalog=json.loads((ROOT/'data/catalog.json').read_text(encoding='utf8'))
        ind=next(i for i in catalog['industries'] if i['id']=='semicon')
        self.assertEqual(next(g['name'] for g in ind['groups'] if g['id']=='ai_asic'),'AI ASIC')
        sections=[s for s in ind['sections'] if s.get('tab')=='ai_asic']
        self.assertEqual(sections[0]['indicators'],['ai_asic_specs'])
        self.assertEqual(self.doc['source_range'],'Chip!A1:AA67')
        for view in self.doc['views']:
            self.assertEqual(view['keys'][:2],['name','date'])


if __name__=='__main__':unittest.main()
