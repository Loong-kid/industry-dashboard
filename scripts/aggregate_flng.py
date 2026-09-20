# -*- coding: utf-8 -*-
"""FLNG 선단 수기입력 CSV → data/natgas/flng_fleet.json (표 + 누적 용량 시계열).

`manual/flng_fleet.csv`를 손으로 관리한다. **FLNG는 선박별 소유·용선·인도 정보를 담은
무료 정형 소스가 없다**(Baltic·Clarksons·Rystad 모두 유료) — 그래서 공개 자료를 정리해 넣는다.
행이 열 몇 개뿐이라 수기로 충분하고, 새 호선이 뜨면 CSV에 한 줄 추가하고 이 스크립트만 돌린다.

    python scripts/aggregate_flng.py
"""
import csv
import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "manual" / "flng_fleet.csv"
OUT_DIR = ROOT / "data" / "natgas"  # 천연가스 탭에 함께 둔다

SOURCE = "수기입력 (참고: EA Global LNG Capacity Tracker 도표 · 용량·연도는 공개 보도 대조)"


def run():
    rows = []
    with SRC.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if not r.get("vessel"):
                continue
            rows.append({
                "vessel": r["vessel"].strip(),
                "operator": r["operator"].strip(),
                "country": r["country"].strip(),
                "field": r["field"].strip(),
                "model": r["model"].strip(),
                "status": r["status"].strip(),
                "start_year": int(r["start_year"]) if r["start_year"].strip() else None,
                "mtpa": float(r["mtpa"]) if r["mtpa"].strip() else None,
                "note": r.get("note", "").strip(),
            })
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    today = dt.date.today().isoformat()
    live = [r for r in rows if r["status"] == "가동중"]
    building = [r for r in rows if r["status"] != "가동중"]
    live_cap = sum(r["mtpa"] for r in live if r["mtpa"])
    build_cap = sum(r["mtpa"] for r in building if r["mtpa"])

    (OUT_DIR / "flng_fleet.json").write_text(json.dumps({
        "id": "flng_fleet", "name": "전세계 FLNG 선단",
        "source": SOURCE, "source_url": "", "updated": today, "fetched": today,
        "manual": True,
        "note": (f"가동중 {len(live)}기 {live_cap:.1f} MTPA · 건조중 {len(building)}기 {build_cap:.1f} MTPA. "
                 "사업모델이 '자가 액화용'이면 가스전 보유사가 자기 가스를 액화하는 것이고, "
                 "'액화 서비스'면 선주가 배만 빌려주고 수수료를 받는 구조다(Golar가 이 방식). "
                 "수기 관리 파일이라 새 호선·용선 변경은 manual/flng_fleet.csv에 직접 추가한다."),
        "cols": [
            {"key": "vessel", "label": "선박"},
            {"key": "operator", "label": "운영사"},
            {"key": "country", "label": "위치"},
            {"key": "mtpa", "label": "용량(MTPA)", "align": "right", "fmt": "num"},
            {"key": "model", "label": "사업모델"},
            {"key": "status", "label": "상태"},
            {"key": "start_year", "label": "가동(예정)", "align": "right"},
            {"key": "field", "label": "가스전"},
            {"key": "note", "label": "비고"},
        ],
        "rows": rows,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    # 연도별 누적: FLNG가 실제로 얼마나 빠르게 늘었는지 (건조중은 예정연도에 얹는다)
    cum, total = [], 0.0
    for r in sorted([r for r in rows if r["start_year"] and r["mtpa"]], key=lambda r: r["start_year"]):
        total = round(total + r["mtpa"], 2)
        cum.append([f"{r['start_year']}-01-01", total, r["status"]])
    live_pts = [[d, v] for d, v, s in cum if s == "가동중"]
    all_pts = [[d, v] for d, v, _ in cum]
    (OUT_DIR / "flng_capacity.json").write_text(json.dumps({
        "id": "flng_capacity", "name": "FLNG 누적 액화용량", "unit": "MTPA", "frequency": "yearly", "full_range": True,
        "source": SOURCE, "source_url": "", "updated": today, "fetched": today, "manual": True,
        "default_series": ["가동중 누적", "건조중 포함"],
        "description": (
            "떠 있는 액화설비(FLNG)가 해마다 얼마나 쌓였는지. 육상 터미널과 달리 배라서 가스전이 고갈되면 "
            "다른 가스전으로 옮겨갈 수 있고, 그래서 매장량이 작거나 육상 부지가 어려운 곳을 연다. "
            "위 미국 육상 프로젝트(단일 트레인 5 MTPA 안팎)와 견주면 한 기의 크기를 가늠할 수 있다."
        ),
        "note": "첫 가동연도에 그 배의 설계용량을 한꺼번에 얹은 단순 누적이다. 램프업 기간은 반영하지 않았다.",
        "series": {"가동중 누적": live_pts, "건조중 포함": all_pts},
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"  FLNG {len(rows)}기 (가동 {len(live)}/{live_cap:.1f} MTPA · 건조 {len(building)}/{build_cap:.1f} MTPA)")


if __name__ == "__main__":
    run()
