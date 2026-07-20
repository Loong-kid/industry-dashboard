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

    # 파생 지표(시계열)도 생성 → 기존 차트 인프라(카드/칩/기간필터)로 그대로 렌더됨
    build_revenue_forecast(orders, mode="progress")   # 진행기준 = 손익 매출 인식
    build_revenue_forecast(orders, mode="delivery")   # 납기 일시 = 헤비테일 현금 근사
    build_price_series(orders)


# ── 파생 1: 회사별 분기 예상매출 (진행기준 / 납기 두 방식) ─────────────
def _quarter_start(d: date) -> date:
    return date(d.year, ((d.month - 1) // 3) * 3 + 1, 1)


def _next_quarter(d: date) -> date:
    return date(d.year + 1, 1, 1) if d.month >= 10 else date(d.year, d.month + 3, 1)


REVENUE_META = {
    "progress": {
        "id": "korea_revenue_progress",
        "name": "예상 매출 — 진행기준 (손익 인식)",
        "source": "DART 공시 수주액을 건조기간에 진행기준(시간비례) 분할",
    },
    "delivery": {
        "id": "korea_revenue_delivery",
        "name": "인도시점 인식 — 헤비테일 현금 유입 근사",
        "source": "DART 공시 수주액을 인도(계약 종료)일 분기에 일시 인식",
    },
}


def build_revenue_forecast(orders, mode="progress"):
    """수주액을 분기별 흐름으로 변환. 두 방식:

    - progress(진행기준): 계약 시작~종료 건조기간에 시간 비례로 분산. 조선사가 K-IFRS상
      실제 매출(손익)을 인식하는 방식. 실제 진행률은 투입원가 기준이라 시간에 정비례하진
      않지만 개별 원가곡선이 공시에 없어 시간비례를 근사치로 사용.
    - delivery(납기): 계약금액 전액을 인도(계약 종료)일이 속한 분기에 일시 계상. 대금
      지급이 잔금 위주(헤비테일)인 경우의 '현금 유입' 시점 근사. 실제 매출 인식과는 다름.

    단위: 억원. 공시된 대형 수주만 반영하므로 회사 총매출과는 다르다.
    """
    from collections import defaultdict
    acc = defaultdict(lambda: defaultdict(float))  # company -> quarter_iso -> 억원

    def valid(s):
        return bool(re.match(r"^\d{4}-\d{2}-\d{2}$", s or ""))

    for o in orders:
        amt_eok = o["amount_krw"] / 1e8
        corp = o["corp_name"]
        end = o["contract_end"]

        if mode == "delivery":
            # 인도(종료)일 분기에 전액. 종료일 없으면 수주일 폴백.
            base = end if valid(end) else (o["deal_date"] if valid(o["deal_date"]) else o["rcept_dt"])
            if valid(base):
                acc[corp][_quarter_start(date.fromisoformat(base)).isoformat()] += amt_eok
            continue

        # progress
        start = o["contract_start"] if valid(o["contract_start"]) else o["deal_date"]
        if not valid(end):
            base = o["deal_date"] if valid(o["deal_date"]) else o["rcept_dt"]
            if valid(base):
                acc[corp][_quarter_start(date.fromisoformat(base)).isoformat()] += amt_eok
            continue
        s_d = date.fromisoformat(start) if valid(start) else date.fromisoformat(end)
        e_d = date.fromisoformat(end)
        if e_d <= s_d:
            acc[corp][_quarter_start(e_d).isoformat()] += amt_eok
            continue
        total_days = (e_d - s_d).days
        q = _quarter_start(s_d)
        while q < e_d:
            q_next = _next_quarter(q)
            overlap = (min(e_d, q_next) - max(s_d, q)).days
            if overlap > 0:
                acc[corp][q.isoformat()] += amt_eok * overlap / total_days
            q = q_next

    series = {}
    for corp in TARGET_COMPANIES:
        if corp in acc:
            series[corp] = [[q, round(v, 1)] for q, v in sorted(acc[corp].items())]

    meta = REVENUE_META[mode]
    doc = {
        "id": meta["id"],
        "name": meta["name"],
        "unit": "억원/분기",
        "frequency": "분기",
        "source": meta["source"],
        "source_url": "https://dart.fss.or.kr",
        "note": "공시된 대형 수주만 반영 — 회사 총매출과 다름.",
        "default_series": TARGET_COMPANIES,
        "series": series,
        "updated": date.today().isoformat(),
    }
    path = DATA_DIR / "shipbuilding" / f"{meta['id']}.json"
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"저장: {path} ({sum(len(v) for v in series.values())} 분기포인트, {mode})")


# ── 파생 2: 선종별 척당 단가 추이 (회사별 비교) ───────────────────────
PRICE_CATEGORIES = ["탱커", "LNG선", "가스선", "컨테이너선", "벌크선"]


def build_price_series(orders):
    """선종 카테고리별로 회사별 척당 단가(백만달러) 시계열 생성.

    카테고리마다 지표 파일 1개, 시리즈 = 회사. 수주 시점(deal_date)에 점을 찍어
    '같은 선종을 회사별로 시점에 따라 척당 얼마에 수주했나'를 클락슨 신조선가와 대조 가능.
    발주가 불규칙해 점이 드문드문 찍힘(차트가 마커로 표시).
    """
    from collections import defaultdict

    def valid(s):
        return bool(re.match(r"^\d{4}-\d{2}-\d{2}$", s or ""))

    for cat in PRICE_CATEGORIES:
        acc = defaultdict(list)  # company -> [(date, M$)]
        for o in orders:
            if o["vessel_category"] != cat or not o["per_vessel_usd"]:
                continue
            d = o["deal_date"] if valid(o["deal_date"]) else o["rcept_dt"]
            if not valid(d):
                continue
            acc[o["corp_name"]].append([d, round(o["per_vessel_usd"] / 1e6, 1)])

        series = {}
        for corp in TARGET_COMPANIES:
            if corp in acc:
                # 같은 날짜 중복은 평균
                by_date = defaultdict(list)
                for dt_, v in acc[corp]:
                    by_date[dt_].append(v)
                series[corp] = [[d, round(sum(vs) / len(vs), 1)] for d, vs in sorted(by_date.items())]

        if not series:
            continue
        cat_id = {"탱커": "tanker", "LNG선": "lng", "가스선": "gas",
                  "컨테이너선": "container", "벌크선": "bulk"}[cat]
        doc = {
            "id": f"korea_price_{cat_id}",
            "name": f"{cat} 척당 수주단가 (회사별)",
            "unit": "M$",
            "frequency": "수주 시점",
            "source": "DART 공시 (계약금액÷척수, 공시환율 적용)",
            "source_url": "https://dart.fss.or.kr",
            "default_series": list(series.keys()),
            "series": series,
            "updated": date.today().isoformat(),
        }
        path = DATA_DIR / "shipbuilding" / f"korea_price_{cat_id}.json"
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"저장: {path} ({cat}, {sum(len(v) for v in series.values())}점)")


if __name__ == "__main__":
    run()
