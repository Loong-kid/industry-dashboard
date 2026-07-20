# -*- coding: utf-8 -*-
"""국내 조선 4사(HD현대중공업·삼성중공업·한화오션·대한조선) DART 수주 공시 집계.

원본: 기업\\한국\\_단일판매공급계약\\계약DB.csv
  (별도 프로젝트의 단일판매공급계약 추출기.py가 DART에서 긁어와 관리하는 통합 DB.
   그 폴더에서 `python "단일판매공급계약 추출기.py" --watchlist` 로 먼저 갱신해야 함 — 로컬 전용, CI 아님)

이 스크립트가 하는 일:
  1. 4사 필터 + '해지' 공시 제외(수주 취소는 잔고에서 빠지는 것이라 별도 처리 대상, 현재는 단순 제외)
  2. contract_name에서 선종·척수 파싱 ('유조선 2척' → 유조선/2/척)
  3. 척당 단가 계산: 원화는 계약금액÷척수, 달러는 환율 적용 후 ÷척수
     환율은 공시 원문에 박혀있는 걸 최우선으로 쓴다(회사가 실제 적용한 환율이라 가장 정확).
     못 찾으면 frankfurter.app 스팟환율로 대체(로컬 캐시).
  4. industry-dashboard/data/shipbuilding/korea_orders.json 저장 (테이블 전용, 시계열 아님)

python scripts/aggregate_korea_orders.py
"""
import csv
import json
import re
import sys
from datetime import date
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA_DIR, norm_date, to_float

DART_DB = Path(r"c:\Users\공도일\Desktop\코딩\기업\한국\_단일판매공급계약\계약DB.csv")
FX_CACHE_PATH = Path(__file__).resolve().parent / "_fx_cache.json"
TARGET_COMPANIES = ["HD현대중공업", "삼성중공업", "한화오션", "대한조선"]

# 계약명 → (선종, 척수, 단위). '(157,000 DWT)' 같은 스펙 괄호는 건너뛰고 끝의 'N척/N기'만 인식.
# 매치 안 되면(EPC 공사, 예비작업 등 선박이 아닌 계약) count=None으로 테이블엔 남기되 척당단가는 비움.
VESSEL_RE = re.compile(r"^(.*?)\s*(?:\([^)]*\))?\s*(\d+)\s*(척|기)\s*$")

VESSEL_CATEGORY_RULES = [
    (("유조선", "VLCC", "원유운반선", "P/C", "PC선", "MR", "탱커", "에탄", "제품운반선"), "탱커"),
    (("LNG",), "LNG선"),
    (("VLGC", "LPG", "가스"), "가스선"),
    (("컨테이너",), "컨테이너선"),
    (("벌커", "벌크", "케이프", "파나막스"), "벌크선"),
    (("해양생산설비", "FPSO", "FSRU", "플랜트", "Plant", "해상풍력"), "해양·특수설비"),
]

# 공시 원문에 박힌 환율 문구의 4가지 실측 변형:
#   '1USD = 1,180.30원' / 'USD 1 = 1,481.40원' / '@1,531.8/$' / '(1,505.80원/$)'
FX_PATTERNS = [
    re.compile(r"(?:1\s*USD|USD\s*1|1\s*\$|\$\s*1)\s*=\s*([\d,]+(?:\.\d+)?)\s*원", re.I),
    re.compile(r"([\d,]{3,}(?:\.\d+)?)\s*원?\s*/\s*\$"),
]


def parse_vessel(name: str):
    m = VESSEL_RE.match(name.strip())
    if not m:
        return name.strip(), None, None
    vessel_type, count, unit = m.group(1).strip(), int(m.group(2)), m.group(3)
    return (vessel_type or name.strip()), count, unit


def categorize(vessel_type: str) -> str:
    for keywords, cat in VESSEL_CATEGORY_RULES:
        if any(k.lower() in vessel_type.lower() for k in keywords):
            return cat
    return "기타"


def extract_disclosed_fx(html_path: str):
    if not html_path or not Path(html_path).exists():
        return None
    text = Path(html_path).read_text(encoding="utf-8", errors="replace")
    for pat in FX_PATTERNS:
        m = pat.search(text)
        if m:
            rate = to_float(m.group(1))
            if rate and 500 < rate < 3000:  # 상식적인 USD/KRW 범위만 채택(오탐 방지)
                return rate
    return None


def load_fx_cache() -> dict:
    if FX_CACHE_PATH.exists():
        return json.loads(FX_CACHE_PATH.read_text(encoding="utf-8"))
    return {}


def save_fx_cache(cache: dict) -> None:
    FX_CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")


def spot_fx(date_iso: str, cache: dict):
    """공시에 환율이 없을 때의 폴백: 해당 날짜의 USD/KRW 스팟환율(frankfurter.app, 무료/무인증)."""
    if date_iso in cache:
        return cache[date_iso]
    try:
        r = requests.get(f"https://api.frankfurter.app/{date_iso}?from=USD&to=KRW", timeout=15)
        r.raise_for_status()
        rate = r.json().get("rates", {}).get("KRW")
        cache[date_iso] = rate
        return rate
    except Exception:
        cache[date_iso] = None
        return None


def run():
    if not DART_DB.exists():
        print(f"DART DB 없음: {DART_DB}")
        print('먼저 기업\\한국 폴더에서 `python "단일판매공급계약 추출기.py" --watchlist` 실행 필요')
        return

    with DART_DB.open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    fx_cache = load_fx_cache()
    orders = []
    disclosed_hits, spot_hits, no_fx = 0, 0, 0

    for r in rows:
        corp = r.get("corp_name", "")
        if corp not in TARGET_COMPANIES:
            continue
        if "해지" in (r.get("report_nm") or ""):  # 수주 취소 공시는 제외
            continue
        amt_raw = r.get("contract_amount", "")
        if not amt_raw or not amt_raw.isdigit():
            continue
        amount_krw = int(amt_raw)

        # HD현대중공업 일부 양식은 '체결계약명' 대신 '판매ㆍ공급계약구분' 섹션의 '세부내용'에
        # 계약명이 들어있어 공용 추출기의 contract_name이 비어있다. 동적 컬럼에서 보완.
        name = r.get("contract_name", "") or r.get("판매ㆍ공급계약구분_세부내용", "") or "(계약명 미상)"
        vessel_type, count, unit = parse_vessel(name)

        fx_rate = extract_disclosed_fx(r.get("file_path", ""))
        fx_source = "공시" if fx_rate else None
        if fx_rate:
            disclosed_hits += 1
        else:
            deal_date = r.get("deal_date") or ""
            if re.match(r"^\d{4}-\d{2}-\d{2}$", deal_date):
                fx_rate = spot_fx(deal_date, fx_cache)
                if fx_rate:
                    fx_source = "스팟환율"
                    spot_hits += 1
            if not fx_rate:
                no_fx += 1

        amount_usd = round(amount_krw / fx_rate) if fx_rate else None
        per_vessel_krw = round(amount_krw / count) if count else None
        per_vessel_usd = round(amount_usd / count) if (count and amount_usd) else None

        orders.append({
            "rcept_dt": norm_date(r.get("rcept_dt", "")),  # 다른 지표들과 동일하게 YYYY-MM-DD로 통일(기간필터 호환)
            "deal_date": r.get("deal_date", ""),
            "corp_name": corp,
            "contract_name": name,
            "vessel_type": vessel_type,
            "vessel_category": categorize(vessel_type) if count else "기타(비선박)",
            "count": count,
            "unit": unit,
            "amount_krw": amount_krw,
            "fx_rate": fx_rate,
            "fx_source": fx_source,
            "amount_usd": amount_usd,
            "per_vessel_krw": per_vessel_krw,
            "per_vessel_usd": per_vessel_usd,
            "counterparty": r.get("contract_party", ""),
            "region": r.get("region", ""),
            "contract_start": r.get("contract_start", ""),
            "contract_end": r.get("contract_end", ""),
            "is_correction": r.get("is_correction", "") == "Y",
            "is_latest": r.get("is_latest", "") == "Y",
            "rcept_no": r.get("rcept_no", ""),
            "viewer_url": r.get("viewer_url", ""),
        })

    save_fx_cache(fx_cache)

    # 정정 공시 그룹의 구버전은 표에서 제외 (원본 DB의 is_latest 그대로 신뢰)
    orders = [o for o in orders if o["is_latest"] or not o["is_correction"]]
    orders.sort(key=lambda o: o["rcept_dt"], reverse=True)

    out = {
        "id": "korea_orders",
        "name": "국내 조선 4사 수주 내역",
        "unit": "원/vessel",
        "frequency": "실시간(공시 발생 시)",
        "source": "DART 단일판매ㆍ공급계약 공시",
        "source_url": "https://dart.fss.or.kr",
        "companies": TARGET_COMPANIES,
        "orders": orders,
    }
    out_path = DATA_DIR / "shipbuilding" / "korea_orders.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out["updated"] = date.today().isoformat()
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"저장: {out_path} ({len(orders)}건)")
    print(f"환율 — 공시명시: {disclosed_hits} / 스팟폴백: {spot_hits} / 미확보: {no_fx}")
    by_corp = {}
    for o in orders:
        by_corp[o["corp_name"]] = by_corp.get(o["corp_name"], 0) + 1
    for c, n in by_corp.items():
        print(f"  {c}: {n}건")


if __name__ == "__main__":
    run()
