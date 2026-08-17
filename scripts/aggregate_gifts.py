# -*- coding: utf-8 -*-
"""증여DB.csv → data/institution/gifts.json (대주주 증여 테이블).

main_sh(주요주주여부)로 대주주 vs 소액임원 구분. 기본 UI에서 소액임원 숨김.
    python scripts/aggregate_gifts.py
"""
import csv
import json
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "_dart" / "증여DB.csv"
OUT = ROOT / "data" / "institution" / "gifts.json"


def to_int(s):
    try:
        return int(str(s).replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def to_float(s):
    try:
        return float(str(s).strip())
    except (ValueError, TypeError):
        return None


def run():
    if not DB_PATH.exists():
        raise SystemExit(f"DB 없음: {DB_PATH} — 먼저 fetch_gifts.py 실행")
    rows = list(csv.DictReader(DB_PATH.open(encoding="utf-8-sig")))
    orders = []
    for r in rows:
        rd = r["rcept_dt"].replace(".", "-")
        holder = "소액임원" if (r.get("main_sh", "-") in ("", "-")) else "대주주"
        o = {
            "rcept_dt": rd,
            "corp_name": r["corp_name"],
            "stock_code": r["stock_code"],
            "market": r["market"],
            "reporter": r["reporter"],
            "position": r["position"],
            "holder_type": holder,
            "main_sh": r["main_sh"],
            "direction": r["direction"],       # 증여(줌) / 수증(받음)
            "gift_shares": to_int(r["gift_shares"]),
            "gift_rate": to_float(r["gift_rate"]),
            "counterparty": r["counterparty"],
            "rcept_no": r["rcept_no"],
        }
        orders.append(o)

    orders.sort(key=lambda o: o["rcept_dt"], reverse=True)
    markets = [m for m, _ in Counter(o["market"] for o in orders if o["market"]).most_common()]

    doc = {
        "id": "gifts",
        "name": "대주주 증여 공시",
        "unit": "건",
        "frequency": "수시(공시 발생 시)",
        "source": "DART 임원·주요주주 소유보고(증여/수증)",
        "source_url": "https://dart.fss.or.kr",
        "note": "임원·주요주주 소유보고 중 증여/수증만. 기본: 소액임원(비주요주주) 숨김. "
                "규모 = 증여 주식수·발행총수 대비 %. 편법증여+주가부양 모니터링용.",
        "updated": orders[0]["rcept_dt"] if orders else date.today().isoformat(),
        "fetched": date.today().isoformat(),
        "markets": markets,
        "holder_types": ["대주주", "소액임원"],
        "directions": ["증여(줌)", "수증(받음)"],
        "orders": orders,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    ht = Counter(o["holder_type"] for o in orders)
    print(f"완료: {len(orders):,}건 → {OUT.relative_to(ROOT)}")
    print(f"  유형 {dict(ht)}, 시장 {markets}")


if __name__ == "__main__":
    run()
