"""Compact the 2025-era benchmarks from Epoch AI's public benchmark_data.zip (CC BY 4.0).

Usage: python scripts/extract_epoch_benchmarks.py [path/to/benchmark_data.zip]
Without a path the zip is downloaded from https://epoch.ai/data/benchmark_data.zip.
"""
import csv
import io
import json
import sys
import urllib.request
import zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'manual/ai-overview/epoch-benchmarks.json'
URL = 'https://epoch.ai/data/benchmark_data.zip'
# key: (file, score column, scale divisor, extra columns kept)
BENCHMARKS = {
    'gpqa': ('gpqa_diamond.csv', 'Best score (across scorers)', 1, []),
    'aime': ('otis_mock_aime_2024_2025.csv', 'Best score (across scorers)', 1, []),
    'frontiermath': ('frontiermath.csv', 'Best score (across scorers)', 1, []),
    'swe': ('swe_bench_verified.csv', 'Best score (across scorers)', 1, []),
    'simpleqa': ('simpleqa_verified.csv', 'Best score (across scorers)', 1, []),
    'hle': ('hle_external.csv', 'Accuracy', 1, ['Name']),
    'arc1': ('arc_agi_external.csv', 'Score', 1, ['Name']),
    'arc2': ('arc_agi_2_external.csv', 'Score', 1, ['Name']),
    'aider': ('aider_polyglot_external.csv', 'Percent correct', 100, []),
    'metr': ('metr_time_horizons_external.csv', 'Time horizon', 1, ['METR version']),
}


def extract(zip_bytes):
    archive = zipfile.ZipFile(io.BytesIO(zip_bytes))
    names = {Path(n).name: n for n in archive.namelist()}
    result = {}
    for key, (file, column, scale, extra) in BENCHMARKS.items():
        rows = []
        for row in csv.DictReader(io.TextIOWrapper(archive.open(names[file]), encoding='utf-8')):
            version, value = (row.get('Model version') or '').strip(), (row.get(column) or '').strip()
            if not version or not value:
                continue
            item = dict(version=version, release=(row.get('Release date') or '')[:10], score=round(float(value) / scale, 5))
            for name in extra:
                if row.get(name):
                    item[name.lower().replace(' ', '_')] = row[name].strip()
            rows.append(item)
        result[key] = sorted(rows, key=lambda r: (r['version'], -r['score']))
    return result


if __name__ == '__main__':
    data = Path(sys.argv[1]).read_bytes() if len(sys.argv) > 1 else urllib.request.urlopen(
        urllib.request.Request(URL, headers={'User-Agent': 'industry-dashboard research'}), timeout=120).read()
    doc = dict(source='https://epoch.ai/benchmarks', download=URL, retrieved=date.today().isoformat(),
               license='CC BY 4.0', citation="Epoch AI, 'Capabilities & benchmarking'. Retrieved from https://epoch.ai/benchmarks",
               benchmarks=extract(data))
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=0) + '\n', encoding='utf-8')
    print(OUT, {k: len(v) for k, v in doc['benchmarks'].items()})
