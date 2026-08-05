# -*- coding: utf-8 -*-
"""대량보유DB.csv → data/institution/major_holdings.json (기관 수급 테이블).

보고자를 '개인' vs '법인·기관'으로 태깅한다. 방침은 보수적:
회사를 개인으로 오분류해 숨기는 게 최악(누락)이라, 확신할 때만 개인으로 찍는다.
  - DART 전체 기업명 캐시(_corp_names.json)에 있으면 무조건 법인
  - 법인 키워드(운용/투자/캐피탈/펀드/연금/증권/은행 등) 있으면 법인
  - 그 외 '성씨로 시작하는 순수 한글 2~4자'만 개인, 나머지는 전부 법인(애매하면 법인)

키/네트워크 불필요(순수 변환). 기업명 캐시는 fetch_major_holdings.py가 유지.
    python scripts/aggregate_major_holdings.py
"""
import csv
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "_dart" / "대량보유DB.csv"
DETAIL_PATH = ROOT / "data" / "_dart" / "대량보유상세DB.csv"
CORP_NAMES_PATH = ROOT / "data" / "_dart" / "_corp_names.json"
OUT = ROOT / "data" / "institution" / "major_holdings.json"
TRAJ_OUT = ROOT / "data" / "institution" / "holdings_traj.json"
VIEWER_URL = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo={no}"


def to_float(s):
    try:
        return float(str(s).replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def load_details() -> dict:
    """rcept_no -> {stkrt, chg}. majorstock 상세(보유비율·직전대비 증감)."""
    d = {}
    if DETAIL_PATH.exists():
        with DETAIL_PATH.open(encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                d[r["rcept_no"]] = {"stkrt": to_float(r.get("stkrt")), "chg": to_float(r.get("stkrt_irds"))}
    return d

CORP_KW = [
    "자산운용", "투자자문", "일임", "인베스트", "캐피탈", "캐피털", "파트너스", "홀딩", "그룹",
    "조합", "펀드", "연금", "공단", "은행", "증권", "보험", "생명", "화재", "벤처", "에쿼티",
    "매니지", "신탁", "사모", "재단", "법인", "리츠", "뱅크", "트러스트", "자산", "운용", "투자",
    "LLC", "LTD", "CAPITAL", "MANAGEMENT", "PARTNERS", "FUND", "ASSET", "INVEST", "HOLDING",
    "GROUP", "TRUST", "EQUITY",
]
SURNAMES = set("김이박최정강조윤장임한오서신권황안송전홍유고문양손배백허남심노하곽성차주우구민류"
               "나진지엄채원천방공현함변염여추도소석선설마길위연표명기반라왕금옥육인맹제모탁국어은편용예봉")


def base_name(nm: str) -> str:
    return re.sub(r"\s*외\s*\d+\s*인", "", nm or "").strip()


def classify(flr_nm: str, corp_names: set) -> str:
    b = base_name(flr_nm)
    if not b:
        return "법인·기관"
    if b in corp_names:
        return "법인·기관"
    up = flr_nm.upper()
    if any(k.upper() in up for k in CORP_KW):
        return "법인·기관"
    if re.fullmatch(r"[가-힣]{2,4}", b) and b[0] in SURNAMES:
        return "개인"
    return "법인·기관"  # 애매하면 법인(누락 방지)


def build_trajectory():
    """상세DB(majorstock, ~최근 2년) → 종목별·보고자별 보유비율 시계열.
    연속 동일값(담보/계약변경으로 지분율 그대로)은 접어 스텝만 남긴다(용량↓, 궤적 유지)."""
    if not DETAIL_PATH.exists():
        return {}
    stocks = {}  # 종목명 → 보고자 → [(date, stkrt)]
    for r in csv.DictReader(DETAIL_PATH.open(encoding="utf-8-sig")):
        rt = to_float(r.get("stkrt"))
        if rt is None:
            continue
        stocks.setdefault(r["corp_name"], {}).setdefault(r["repror"], []).append((r["rcept_dt"], rt))
    out = {}
    for name, reps in stocks.items():
        s = {}
        for rep, pts in reps.items():
            pts.sort(key=lambda p: p[0])
            comp = []
            for i, (d, v) in enumerate(pts):
                if not comp or comp[-1][1] != v or i == len(pts) - 1:
                    comp.append([d, v])
            s[rep] = comp
        out[name] = {"s": s}
    return out


def report_label(report_nm: str):
    is_corr = "정정" in report_nm
    kind = "약식" if "약식" in report_nm else "일반"
    short = ("정정·" if is_corr else "") + kind
    return short, is_corr


def run():
    if not DB_PATH.exists():
        raise SystemExit(f"DB 없음: {DB_PATH} — 먼저 fetch_major_holdings.py 실행")
    corp_names = set(json.loads(CORP_NAMES_PATH.read_text(encoding="utf-8"))) if CORP_NAMES_PATH.exists() else set()
    if not corp_names:
        print("  경고: _corp_names.json 없음 → 기업명 대조 없이 키워드/인명 규칙만 적용")

    details = load_details()
    rows = list(csv.DictReader(DB_PATH.open(encoding="utf-8-sig")))
    orders = []
    for r in rows:
        rd = r["rcept_dt"].replace(".", "-")
        if not re.match(r"\d{4}-\d{2}-\d{2}", rd):
            digits = re.sub(r"\D", "", r["rcept_dt"])
            if len(digits) >= 8:
                rd = f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
            else:
                continue
        short, is_corr = report_label(r["report_nm"])
        det = details.get(r["rcept_no"], {})
        stkrt, chg = det.get("stkrt"), det.get("chg")
        o = {
            "rcept_dt": rd,
            "corp_name": r["corp_name"],
            "stock_code": r["stock_code"],
            "market": r["corp_cls"],
            "reporter": r["flr_nm"],
            "reporter_type": classify(r["flr_nm"], corp_names),
            "report_short": short,
            "is_correction": is_corr,
            "rcept_no": r["rcept_no"],  # 원문 URL은 렌더러에서 조립(용량 절감)
        }
        if stkrt is not None:
            o["stkrt"] = stkrt            # 보고 후 보유비율(%)
            o["chg"] = chg                # 직전대비 증감(%p)
        orders.append(o)

    orders.sort(key=lambda o: o["rcept_dt"], reverse=True)

    mkt_freq = Counter(o["market"] for o in orders)
    markets = [m for m, _ in mkt_freq.most_common()]
    reporter_types = ["법인·기관", "개인"]  # 칩 순서 고정(기본 개인 OFF)

    doc = {
        "id": "major_holdings",
        "name": "대량보유 공시 (5%룰)",
        "unit": "건",
        "frequency": "수시(공시 발생 시)",
        "source": "DART 주식등의 대량보유상황보고서",
        "source_url": "https://dart.fss.or.kr",
        "note": "코스피·코스닥 5% 대량보유 공시. 기본: 개인·지분율 변동없음(담보/계약변경) 숨김(칩으로 토글). "
                "지분율 = 직전→현재 보유비율. 5% 룰 특성상 5영업일 지연·5%↑ 변동만 포착.",
        "updated": orders[0]["rcept_dt"] if orders else date.today().isoformat(),
        "markets": markets,
        "reporter_types": reporter_types,
        "orders": orders,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    # 12k행 규모라 compact(무들여쓰기)로 저장해 용량 최소화
    OUT.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    # 종목별 지분 추이(상세DB 전체 ~2년, 테이블 1년과 별개)
    traj = build_trajectory()
    traj_doc = {"id": "holdings_traj", "name": "종목별 지분 추이",
                "updated": doc["updated"], "stocks": traj}
    TRAJ_OUT.write_text(json.dumps(traj_doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"  추이: {len(traj):,}종목 → {TRAJ_OUT.relative_to(ROOT)} ({TRAJ_OUT.stat().st_size//1024}KB)")
    tcnt = Counter(o["reporter_type"] for o in orders)
    print(f"완료: {len(orders):,}건 → {OUT.relative_to(ROOT)}")
    print(f"  시장 {dict(mkt_freq)}, 유형 {dict(tcnt)}")
    if orders:
        print(f"  기간 {orders[-1]['rcept_dt']}~{orders[0]['rcept_dt']}")


if __name__ == "__main__":
    run()
