"""Register user-supplied translations without editing their Markdown bytes.

Usage: python scripts/import_photomask_translations.py --source <download-folder>
The source folder must contain download-manifest.json and ko-translation/.
No translation, PDF extraction, or network requests are performed here.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / 'data/semicon/photomask_ir_library.json'
DEST = ROOT / 'data/semicon/photomask-ir-ko'


def import_translations(source):
    source = source.resolve()
    originals = json.loads((source / 'download-manifest.json').read_text(encoding='utf-8'))
    translations = source / 'ko-translation'
    manifest = json.loads((translations / 'translation-manifest.json').read_text(encoding='utf-8'))
    index = json.loads(INDEX.read_text(encoding='utf-8'))
    previous = {row['id']: row for row in index['documents']}
    by_pdf = {row['source_pdf']: row for row in manifest['documents']}
    assert len(by_pdf) == len(manifest['documents']), 'Duplicate translation source PDF'
    assert len(by_pdf) == len(originals['documents']), 'Translation/original count mismatch'
    rows, copies = [], []
    for original in originals['documents']:
        supplied = by_pdf[original['local_file']]
        assert supplied['source_sha256'] == original['sha256'], original['id']
        assert supplied['source_url'] == original['url'], original['id']
        assert supplied['period_end'] == original['period_end'], original['id']
        path = (translations / supplied['translation_file']).resolve()
        assert path.is_relative_to(translations.resolve()), 'Translation path outside source'
        raw = path.read_bytes()
        text = raw.decode('utf-8-sig')
        scope = re.search(r'^- 번역 범위: (.+)$', text, re.M)
        note = re.search(r'^- 번역 상태: (.+)$', text, re.M)
        assert scope and note and '## 원문 ' in text, f'Incomplete document: {path}'
        row = {key: value for key, value in original.items() if key not in {
            'local_file', 'bytes', 'sha256', 'qa_heading_detected', 'downloaded_pages', 'downloaded_date'
        }}
        # Retain previously verified date metadata rather than replacing it.
        row.update(previous.get(original['id'], {}))
        row['pages'] = original['downloaded_pages']
        row['verified_date'] = original['downloaded_date']
        row['translation_status'] = 'provided_draft'
        row['translation'] = {
            'path': f"data/semicon/photomask-ir-ko/{original['id']}.md",
            'scope': scope.group(1).strip(),
            'note': note.group(1).strip(),
            'review_status': supplied['status'],
            'source': 'user_provided',
            'sha256': hashlib.sha256(raw).hexdigest(),
            'registered_date': manifest['created_date'],
        }
        rows.append(row)
        copies.append((DEST / f"{original['id']}.md", raw))
    assert len({row['id'] for row in rows}) == len(rows), 'Duplicate document IDs'
    DEST.mkdir(parents=True, exist_ok=True)
    for path, raw in copies:
        path.write_bytes(raw)
    order = {company['id']: i for i, company in enumerate(index['companies'])}
    rows.sort(key=lambda row: (order[row['company']], -int(row['period_end'].replace('-', '')), row['kind']))
    index['documents'] = rows
    index['updated'] = manifest['created_date']
    index['coverage'] = {
        'start_period_end': min(row['period_end'] for row in rows),
        'end_period_end': max(row['period_end'] for row in rows),
        'document_count': len(rows),
    }
    INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Registered {len(rows)} supplied translations; Markdown bytes preserved.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    import_translations(parser.parse_args().source)
