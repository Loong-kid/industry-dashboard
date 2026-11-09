"""Publish reviewed, user-provided AIXTRON calls without altering the source PDFs.

Initial import: python scripts/build_aixtron_calls.py --source-directory <folder>
Rebuild from checked-in originals: python scripts/build_aixtron_calls.py
"""
import argparse
import hashlib
import json
import re
import shutil
import statistics
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
MANUAL = ROOT / 'manual/aixtron-calls'
PUBLIC = ROOT / 'data/semicon/aixtron-calls'
INDEX = ROOT / 'data/semicon/aixtron_calls.json'


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_pages(text):
    parts = re.split(r'^## 원문 (\d+)쪽\s*\n', text, flags=re.M)
    if parts[0].strip():
        raise ValueError('Translation must start with a source-page heading')
    pages = [(int(parts[i]), parts[i + 1].strip()) for i in range(1, len(parts), 2)]
    if [n for n, _ in pages] != list(range(1, len(pages) + 1)) or any(not body for _, body in pages):
        raise ValueError('Missing, duplicate or empty source page')
    return pages


def english_page(page, refinitiv=False):
    """Read visual lines, including bold runs that get misplaced by text(sort=True)."""
    rows = []
    for word in sorted(page.get_text('words'), key=lambda w: ((w[1] + w[3]) / 2, w[0])):
        center = (word[1] + word[3]) / 2
        if not rows or abs(center - rows[-1]['y']) > 3:
            rows.append(dict(y=center, words=[word]))
        else:
            rows[-1]['words'].append(word)
    lines = []
    last_y = None
    gaps = [b['y'] - a['y'] for a, b in zip(rows, rows[1:]) if 8 < b['y'] - a['y'] < 45]
    paragraph_gap = statistics.median(gaps) * 1.4 if gaps else 25
    for row in rows:
        y = row['y']
        text = ' '.join(w[4] for w in sorted(row['words'], key=lambda w: w[0])).strip()
        if re.fullmatch(r'\d+', text) or '©' in text or 'REFINITIV STREETEVENTS |' in text:
            continue
        if refinitiv and (y > page.rect.height - 50 or re.match(r'OCTOBER 30, 2025 /', text)):
            continue
        if not refinitiv and y > page.rect.height - 65:
            continue
        if last_y is not None and y - last_y > paragraph_gap:
            lines.append('')
        lines.append(text)
        last_y = y
    # Joining here only removes layout line wrapping; numbers and words stay unchanged.
    paragraphs = re.split(r'\n\s*\n', '\n'.join(lines))
    return '\n\n'.join(' '.join(p.split()) for p in paragraphs).strip()


def build(source_directory=None):
    review = json.loads((MANUAL / 'review.json').read_text(encoding='utf-8'))
    PUBLIC.mkdir(parents=True, exist_ok=True)
    records = []
    for item in review['documents']:
        ident = item['id']
        original_name = ident.replace('-q', '_Q') + '.pdf'
        original = PUBLIC / (ident + '-original.pdf')
        if source_directory:
            source = Path(source_directory) / original_name
            shutil.copy2(source, original)
            if sha256(source) != sha256(original):
                raise ValueError('Original PDF changed while importing')
        with pymupdf.open(original) as pdf:
            if len(pdf) != item['pages']:
                raise ValueError('Source page count changed: ' + ident)
            english = [english_page(p, item['provider'] != 'AIXTRON') for p in pdf]
        korean = read_pages((MANUAL / (ident + '-ko.md')).read_text(encoding='utf-8'))
        if len(korean) != len(english):
            raise ValueError('Translation does not cover every source page: ' + ident)
        pages = [dict(page=n, en=en, ko=ko,
                      notes=[note['text'] for note in item['notes'] if note['page'] == n])
                 for (n, ko), en in zip(korean, english)]
        if any(len(p['en']) < 20 for p in pages):
            raise ValueError('Unreadable English page: ' + ident)
        label = ident.replace('-q', ' Q')
        kind_label = '발표 및 Q&A 전문' if item['kind'] == 'transcript' else '경영진 발표문 · Q&A 미포함'
        source = dict(filename=original_name, path=f'data/semicon/aixtron-calls/{original.name}',
                      sha256=sha256(original), provider=item['provider'])
        previous = None
        if item['previous_translation']:
            previous = dict(filename=item['previous_translation'])
            if source_directory:
                previous['sha256'] = sha256(Path(source_directory) / item['previous_translation'])
            elif INDEX.exists():
                old = json.loads(INDEX.read_text(encoding='utf-8'))
                previous = next(d['previous_translation'] for d in old['documents'] if d['id'] == ident)
        doc = dict(id=ident, label=label, date=item['date'], kind=item['kind'], kind_label=kind_label,
                   source=source, reviewed=review['reviewed'], previous_translation=previous, pages=pages)
        data_path = PUBLIC / (ident + '.json')
        data_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
        download = f'# AIXTRON {label} 컨콜 한국어 번역\n\n회의일: {item["date"]}\n\n검수일: {review["reviewed"]}\n\n자료 범위: {kind_label}\n\n{review["method"]}\n\n'
        for page in pages:
            download += f'## 원문 {page["page"]}쪽\n\n{page["ko"]}\n\n'
            for note in page['notes']:
                download += f'> 번역 검수 주: {note}\n\n'
        ko_path = PUBLIC / (ident + '-ko.md')
        ko_path.write_text(download.rstrip() + '\n', encoding='utf-8', newline='\n')
        records.append({k: v for k, v in doc.items() if k != 'pages'} | dict(
            page_count=len(pages), path=f'data/semicon/aixtron-calls/{ident}.json',
            translation_path=f'data/semicon/aixtron-calls/{ko_path.name}',
            translation_sha256=sha256(ko_path), content_sha256=sha256(data_path)))
    records.sort(key=lambda d: d['id'], reverse=True)
    index = dict(id='aixtron_calls', name='아익스트론 컨콜', updated=review['reviewed'], fetched=review['reviewed'],
                 review_method=review['method'], documents=records)
    INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    return index


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-directory', type=Path)
    result = build(parser.parse_args().source_directory)
    print(len(result['documents']), 'calls;', sum(d['page_count'] for d in result['documents']), 'source pages')
