import copy
import json
from pathlib import Path
import unittest

import aggregate_gpu_specs as gpu

ROOT=Path(__file__).resolve().parents[1]


class GPUSpecs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        read=lambda name:json.loads((ROOT/'manual'/name).read_text(encoding='utf8'))
        cls.raw=read('gpu_specs_sheet.json');cls.extra=read('gpu_specs_supplements.json')
        cls.dates=read('gpu_release_dates.json')
        cls.ai_raw=read('nvidia_ai_sheet.json');cls.reviews=read('nvidia_ai_reviews.json')
        cls.doc=gpu.build_gpu(cls.raw,cls.extra,cls.dates);cls.ai=gpu.build_ai(cls.ai_raw,cls.reviews)

    def test_all_source_gpu_values_and_order_are_preserved(self):
        self.assertEqual(len(self.doc['rows']),40)
        self.assertEqual([r['source_values'] for r in self.doc['rows']],[(r+['']*26)[:26] for r in self.raw['values'][1:]])
        self.assertEqual(self.doc,json.loads((ROOT/'data/semicon/gpu_specs.json').read_text(encoding='utf8')))
        self.assertEqual(self.ai,json.loads((ROOT/'data/semicon/nvidia_ai_specs.json').read_text(encoding='utf8')))

    def test_benchmarks_have_explicit_api_and_device_scope(self):
        self.assertEqual(sum(len(r['reviews']) for r in self.doc['rows']),152)
        rows={r['name']:r for r in self.doc['rows']}
        for row in self.doc['rows']:
            for key,cell in row['reviews'].items():
                if key in ('announced','released'):continue
                self.assertFalse(row['original'].get(key))
                self.assertIn(key,('gb7_opencl','gb7_vulkan','N'))
                self.assertIn('장치명' if key.startswith('gb7_') else '이론 상한',cell['note'])
                self.assertIn(cell['source'],self.doc['sources'])
        self.assertEqual(rows['GeForce RTX 5090']['reviews']['gb7_opencl']['value'],'369574')
        self.assertEqual(rows['GeForce RTX 5090 Laptop GPU']['reviews']['gb7_opencl']['value'],'195934')
        self.assertNotIn('gb7_opencl',rows['Intel Iris Xe Graphics G7 96EU']['reviews'])
        self.assertNotIn('gb7_vulkan',rows['Intel Iris Xe Graphics G7 96EU']['reviews'])
        self.assertIn('VRAM',rows['GeForce RTX 3060 12GB']['reviews']['gb7_opencl']['note'])
        self.assertEqual(rows['GeForce RTX 5090 Laptop GPU']['reviews']['N']['value'],'최대 45.34 · 이론 산출')
        self.assertIn('10496',rows['GeForce RTX 5090 Laptop GPU']['reviews']['N']['note'])
        self.assertFalse(rows['GeForce RTX 5090 Laptop GPU']['original']['N'])

    def test_moved_row_or_existing_cell_cannot_be_silently_overwritten(self):
        extra=copy.deepcopy(self.extra);extra['cells'][0]['column']='C'
        with self.assertRaises(ValueError):gpu.build_gpu(self.raw,extra,self.dates)
        raw=copy.deepcopy(self.raw);raw['values'][self.extra['cells'][0]['row']-1][2]='Another GPU'
        with self.assertRaises(ValueError):gpu.build_gpu(raw,self.extra,self.dates)
        reviews=copy.deepcopy(self.reviews);reviews['products'][0]['product']='Another GPU'
        with self.assertRaises(ValueError):gpu.build_ai(self.ai_raw,reviews)

    def test_announcement_and_availability_are_separate_with_source_precision(self):
        rows={r['sheet_row']:r for r in self.doc['rows']}
        for row in rows.values():
            self.assertIn('released',row['reviews'])
            self.assertEqual(row['original']['E'],row['source_values'][4])
            for key in ('announced','released'):
                if key not in row['reviews']:continue
                cell=row['reviews'][key]
                gpu.validate_date(cell)
                self.assertIn(cell['source'],self.doc['sources'])
                self.assertTrue(cell['note'])
        self.assertEqual(rows[17]['reviews']['announced']['value'],'2024-12-03')
        self.assertEqual(rows[17]['reviews']['released']['value'],'2024-12-13')
        self.assertEqual(rows[18]['reviews']['released']['value'],'2025-01-16')
        self.assertEqual(rows[25]['reviews']['announced']['value'],'2025-01-06')
        self.assertEqual(rows[25]['reviews']['released']['value'],'2025-03-05')
        self.assertEqual(rows[22]['reviews']['released']['value'],'2022-Q2')
        self.assertEqual(rows[30]['reviews']['released']['precision'],'year')
        self.assertEqual(rows[35]['reviews']['released']['status'],'scheduled')
        for number in (13,14,16):
            self.assertNotIn('announced',rows[number]['reviews'])
            self.assertTrue(rows[number]['date_note'])
        self.assertEqual(self.doc['views'][0]['keys'][:2],['C','released'])

    def test_invalid_dates_and_moved_date_rows_fail_instead_of_shifting(self):
        for key,value in [('value','2025-02-30'),('value','2025-Q5'),('precision','month'),('status','announcement')]:
            dates=copy.deepcopy(self.dates)
            dates['products'][0]['fields']['released'][key]=value
            with self.assertRaises(ValueError):gpu.build_gpu(self.raw,self.extra,dates)
        dates=copy.deepcopy(self.dates);dates['products'][0]['product']='Another GPU'
        with self.assertRaises(ValueError):gpu.build_gpu(self.raw,self.extra,dates)
        dates=copy.deepcopy(self.dates);dates['products'].append(dates['products'][0])
        with self.assertRaises(ValueError):gpu.build_gpu(self.raw,self.extra,dates)

    def test_ai_preserves_source_rows_and_classifies_physical_units(self):
        self.assertEqual(len([r for r in self.ai['rows'] if r['sheet_row']]),30)
        self.assertEqual(len(self.ai['rows']),34)
        for row in self.ai['rows']:
            if row['sheet_row']:
                expected=[str(v or '') for v in self.ai_raw['values'][row['sheet_row']-1]]
                self.assertEqual(row['source_values'],expected+['']*(31-len(expected)))
        rows={r['name']:r for r in self.ai['rows']}
        self.assertEqual(rows['DGX GB200']['group'],'랙')
        self.assertEqual(rows['Full B200']['group'],'아키텍처 최대')
        self.assertEqual(rows['ConnectX-8 Super NIC']['original']['network'],'800Gb/s')
        self.assertNotIn('power',rows['ConnectX-8 Super NIC']['original'])
        self.assertFalse(rows['GK180']['reviews'])
        self.assertFalse(rows['DGX-1']['reviews'])

    def test_ai_profile_corrections_are_sourced_and_original_remains_visible(self):
        rows={r['name']:r for r in self.ai['rows']}
        h=rows['H200']
        self.assertEqual(h['original']['bandwidth'],'4.8GB/s')
        self.assertEqual(h['reviews']['bandwidth']['value'],'4.8 TB/s')
        self.assertEqual(rows['B300']['reviews']['memory']['value'],'270 GB HBM3E')
        self.assertEqual(rows['B300 NVL72 profile']['reviews']['memory']['value'],'279 GB HBM3E')
        self.assertEqual(rows['B300']['reviews']['fp4']['value'],'14 / 18 PFLOPS')
        self.assertEqual(rows['B300 NVL72 profile']['reviews']['fp4']['value'],'15 / 20 PFLOPS')
        self.assertEqual(rows['Rubin GPU']['reviews']['bandwidth']['value'],'19.2 TB/s')
        self.assertEqual(rows['Rubin architectural maximum']['reviews']['bandwidth']['value'],'22 TB/s')
        self.assertEqual(rows['GB200 NVL72']['reviews']['fp32']['value'],'5760 TFLOPS')
        self.assertEqual(rows['DGX B200']['reviews']['power']['value'],'최대 약14.3 kW · 시스템')
        for row in self.ai['rows']:
            for cell in row['reviews'].values():
                self.assertIn(cell['source'],self.ai['sources'])
                self.assertTrue(cell['note'])


if __name__=='__main__':unittest.main()
