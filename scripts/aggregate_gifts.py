# -*- coding: utf-8 -*-
"""증여DB.csv → data/institution/gifts.json (대주주 증여 테이블).

main_sh(주요주주여부)로 대주주 vs 소액임원 구분. 기본 UI에서 소액임원 숨김.
    python scripts/aggregate_gifts.py
"""
import csv
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "_dart" / "증여DB.csv"
OUT = ROOT / "data" / "gifts" / "gifts.json"  # 전용 탭(industry id=gifts)


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


def clean_name(nm):
    """DART가 정렬용으로 한 글자씩 띄운 인명('강 덕 영') → 붙임. '홍길동 외 2인' 등은 보존."""
    nm = (nm or "").strip()
    parts = nm.split()
    if len(parts) >= 2 and all(re.fullmatch(r"[가-힣]", p) for p in parts):
        return "".join(parts)
    return nm


def iso_date(s):
    d = re.sub(r"\D", "", s or "")
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}" if len(d) >= 8 else (s or "")


def run():
    if not DB_PATH.exists():
        raise SystemExit(f"DB 없음: {DB_PATH} — 먼저 fetch_gifts.py 실행")
    rows = list(csv.DictReader(DB_PATH.open(encoding="utf-8-sig")))
    orders = []
    for r in rows:
        holder = "소액임원" if (r.get("main_sh", "-") in ("", "-")) else "대주주"
        gs = to_int(r["gift_shares"])
        after = to_int(r.get("after_shares"))
        ft = to_int(r.get("float_total"))
        # 보유자 지분율 변동전→후: 변동후 수량에 증여분을 되돌려 변동전 산출
        before = None
        if after is not None and gs is not None:
            before = after + gs if r["direction"].startswith("증여") else after - gs
        o = {
            "rcept_dt": iso_date(r["rcept_dt"]),
            "corp_name": r["corp_name"],
            "stock_code": r["stock_code"],
            "market": r["market"],
            "reporter": clean_name(r["reporter"]),
            "position": r["position"],
            "holder_type": holder,
            "main_sh": r["main_sh"],
            "direction": r["direction"],       # 증여(줌) / 수증(받음)
            "gift_shares": gs,
            "gift_rate": to_float(r["gift_rate"]),
            "before_rate": round(100 * before / ft, 3) if before is not None and ft else None,
            "after_rate": round(100 * after / ft, 3) if after is not None and ft else None,
            "counterparty": clean_name(r["counterparty"]),
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
