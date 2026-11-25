import json
import unittest
from pathlib import Path

from build_ai_overview import AA_COLUMNS, AA_SOURCE, EPOCH_COLUMNS, EPOCH_SOURCE, MEDIA_SOURCE, PUBLIC, ROOT, SOURCE, VALS_SOURCE, build, display, grid, letter


class AIOverviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = json.loads(SOURCE.read_text(encoding='utf-8'))
        cls.docs = build(cls.snapshot)
        cls.public = json.loads(PUBLIC.read_text(encoding='utf-8'))
        cls.integrated = build(cls.snapshot,cls.public)
        cls.aa = json.loads(AA_SOURCE.read_text(encoding='utf-8'))
        cls.vals = json.loads(VALS_SOURCE.read_text(encoding='utf-8'))
        cls.epoch = json.loads(EPOCH_SOURCE.read_text(encoding='utf-8'))
        cls.media = json.loads(MEDIA_SOURCE.read_text(encoding='utf-8'))
        cls.full = build(cls.snapshot,cls.public,cls.aa,cls.vals,cls.epoch,cls.media)

    def test_generated_tables_match_snapshot(self):
        for key, doc in self.full.items():
            self.assertEqual(doc, json.loads((ROOT / 'data/datacenter' / (key+'.json')).read_text(encoding='utf-8')))
            self.assertEqual(doc['imported'], '2026-11-04')
            self.assertTrue(doc['manual'])
            self.assertIn('#gid=', doc['source']['tab_url'])
        self.assertEqual([(len(t['rows']), len(t['columns'])) for d in self.full.values() for t in d['tables']], [(121,44+len(AA_COLUMNS)+len(EPOCH_COLUMNS)),(9+len(self.media['image']),5),(11+len(self.media['video']),8)])

    def test_aa_and_vals_fill_blanks_without_overwriting_sheet_values(self):
        before={r['id']:r for r in self.integrated['dc_ai_overview']['tables'][0]['rows']}
        table=self.full['dc_ai_overview']['tables'][0]
        rows={r['model']:r for r in table['rows']}
        for row in table['rows']:
            for key,cell in before[row['id']]['cells'].items():
                if key=='J' and cell.get('public'):continue
                self.assertEqual(row['cells'][key],cell,(row['model'],key))
        fable=rows['Claude Fable 5.2']['cells']
        self.assertEqual(fable['M']['text'],'74%')
        self.assertAlmostEqual(fable['M']['number'],0.7428,places=3)
        self.assertEqual(fable['AA']['text'],'71.3%')
        self.assertIn('Vals Index v2.2',fable['AA']['note'])
        self.assertEqual(rows['Claude Opus 5.5']['cells']['M']['text'],'61%')
        opus=rows['Claude Opus 5.5']['cells']['J']
        self.assertEqual((opus['text'],opus['original']['text']),('59 · v5','58'))
        self.assertIn('이전 공개 자료 값 57 · v5',opus['note'])
        self.assertEqual(rows['GPT-6.2 Sol']['cells']['J']['text'],'57 · v5')
        self.assertNotIn('aa_gdpval',rows['Claude Opus 4.6']['cells'])
        added=[c for c in table['columns'] if c.get('added')]
        self.assertEqual([c['key'] for c in added],[c[0] for c in AA_COLUMNS+EPOCH_COLUMNS])
        views={v['id']:v['keys'] for v in table['views']}
        self.assertEqual(set(views['all']),{c['key'] for c in table['columns']})
        self.assertTrue(set(views['summary'])>={'J','M','N','P','aa_gdpval','AA','AO'})
        for keys in views.values():
            self.assertTrue(set(keys)<={c['key'] for c in table['columns']})

    def test_public_media_rows_keep_sheet_rows_and_cite_sources(self):
        sheet={t['id']:t for t in self.docs['dc_ai_overview2']['tables']}
        full=self.full['dc_ai_overview2']
        self.assertEqual(full['public_reviewed'],self.media['imported'])
        for table in full['tables']:
            original=[r for r in table['rows'] if 'source_row' in r]
            self.assertEqual(original,sheet[table['id']]['rows'])
            added=[r for r in table['rows'] if 'source_row' not in r]
            self.assertEqual(len(added),len(self.media[table['id']]))
            for row in added:
                self.assertTrue(row['provider'])
                for cell in row['cells'].values():
                    self.assertTrue(cell['public'])
                    self.assertTrue(cell['links'] and all(l.startswith('https://') for l in cell['links']))
        image={r['model']:r['cells'] for r in full['tables'][0]['rows']}
        self.assertIn('$30/M',image['GPT Image 2.6 (Sunburst / Flare)']['D']['text'])
        self.assertEqual(image['Seedream 5.5']['D']['text'],'')
        self.assertIn('가격',image['Seedream 5.5']['D']['note'])
        video={r['model']:r['cells'] for r in full['tables'][1]['rows']}
        self.assertEqual(video['Gemini Omni 1.2 Flash']['N']['text'],'15')
        self.assertIn('미기재',video['Kling 4.0']['N']['note'])
        # new rows sit inside their provider block, newest first
        models=[r['model'] for r in full['tables'][1]['rows']]
        self.assertEqual(models.index('Gemini Omni 1.2 Flash')+1,models.index('Gemini Omni Flash'))

    def test_epoch_2025_benchmarks_match_the_right_generation(self):
        self.assertEqual(self.epoch['license'],'CC BY 4.0')
        table=self.full['dc_ai_overview']['tables'][0]
        rows={r['model']:r['cells'] for r in table['rows']}
        gpt5=rows['GPT-5']
        self.assertEqual(gpt5['e_gpqa']['text'],'86.2%')
        self.assertIn('gpt-5-2025-08-07',gpt5['e_gpqa']['note'])
        self.assertEqual(gpt5['e_metr']['text'],'3.4시간')
        # Same family name, different generation: release dates keep them apart.
        self.assertEqual((rows['Claude 3.5 Sonnet v2']['e_metr']['text'],rows['Claude 3.5 Sonnet']['e_metr']['text']),('21분','11분'))
        # '1017' belongs to the model name, so the two DeepSeek releases keep their own runs.
        self.assertIn('flash-1017',rows['DeepSeek V4.1 Flash 1017']['e_gpqa']['note'])
        self.assertNotIn('1017',rows['DeepSeek V4.1 Flash']['e_gpqa']['note'])
        self.assertNotIn('e_gpqa',rows['DeepSeek V4 Pro 0424'])
        view=next(v for v in table['views'] if v['id']=='y2025')
        self.assertTrue(set(view['keys'])>={c[0] for c in EPOCH_COLUMNS}|{'S','T','U','M'})
        for column in table['columns']:
            if column['key'].startswith('e_'):self.assertIn('CC BY 4.0',column['note'])

    def test_public_data_uses_existing_columns_and_preserves_sheet_cells(self):
        base=self.docs['dc_ai_overview']['tables'][0]
        doc=self.integrated['dc_ai_overview']
        table=doc['tables'][0]
        self.assertEqual(doc['public_reviewed'],self.public['imported'])
        self.assertEqual(table['columns'],base['columns'])
        self.assertEqual(table['views'],base['views'])
        by_id={r['id']:r for r in table['rows']}
        self.assertEqual(len(by_id),len(table['rows']))
        for row in base['rows']:
            patched=by_id[row['id']]
            self.assertEqual(patched['source_row'],row['source_row'])
            for key,original in row['cells'].items():
                cell=patched['cells'][key]
                self.assertEqual(cell.get('original',cell),original)
        sol=by_id['llm-public-gpt-6.2-sol']
        self.assertNotIn('source_row',sol)
        self.assertEqual([sol['cells'][k]['number'] for k in ('D','E','J','K','L')],[2,10,57,53,55])
        self.assertEqual(sol['cells']['J']['text'],'57 · v5')
        self.assertIn('max 57점',sol['cells']['J']['note'])
        self.assertIn('캐시 읽기 $0.1',sol['cells']['I']['text'])
        self.assertEqual(by_id['llm-r28']['cells']['L']['original']['text'],'50')
        self.assertNotIn('llm-public-gpt-6.1-sol',by_id)
        self.assertNotIn('llm-public-claude-opus-5-5',by_id)
        self.assertNotIn('llm-public-grok-4-7',by_id)
        self.assertEqual(by_id['llm-public-kimi-k3-1-pro']['group'],'중국')
        self.assertEqual(self.docs['dc_ai_overview2'],self.integrated['dc_ai_overview2'])

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
