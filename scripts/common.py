# -*- coding: utf-8 -*-
"""공통 유틸: 지표 JSON 로드/머지/저장.

지표 JSON 포맷 (data/{industry}/{id}.json):
{
  "id": "kcci",
  "name": "KCCI (KOBC 컨테이너 운임 종합지수)",
  "unit": "pt",
  "frequency": "weekly",
  "source": "한국해양진흥공사",
  "source_url": "https://...",
  "updated": "2026-07-14",
  "default_series": ["KCCI"],          # 차트에서 기본 표시할 시리즈(나머지는 범례로 토글)
  "series": { "KCCI": [["2022-11-07", 2892.0], ...], ... }
}
"""
import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def load_indicator(industry: str, ind_id: str) -> dict:
    path = DATA_DIR / industry / f"{ind_id}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"id": ind_id, "series": {}}


def collection_date() -> str:
    return datetime.now(timezone(timedelta(hours=9))).date().isoformat()


def save_indicator(industry: str, doc: dict, *, data_date: bool = False) -> None:
    path = DATA_DIR / industry / f"{doc['id']}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    doc["updated"] = max((p[0] for points in doc.get("series", {}).values() for p in points), default=collection_date()) if data_date else date.today().isoformat()
    # fetched: 수집이 실제로 돌아간 날. updated와 달리 어떤 스크립트에서도 항상 '오늘'이라,
    # 대시보드가 "이 지표 수집이 멈췄나"를 판정하는 유일한 신호다. (updated는 스크립트별로
    # 데이터 날짜를 담기도 해서 stale 판정에 쓸 수 없다.)
    doc["fetched"] = collection_date()
    if doc.get("collection_status", {}).get("kind") == "fetch_error":
        doc.pop("collection_status")
    for name, points in doc.get("series", {}).items():
        doc["series"][name] = sorted(points, key=lambda p: p[0])
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    n = sum(len(v) for v in doc["series"].values())
    print(f"  saved {path.relative_to(ROOT)} ({n} points)")


def record_fetch_failure(industry: str, ind_id: str, error: Exception) -> None:
    """실패 사실만 기록한다. 데이터 기준일/마지막 성공 수집일은 갱신하지 않는다."""
    path = DATA_DIR / industry / f"{ind_id}.json"
    if not path.exists():
        return
    doc = load_indicator(industry, ind_id)
    doc["collection_status"] = {"kind": "fetch_error", "checked": collection_date(), "ok": False,
                                "message": f"수집 실패 · {type(error).__name__}: {str(error)[:240]}"}
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")


def merge_points(doc: dict, series_name: str, new_points: list) -> int:
    """(date, value) 리스트를 기존 시리즈에 머지. 같은 날짜는 새 값으로 덮어씀."""
    existing = {p[0]: p[1] for p in doc["series"].get(series_name, [])}
    added = 0
    for d, v in new_points:
        if v is None:
            continue
        if d not in existing:
            added += 1
        existing[d] = v
    doc["series"][series_name] = [[d, existing[d]] for d in sorted(existing)]
    return added


def norm_date(s: str) -> str:
    """'20260713' | '2025.01.03' | '2025-01-03' → '2025-01-03'"""
    digits = re.sub(r"\D", "", str(s))
    return f"{digits[0:4]}-{digits[4:6]}-{digits[6:8]}"


def to_float(s) -> float | None:
    try:
        return float(str(s).replace(",", "").strip())
    except (ValueError, TypeError):
        return None
