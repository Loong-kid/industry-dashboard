# -*- coding: utf-8 -*-
"""manual/ 폴더의 수기입력 CSV → data/ JSON 변환.

CSV 포맷: 첫 줄 헤더 `date,시리즈명1,시리즈명2,...` / 이후 `2026-02-28,182.14,...`
빈 칸은 건너뜀. 메타데이터는 manual/manifest.json 에서 관리.
"""
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, load_indicator, merge_points, save_indicator, to_float

MANUAL_DIR = ROOT / "manual"


def run():
    manifest = json.loads((MANUAL_DIR / "manifest.json").read_text(encoding="utf-8"))
    for entry in manifest:
        csv_path = MANUAL_DIR / entry["file"]
        if not csv_path.exists():
            print(f"  skip {entry['file']} (없음)")
            continue
        with open(csv_path, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.reader(f))
        header = [h.strip() for h in rows[0]] if rows else ["date"]
        # 데이터가 없어도 메타데이터는 저장 (대시보드에서 이름·수기입력 안내 표시용)
        doc = load_indicator(entry["industry"], entry["id"])
        doc.update({k: v for k, v in entry.items() if k not in ("file", "industry")})
        for col_idx, series_name in enumerate(header[1:], start=1):
            pts = []
            for row in rows[1:]:
                if len(row) <= col_idx or not row[0].strip():
                    continue
                v = to_float(row[col_idx])
                if v is not None:
                    pts.append((row[0].strip(), v))
            if pts:
                merge_points(doc, series_name, pts)
        save_indicator(entry["industry"], doc)


if __name__ == "__main__":
    run()
