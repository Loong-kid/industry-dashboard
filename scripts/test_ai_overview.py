import json
import unittest
from pathlib import Path

from build_ai_overview import ROOT, SOURCE, build, display, grid, letter


class AIOverviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = json.loads(SOURCE.read_text(encoding='utf-8'))
        cls.docs = build(cls.snapshot)

    def test_generated_tables_match_snapshot(self):
        for key, doc in self.docs.items():
            self.assertEqual(doc, json.loads((ROOT / 'data/datacenter' / (key+'.json')).read_text(encoding='utf-8')))
            self.assertEqual(doc['imported'], '2026-11-04')
            self.assertTrue(doc['manual'])
            self.assertIn('#gid=', doc['source']['tab_url'])
        self.assertEqual([(len(t['rows']), len(t['columns'])) for d in self.docs.values() for t in d['tables']], [(110,44),(9,5),(11,8)])

    def test_all_visible_cells_and_notes_survive_without_conversions(self):
        for doc in self.docs.values():
            sheet = next(s for s in self.snapshot['sheets'] if s['properties']['sheetId'] == doc['source']['sheet_id'])
            source = grid(sheet)
            for table in doc['tables']:
                for column in table['columns']:
                    cell = source[1].get(column['index'], {})
                    self.assertEqual(column['source_label'], display(cell))
                    self.assertEqual(column['note'], cell.get('note',''))
                for row in table['rows']:
                    for column in table['columns']:
                        cell = source[row['source_row']].get(column['index'], {})
                        actual = row['cells'].get(column['key'], {})
                        self.assertEqual(actual.get('text',''), display(cell))
                        self.assertEqual(actual.get('note',''), cell.get('note',''))
                        if 'numberValue' in cell.get('effectiveValue',{}):
                            self.assertEqual(actual['number'], cell['effectiveValue']['numberValue'])
                        if cell.get('hyperlink'): self.assertIn(cell['hyperlink'], actual['links'])
                    self.assertEqual(row['model'], display(source[row['source_row']][next(c['index'] for c in table['columns'] if c['key']==table['model_key'])]))

    def test_provider_blocks_do_not_leak_across_empty_rows(self):
        llm = self.docs['dc_ai_overview']['tables'][0]
        self.assertEqual(llm['rows'][0]['provider'], 'Anthropic')
        self.assertTrue(llm['rows'][0]['provider_derived'])
        self.assertEqual(llm['rows'][0]['raw_provider'], '')
        image = self.docs['dc_ai_overview2']['tables'][0]
        stable = next(row for row in image['rows'] if row['model']=='stable diffusion')
        self.assertEqual(stable['provider'], '')
        china = [r for r in llm['rows'] if r['source_row']>100]
        self.assertTrue(china)
        self.assertTrue(all(r['group']=='중국' for r in china))
        self.assertEqual(len({r['id'] for r in llm['rows']}),110)

    def test_price_notes_zero_refs_and_all_column_access(self):
        llm = self.docs['dc_ai_overview']['tables'][0]
        self.assertEqual(set(llm['views'][-1]['keys']),{c['key'] for c in llm['columns']})
        self.assertNotIn('Z',llm['views'][-1]['keys'])
        self.assertNotIn('BC',llm['views'][-1]['keys'])
        video = self.docs['dc_ai_overview2']['tables'][1]
        gen = next(r for r in video['rows'] if r['model']=='Gen-4.5')
        self.assertEqual(gen['cells']['P']['text'],'0')
        self.assertEqual(gen['cells']['P']['number'],0)
        clips=[r for r in video['rows'] if r['source_row'] in [14,15]]
        self.assertTrue(all(r['cells']['M']['note']=='/clip' for r in clips))
        self.assertIn('1M token',llm['unit_note'])
        self.assertEqual(letter(63),'BK')

    def test_catalog_combines_both_source_tables_in_source_order(self):
        catalog=json.loads((ROOT/'data/catalog.json').read_text(encoding='utf-8'))
        dc=next(i for i in catalog['industries'] if i['id']=='datacenter')
        self.assertIn('ai_overview',{t['id'] for t in dc['tabs']})
        self.assertNotIn('ai_overview2',{t['id'] for t in dc['tabs']})
        sections=[s for s in dc['sections'] if s['tab']=='ai_overview']
        self.assertEqual([s['indicators'] for s in sections],[['dc_ai_overview'],['dc_ai_overview2']])
        self.assertFalse(any(s['tab']=='ai_overview2' for s in dc['sections']))
        for section in sections:
            self.assertEqual(section['table_kind'],'ai_overview')
        self.assertTrue(any(t['id']=='us' and len(t['views'])==2 for t in dc['tabs']))


if __name__=='__main__':unittest.main()
