import copy
import json
from pathlib import Path
import unittest

import aggregate_memory_specs as memory

ROOT=Path(__file__).resolve().parents[1]


class MemorySpecs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        read=lambda name:json.loads((ROOT/'manual'/name).read_text(encoding='utf8'))
        cls.raw=read('dram_specs_sheet.json');cls.extra=read('memory_specs_supplements.json')
        cls.ddr,cls.hbm=memory.build(cls.raw,cls.extra)

    def test_all_source_rows_remain_exact_and_published_files_match(self):
        self.assertEqual([len(d['rows']) for d in (self.ddr,self.hbm)],[18,16])
        for doc in (self.ddr,self.hbm):
            self.assertEqual(doc,json.loads((ROOT/'data/semicon'/f"{doc['id']}.json").read_text(encoding='utf8')))
            for row in doc['rows']:
                expected=self.raw['values'][row['sheet_row']-1]
                self.assertEqual(row['source_values'],expected+['']*(20-len(expected)))
                for cell in row['reviews'].values():
                    self.assertIn(cell['source'],doc['sources'])
                    self.assertTrue(cell['note'])
        self.assertEqual(sum(len(r['reviews']) for doc in (self.ddr,self.hbm) for r in doc['rows']),122)

    def test_ddr_generation_comparison_is_separate_from_process_notes(self):
        self.assertEqual(self.ddr['default_group'],'세대 비교')
        self.assertEqual([r['name'] for r in self.ddr['rows'] if r['group']=='세대 비교'],['SDRAM','DDR','DDR2','DDR3','DDR4','DDR5'])
        rows={r['sheet_row']:r for r in self.ddr['rows']}
        self.assertEqual(rows[9]['original']['process_nm'],'26nm')
        self.assertEqual(rows[9]['original']['data_rate'],'')
        self.assertEqual(rows[9]['original']['company'],'Hynix')
        self.assertEqual(rows[16]['original']['bandwidth'],'38.4~51.2')
        self.assertEqual(rows[16]['reviews']['bandwidth']['value'],'25.6~51.2')
        self.assertIn('64 bit',rows[16]['reviews']['bandwidth']['note'])
        self.assertEqual(rows[12]['reviews']['bandwidth']['value'],'12.8~25.6')
        self.assertEqual(rows[12]['reviews']['prefetch']['value'],'8n')
        self.assertEqual(rows[16]['reviews']['prefetch']['value'],'16n')

    def test_hbm_product_scope_units_and_development_dates_remain_explicit(self):
        rows={r['sheet_row']:r for r in self.hbm['rows']}
        self.assertEqual(rows[27]['original']['bandwidth'],'165')
        self.assertEqual(rows[27]['reviews']['bandwidth']['value'],'>2000')
        self.assertEqual(rows[27]['reviews']['io']['value'],'2048')
        self.assertEqual(rows[27]['reviews']['milestone']['value'],'개발·양산 준비')
        self.assertEqual(rows[38]['reviews']['capacity']['value'],'24~36 · 12H')
        self.assertNotIn('48',rows[38]['reviews']['capacity']['value'])
        self.assertEqual(rows[38]['reviews']['base_die']['value'],'4nm logic')
        self.assertEqual(rows[24]['reviews']['milestone_date']['value'],'2020-07-02')
        self.assertEqual(rows[24]['original']['sheet_year'],'2019')
        self.assertEqual(rows[36]['original']['die_raw'],'36')
        self.assertEqual(rows[36]['original']['die_density'],'')
        self.assertEqual(rows[36]['reviews']['die_density']['value'],'24Gb · 계산')
        self.assertIn('미확인',rows[31]['reviews']['capacity']['note'])
        self.assertEqual(rows[29]['group'],'시트 메모')
        self.assertFalse(rows[29]['reviews'])
        self.assertEqual(rows[39]['reviews']['bandwidth']['value'],'4096 · 계산 최대')
        self.assertIn('출하 미확인',rows[39]['reviews']['milestone']['value'])
        self.assertNotIn('milestone_date',rows[39]['reviews'])
        for number in (35,36):
            self.assertEqual(rows[number]['reviews']['data_rate']['value'],'최대9.2')
            self.assertEqual(rows[number]['reviews']['bandwidth']['value'],'최대1180')

    def test_missing_companies_are_only_context_and_raw_blank_is_preserved(self):
        rows={r['sheet_row']:r for r in self.hbm['rows']}
        for number in (32,34,36,39):
            self.assertEqual(rows[number]['company'],'삼성전자')
            self.assertEqual(rows[number]['original']['company'],'')
            self.assertEqual(rows[number]['reviews']['company']['source'],'sheet_context')

    def test_schema_moved_rows_and_duplicate_supplements_are_rejected(self):
        for transform in ('layout','name','duplicate','source','date','table'):
            raw=copy.deepcopy(self.raw);extra=copy.deepcopy(self.extra)
            if transform=='layout':raw['values'][20][4]='Other header'
            elif transform=='name':raw['values'][extra['cells'][0]['row']-1][0]='Another DDR'
            elif transform=='duplicate':extra['cells'].append(extra['cells'][0])
            elif transform=='source':extra['cells'][0]['source']='unknown'
            elif transform=='date':next(c for c in extra['cells'] if c['column']=='milestone_date')['value']='2026-02-30'
            else:extra['cells'][0]['table']='unknown'
            with self.assertRaises(ValueError):memory.build(raw,extra)

    def test_catalog_includes_both_tables_and_retains_nine_financial_cards(self):
        catalog=json.loads((ROOT/'data/catalog.json').read_text(encoding='utf8'))
        sections=[s for s in next(i for i in catalog['industries'] if i['id']=='semicon')['sections'] if s.get('tab')=='memory']
        self.assertEqual([s['indicators'] for s in sections[:2]],[['ddr_specs'],['hbm_specs']])
        self.assertEqual(sum(len(s['indicators']) for s in sections if s.get('type')!='table'),9)


if __name__=='__main__':unittest.main()
