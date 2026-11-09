"""Coverage, original-file integrity, published content and reproducible import."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import build_aixtron_calls as calls

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

class AIXTRONCallTests(unittest.TestCase):
    def test_every_source_page_has_translation_and_source_notes_are_separate(self):
        index = read(calls.INDEX)
        self.assertEqual(len(index['documents']), 7)
        self.assertEqual(sum(d['page_count'] for d in index['documents']), 126)
        for record in index['documents']:
            detail_path = calls.ROOT / record['path']
            detail = read(detail_path)
            self.assertNotIn(b'\r', detail_path.read_bytes())
            self.assertNotIn(b'\r', (calls.ROOT / record['translation_path']).read_bytes())
            self.assertEqual(calls.sha256(detail_path), record['content_sha256'])
            self.assertEqual(calls.sha256(calls.ROOT / record['source']['path']), record['source']['sha256'])
            self.assertEqual(calls.sha256(calls.ROOT / record['translation_path']), record['translation_sha256'])
            self.assertEqual([p['page'] for p in detail['pages']], list(range(1, record['page_count'] + 1)))
            translated = calls.read_pages((calls.MANUAL / (record['id'] + '-ko.md')).read_text(encoding='utf-8'))
            self.assertEqual([p['ko'] for p in detail['pages']], [p[1] for p in translated])
            self.assertTrue(all(p['en'] and p['ko'] for p in detail['pages']))
            self.assertEqual(detail['kind'] == 'transcript', record['id'] in ['2025-q1', '2025-q3'])
        self.assertEqual(index['documents'][0]['id'], '2026-q3')

    def test_numbers_and_units_are_not_silently_repaired_or_turned_into_quarterly_data(self):
        q1 = read(calls.PUBLIC / '2025-q1.json')['pages']
        self.assertIn('EUR 130', q1[3]['en'])
        self.assertIn('1억 3,000만 유로', q1[3]['ko'])
        self.assertTrue(q1[3]['notes'])
        self.assertIn('1.6테라헤르츠', q1[8]['ko'])
        self.assertIn('410억 유로', q1[9]['ko'])
        q2 = read(calls.PUBLIC / '2025-q2.json')['pages']
        self.assertIn('410억 달러', q2[8]['ko'])
        q3 = read(calls.PUBLIC / '2025-q3.json')['pages']
        self.assertIn('EUR246 million', q3[2]['en'])
        self.assertIn('2억 4,600만 유로', q3[2]['ko'])
        self.assertTrue(q3[2]['notes'])
        self.assertIn('수주의 약 50%', q3[9]['ko'])
        self.assertNotIn('예약', q3[9]['ko'])
        self.assertIn('첫 9개월', read(calls.PUBLIC / '2026-q3.json')['pages'][3]['ko'])

    def test_visual_word_order_preserves_bold_wafer_diameters(self):
        page = read(calls.PUBLIC / '2026-q1.json')['pages'][9]
        self.assertIn('4‑inch wafers, but are already equipped with 6‑inch conversion kits', page['en'])
        self.assertIn('4인치 웨이퍼', page['ko'])
        self.assertIn('6인치 전환 키트', page['ko'])

    def test_import_is_reproducible_and_source_pdf_bytes_are_unchanged(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'source'; source.mkdir()
            for record in read(calls.INDEX)['documents']:
                (source / record['source']['filename']).write_bytes((calls.ROOT / record['source']['path']).read_bytes())
                previous = record['previous_translation']
                if previous:
                    (source / previous['filename']).write_bytes(b'local translation fixture')
            public = root / 'public'; index = root / 'index.json'
            with patch.object(calls, 'PUBLIC', public), patch.object(calls, 'INDEX', index):
                first = calls.build(source)
                before = {p.name: p.read_bytes() for p in public.iterdir()}
                second = calls.build()
                self.assertEqual(first, second)
                self.assertEqual(before, {p.name: p.read_bytes() for p in public.iterdir()})

    def test_missing_duplicate_and_empty_pages_are_rejected(self):
        for text in ['## 원문 2쪽\n\n본문', '## 원문 1쪽\n\nA\n\n## 원문 1쪽\n\nB', '## 원문 1쪽\n\n']:
            with self.assertRaises(ValueError): calls.read_pages(text)

if __name__ == '__main__':
    unittest.main()
