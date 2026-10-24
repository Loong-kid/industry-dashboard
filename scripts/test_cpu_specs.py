import copy
import json
from pathlib import Path
import unittest

import aggregate_cpu_specs as specs

ROOT=Path(__file__).resolve().parents[1]


class CPUSpecs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        read=lambda path:json.loads((ROOT/path).read_text(encoding='utf8'))
        cls.raw=read('manual/cpu_specs_sheet.json')
        cls.extra=read('manual/cpu_specs_supplements.json')
        cls.doc=specs.build(cls.raw,cls.extra)

    def test_entire_sheet_values_and_order_preserved(self):
        self.assertEqual([c['label'] for c in self.doc['columns']],self.raw['values'][0])
        expected=[(i,r+['']*(37-len(r))) for i,r in enumerate(self.raw['values'][1:],2) if r]
        self.assertEqual([(r['sheet_row'],r['values']) for r in self.doc['rows']],expected)
        self.assertEqual(len(expected),292)
        self.assertEqual(len({r['values'][0] for r in self.doc['rows']}),9)
        self.assertEqual(self.doc,json.loads((ROOT/'data/semicon/cpu_specs.json').read_text(encoding='utf8')))

    def test_only_blanks_are_filled_and_each_addition_has_evidence(self):
        self.assertEqual(sum(len(r['supplements']) for r in self.doc['rows']),226)
        for row in self.doc['rows']:
            for column,cell in row['supplements'].items():
                self.assertEqual(row['values'][int(column)],'')
                self.assertTrue(self.doc['sources'][cell['source']]['url'].startswith('https://'))
                self.assertTrue(cell['note'])
        extra=copy.deepcopy(self.extra)
        extra['cells'][0]['column']=3
        with self.assertRaises(ValueError):specs.build(self.raw,extra)
        moved=copy.deepcopy(self.raw)
        moved['values'][self.extra['cells'][0]['row']-1][2]='Another CPU'
        with self.assertRaises(ValueError):specs.build(moved,self.extra)

    def test_version_and_device_scope_are_not_combined(self):
        rows={r['values'][2]:r for r in self.doc['rows']}
        m3=rows['M3 Ultra']
        self.assertEqual(m3['supplements']['31']['value'],'3156')
        self.assertEqual(m3['supplements']['32']['value'],'27515')
        self.assertIn('개별',self.doc['sources']['m3_ultra_gb6']['note'])
        self.assertEqual(m3['values'][33:35],['2918','39168'])
        snap=rows['Snapdragon X Elite']
        self.assertEqual(snap['supplements']['33']['value'],'2607')
        self.assertIn('X1E-84-100',snap['supplements']['35']['value'])
        self.assertFalse(rows['Snapdragon X2 Elite (12-core)']['supplements'])
        self.assertEqual(rows['Graviton3']['supplements']['8']['value'],'64코어')
        self.assertEqual(rows['Azure Cobalt 200']['supplements']['8']['value'],'132 active cores')


if __name__=='__main__':unittest.main()
