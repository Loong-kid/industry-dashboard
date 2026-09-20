# -*- coding: utf-8 -*-
"""전 세계(미국 외) LNG 액화 프로젝트 수기입력 CSV → data/natgas/lng_global*.json.

**전 세계 프로젝트는 무료 자동 소스가 없다.** GEM 가스인프라 트래커가 유일한 전수 데이터인데
이메일 폼을 거쳐야 받을 수 있고(직접 링크 없음), IEA 트래커·FERC는 봇을 막는다. 그래서 큰 덩어리
프로젝트만 공개 보도를 근거로 손으로 관리한다 — 신규 물량의 대부분은 여기 담긴 소수 프로젝트다.

미국은 EIA 워크북(fetch_lng_projects.py)이 train 단위로 커버하므로 **이 파일에는 넣지 않는다**.
GEM xlsx를 확보하면 이 스크립트를 그 파서로 갈아끼우고 CSV는 보조로 내린다.

    python scripts/aggregate_global_lng.py
"""
import csv
import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "manual" / "lng_projects_global.csv"
OUT_DIR = ROOT / "data" / "natgas"
SOURCE = "수기입력 (공개 보도·기업 발표 기준, 미국 제외)"


def run():
    rows = []
    with SRC.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if not r.get("project"):
                continue
            rows.append({
                "project": r["project"].strip(),
                "operator": r["operator"].strip(),
                "country": r["country"].strip(),
                "mtpa": float(r["mtpa"]) if r["mtpa"].strip() else None,
                "status": r["status"].strip(),
                "year": int(r["start_year"]) if r["start_year"].strip() else None,
                "note": r.get("note", "").strip(),
            })
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    today = dt.date.today().isoformat()

    def cap(*statuses):
        return sum(r["mtpa"] for r in rows if r["mtpa"] and r["status"] in statuses)

    (OUT_DIR / "lng_global.json").write_text(json.dumps({
        "id": "lng_global", "name": "전세계 LNG 프로젝트 (미국 외)",
        "source": SOURCE, "source_url": "", "updated": today, "fetched": today, "manual": True,
        "note": (f"건설중 {cap('건설중'):.1f} MTPA · FID 완료 미착공 {cap('FID 완료'):.1f} · "
                 f"FID 전 {cap('FID 전'):.1f} · 제재 중단 {cap('제재 중단'):.1f}. "
                 "미국은 위 EIA 표가 train 단위로 담고 있어 여기서 뺐다. "
                 "전수가 아니라 큰 덩어리만 추린 수기 목록이며, 전 세계 전수 데이터(GEM 트래커)는 "
                 "이메일 폼 수동 다운로드라 아직 연결하지 못했다."),
        "cols": [
            {"key": "project", "label": "프로젝트"},
            {"key": "operator", "label": "운영사"},
            {"key": "country", "label": "국가"},
            {"key": "mtpa", "label": "용량(MTPA)", "align": "right", "fmt": "num"},
            {"key": "status", "label": "상태"},
            {"key": "year", "label": "가동(예정)", "align": "right"},
            {"key": "note", "label": "비고"},
        ],
        "rows": rows,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    # 연도별 신규(가동 예정연도가 있는 것만). 연도 미정은 표에서 본다.
    by_year = {}
    for r in rows:
        if r["year"] and r["mtpa"]:
            by_year[r["year"]] = round(by_year.get(r["year"], 0) + r["mtpa"], 2)
    undated = round(sum(r["mtpa"] for r in rows if r["mtpa"] and not r["year"]), 1)
    (OUT_DIR / "lng_global_timeline.json").write_text(json.dumps({
        "id": "lng_global_timeline", "name": "전세계 신규 액화용량 (미국 외)",
        "unit": "MTPA", "frequency": "yearly", "full_range": True,
        "source": SOURCE, "source_url": "", "updated": today, "fetched": today, "manual": True,
        "default_series": ["신규 가동 예정"],
        "description": (
            "미국 밖에서 어느 해에 얼마나 새로 들어오는지. 카타르 North Field 확장이 단일 프로젝트로는 "
            "세계 최대 증설이라 2027년 전후가 두껍고, 그 뒤 모잠비크·UAE·러시아 물량이 이어진다. "
            "미국 물량은 위 'EIA 미국 액화용량' 카드와 나란히 보면 전체 공급 파도가 잡힌다."
        ),
        "note": (f"가동 예정연도가 정해진 물량만 그렸다 — 연도 미정 {undated:.1f} MTPA"
                 "(제재 중단·FID 전 등)는 아래 표에서 본다. 수기 목록이라 전수가 아니다."),
        "series": {"신규 가동 예정": [[f"{y}-01-01", v] for y, v in sorted(by_year.items())]},
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"  전세계(미국 외) {len(rows)}건 · 건설중 {cap('건설중'):.1f} MTPA")


if __name__ == "__main__":
    run()
