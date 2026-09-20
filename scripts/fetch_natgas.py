# -*- coding: utf-8 -*-
"""천연가스·비료 → data/natgas/*.json (일반 시계열 카드).

구 natgas-monitor(Streamlit)의 현물·프론트·지역비교·비료 탭을 이 리포로 옮긴 것.
- 헨리허브 현물은 EIA 대신 **FRED DHHNGSP**(1997~)를 쓴다. 기존 FRED 키를 그대로 쓰고
  EIA API 키가 필요 없으며 이력도 더 길다.
- 유럽·아시아 장기(1992~)는 IMF 월간(FRED PNGASEUUSDM/PNGASJPUSDM).
- 프론트 선물·비료는 Yahoo(키 없음).

    FRED_API_KEY=... python scripts/fetch_natgas.py
"""
import datetime as dt
import json
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_commodities import fetch_yahoo  # noqa: E402
from fetch_fred import fetch_series as fetch_fred_series  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "natgas"  # 탭 id=natgas
FRED_START = "1900-01-01"  # 시리즈 시작부터(카드별 START 기본값 2010을 쓰지 않는다)

# TTF는 EUR/MWh로 호가된다 → $/MMBtu = (EUR/MWh ÷ 3.412) × EURUSD
MWH_PER_MMBTU = 3.412

# 선물 월물 코드(1~12월). Yahoo 티커는 NG{코드}{연2자리}.NYM 꼴이다(NGX26.NYM = 26년 11월물).
MONTH_CODES = "FGHJKMNQUVXZ"
HIST_CONTRACTS = 8  # 월물 추이 카드에 담을 월물 수(전부 담으면 1.2MB — 앞쪽만으로 충분)

# LNG 운임 평가치(Baltic·Spark)가 유료라, 시장이 매긴 대체 지표로 선사·수출업체 주가를 쓴다.
LNG_EQUITIES = [
    ("Flex LNG", "FLNG"),
    ("Golar LNG", "GLNG"),
    ("Capital Clean Energy", "CCEC"),
    ("Dynagas LNG", "DLNG"),
    ("Cheniere(수출터미널)", "LNG"),
]


def try_yahoo(session, ticker):
    """월물은 상장 범위 밖이면 404다(TTF는 먼 달이 비는 경우가 잦다). 없는 계약은 조용히 건너뛴다."""
    try:
        return fetch_yahoo(session, ticker)
    except Exception:  # noqa
        print(f"    (없음: {ticker})")
        return []


def next_contracts(n):
    """다음 달부터 n개월치 (라벨, 만기월 1일, 티커코드) 목록. 당월물은 만기가 코앞이라 건너뛴다."""
    today = dt.date.today()
    y, m = today.year, today.month
    out = []
    for _ in range(n):
        m += 1
        if m > 12:
            m, y = 1, y + 1
        out.append((f"{y % 100:02d}년 {m}월물", f"{y}-{m:02d}-01", f"{MONTH_CODES[m - 1]}{y % 100:02d}"))
    return out


def rebase(series_map, base=100.0):
    """여러 종목을 한 차트에서 비교하려고 첫 값을 100으로 맞춘다(주가 자릿수가 3.7~268로 제각각)."""
    out = {}
    for name, pts in series_map.items():
        if not pts:
            continue
        first = pts[0][1]
        if first:
            out[name] = [[d, round(v / first * base, 2)] for d, v in pts]
    return out


def to_map(points):
    return {d: v for d, v in points}


def convert_ttf(ttf_eur, eurusd):
    """TTF(EUR/MWh) → USD/MMBtu. 환율이 없는 날(휴장)은 직전 환율을 쓴다."""
    fx = to_map(eurusd)
    out, last = [], None
    for d, v in ttf_eur:
        last = fx.get(d, last)
        if last:
            out.append([d, round(v / MWH_PER_MMBTU * last, 3)])
    return out


def spread(a, b):
    """a − b (양쪽 다 값이 있는 날만)."""
    bm = to_map(b)
    return [[d, round(v - bm[d], 3)] for d, v in a if d in bm]


def monthly_avg(points):
    """일간 → 월평균(그 달 1일로 찍는다). FRED 월간 시리즈와 축을 맞추려고 쓴다."""
    acc = {}
    for d, v in points:
        acc.setdefault(d[:7] + "-01", []).append(v)
    return [[m, round(sum(vs) / len(vs), 3)] for m, vs in sorted(acc.items())]


def save(cid, name, unit, freq, series, source, default=None, description=None, note=None, updated=None):
    last = updated or max((p[-1][0] for p in series.values() if p), default="")
    doc = {
        "id": cid, "name": name, "unit": unit, "frequency": freq,
        "source": source, "source_url": "",
        "updated": last or dt.date.today().isoformat(),
        "fetched": dt.date.today().isoformat(),
        "default_series": default or list(series)[:2],
        "series": series,
    }
    if description:
        doc["description"] = description
    if note:
        doc["note"] = note
    (OUT_DIR / f"{cid}.json").write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"  {cid}: {len(series)}시리즈 {sum(len(v) for v in series.values()):,}점 (~{last})")


def run():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0"

    # ── 일간 ────────────────────────────────────────────────────
    hh_spot = fetch_fred_series(session, "DHHNGSP", "lin", FRED_START)
    hh_front = fetch_yahoo(session, "NG=F")
    ttf = convert_ttf(fetch_yahoo(session, "TTF=F"), fetch_yahoo(session, "EURUSD=X"))
    jkm = fetch_yahoo(session, "JKM=F")

    save("ng_prices", "천연가스 가격 (3대 지역)", "$/MMBtu", "daily",
         {"헨리허브 현물": hh_spot, "헨리허브 선물(프론트)": hh_front,
          "TTF 유럽(프론트)": ttf, "JKM 아시아(프론트)": jkm},
         "FRED(DHHNGSP) · Yahoo Finance(NG=F/TTF=F/JKM=F)",
         default=["헨리허브 현물", "TTF 유럽(프론트)", "JKM 아시아(프론트)"],
         description=(
             "미국(헨리허브)·유럽(TTF)·아시아(JKM) 천연가스 가격을 같은 단위($/MMBtu)로 모은 카드. "
             "현물은 오늘 인도분 가격, 프론트는 가장 가까운 만기 선물이다. TTF는 유로/MWh로 호가되므로 "
             "3.412로 나눠 MMBtu로 바꾸고 그날 유로달러 환율을 곱해 환산했다."
         ),
         note="헨리허브 현물(FRED)은 하루 이틀 늦게 올라온다 — 최신 움직임은 프론트 선물이 빠르다.")

    save("ng_spread", "지역 간 가격차 · 아시아-유럽 차익", "$/MMBtu", "daily",
         {"JKM − 헨리허브": spread(jkm, hh_front), "TTF − 헨리허브": spread(ttf, hh_front),
          "JKM − TTF (아시아 프리미엄)": spread(jkm, ttf)},
         "Yahoo Finance (계산)",
         default=["JKM − 헨리허브", "JKM − TTF (아시아 프리미엄)"],
         description=(
             "아시아·유럽 가격에서 미국 가격을 뺀 차이는 미국에서 가스를 사 액화·수송해 파는 LNG 차익의 "
             "크기를 가늠한다. 'JKM − TTF'는 그 화물이 아시아로 갈지 유럽으로 갈지를 가르는 값이다 — "
             "아시아가 충분히 비싸야 파나마·희망봉을 돌아 더 멀리 간다. 이 값이 벌어지면 같은 화물이 더 "
             "먼 거리를 움직여(tonne-mile 증가) 선복이 조이고, 좁혀지면 유럽에서 짧게 소화된다."
         ),
         note=("액화·수송·재기화 비용을 빼지 않은 단순 차이라 실제 차익은 이보다 작다. "
               "아시아행 판단의 통념적 기준선은 운임·경로에 따라 대략 $1~2/MMBtu다."))

    # ── 월간 장기 ───────────────────────────────────────────────
    eu_m = fetch_fred_series(session, "PNGASEUUSDM", "lin", FRED_START)
    jp_m = fetch_fred_series(session, "PNGASJPUSDM", "lin", FRED_START)
    save("ng_long", "천연가스 장기 (월간)", "$/MMBtu", "monthly",
         {"미국 헨리허브": monthly_avg(hh_spot), "유럽": eu_m, "아시아 LNG": jp_m},
         "FRED (IMF 1차산품가격 · 헨리허브 월평균)",
         default=["미국 헨리허브", "유럽", "아시아 LNG"],
         description=(
             "일간 카드가 닿지 못하는 과거까지 보는 월간 카드. 유럽·아시아는 IMF가 집계하는 1차산품 가격"
             "(1992~), 미국은 헨리허브 현물의 월평균이다. 2022년 전쟁 국면에서 유럽·아시아만 수직으로 "
             "뛰고 미국은 상대적으로 잠잠했던 구조적 분리를 한눈에 볼 수 있다."
         ),
         note="IMF 월간은 두 달가량 늦게 확정된다 — 최근 구간은 위 일간 카드를 본다.")

    # ── 비료(가스가 원료) ──────────────────────────────────────
    urea_nola = fetch_yahoo(session, "UFV=F")
    urea_brz = fetch_yahoo(session, "UFB=F")
    uan = fetch_yahoo(session, "UME=F")
    # ── 선물 커브 · 월물 추이 ───────────────────────────────────
    # Yahoo에 월물 개별 계약(NGX26.NYM 등)이 2021년부터 붙어 있다 → 스냅샷 누적 없이 과거까지 그린다.
    months = next_contracts(18)
    fx_last = fetch_yahoo(session, "EURUSD=X")[-1][1]
    raw = {}  # code → (라벨, 만기월, HH 시계열, TTF 시계열)
    for label, expiry, code in months:
        raw[code] = (label, expiry, try_yahoo(session, f"NG{code}.NYM"), try_yahoo(session, f"TTF{code}.NYM"))

    # 커브는 '같은 날 찍은 사진'이어야 한다. 먼 월물은 거래가 뜸해 마지막 값이 며칠 묵을 수 있는데,
    # 그걸 그대로 쓰면 다른 날짜의 값이 한 선에 섞여 커브 모양이 거짓이 된다 → 최신일 값만 싣는다.
    asof = max((pts[-1][0] for _, _, hh, tt in raw.values() for pts in (hh, tt) if pts), default="")
    hh_curve, ttf_curve, hh_hist, ttf_hist, skipped = [], [], {}, {}, []
    for label, expiry, hh, tt in raw.values():
        if hh:
            if hh[-1][0] == asof:
                hh_curve.append([expiry, hh[-1][1]])
            else:
                skipped.append(f"HH {label}({hh[-1][0]})")
            if len(hh_hist) < HIST_CONTRACTS:
                hh_hist[f"HH {label}"] = hh
        if tt:  # EUR/MWh → $/MMBtu (커브는 최신 환율 하나로 통일)
            if tt[-1][0] == asof:
                ttf_curve.append([expiry, round(tt[-1][1] / MWH_PER_MMBTU * fx_last, 3)])
            else:
                skipped.append(f"TTF {label}({tt[-1][0]})")
            if len(ttf_hist) < HIST_CONTRACTS:
                ttf_hist[f"TTF {label}"] = [[d, round(v / MWH_PER_MMBTU * fx_last, 3)] for d, v in tt]
    if skipped:
        print(f"    커브 제외(기준일 {asof} 값 없음): {', '.join(skipped)}")

    save("ng_curve", f"선물 커브 ({asof} 종가 기준)", "$/MMBtu", "daily",
         {"헨리허브": hh_curve, "TTF 유럽": ttf_curve},
         "Yahoo Finance (NYMEX·ICE 월물)",
         updated=dt.date.today().isoformat(),
         # 유럽은 $26, 미국은 $3 수준이라 같이 켜면 HH 커브 모양이 바닥에 눌려 안 보인다.
         # Chart.js는 꺼진 시리즈를 눈금 계산에서 빼므로 기본은 HH만 켜고 TTF는 칩으로 켜게 둔다.
         default=["헨리허브"],
         description=(
             "가로축이 거래일이 아니라 계약의 만기월인 카드. 지금 시장이 앞으로 열두 달 넘게 각 달의 가스값을 "
             "얼마로 보는지 보여준다. 겨울 월물이 솟고 봄 월물이 꺼지는 계절 모양이 기본이며, 앞쪽이 뒤쪽보다 "
             "비싸지면(백워데이션) 당장 물량이 빡빡하다는 신호다. TTF는 최신 환율로 $/MMBtu 환산했다. "
             f"점 하나하나가 서로 다른 계약이다 — 예컨대 2027-01 점은 '27년 1월물'(NGF27) 한 종목의 "
             f"{asof} 종가이며, 18개 계약의 같은 날 종가를 만기 순서로 이은 것이 이 선이다."
         ),
         note=("선을 그은 날짜는 '그 계약의 만기월'이라 미래로 뻗는다 — 기간 버튼과 무관하게 본다. "
               "위 헤드라인 숫자는 가장 먼 월물 값이고, 옆의 증감은 '직전 만기월 대비'라 시간 변화가 아니다. "
               "TTF는 Yahoo에 일부 월물만 있어 빈 달은 선이 건너뛴다(유럽 칩을 켜면 보인다)."))

    save("ng_months", "월물별 가격 추이", "$/MMBtu", "daily",
         {**hh_hist, **ttf_hist},
         "Yahoo Finance (NYMEX·ICE 월물)",
         default=[k for k in hh_hist][:2],
         description=(
             "같은 만기 계약 하나하나가 시간이 지나며 어떻게 가격이 매겨졌는지 본다. 커브가 '오늘의 사진'이라면 "
             "이쪽은 '한 달치 계약의 일대기'다. 겨울 계약이 여름 동안 얼마나 올랐는지 같은 걸 추적할 때 쓴다."
         ),
         note="칩으로 원하는 월물만 켜서 본다. TTF 월물은 최신 환율 하나로 환산해 과거 구간의 환율 변동은 반영되지 않는다.")

    # ── LNG 해운 (운임 평가치 대체: 시장이 매긴 가치) ───────────
    eq = {}
    for name, tkr in LNG_EQUITIES:
        pts = fetch_yahoo(session, tkr)
        if pts:
            eq[name] = pts
    save("lng_equities", "LNG 해운 · 수출 주가 (기준 100)", "지수", "daily", rebase(eq),
         "Yahoo Finance (FLNG/GLNG/CCEC/DLNG/LNG)",
         default=["Flex LNG", "Golar LNG"],
         description=(
             "LNG 운임에는 탱커의 BWET 같은 ETF가 없다. Baltic·Spark의 LNG 운임 평가치가 유료라, 그 대신 "
             "LNG 선사와 수출업체 주가를 같은 출발점(100)으로 맞춰 본다. 운임 자체는 아니지만 시장이 매긴 "
             "LNG 해운의 값이라, 용선료가 오르기 전에 먼저 움직이는 경우가 많다. 실제 용선료는 해운 탭 "
             "'가스선 운임'의 LNG 174k(클락슨, 주간)를 본다."
         ),
         note="주가라 금리·증자·계약 등 운임과 무관한 요인도 섞인다. Cheniere는 선사가 아니라 미국 수출 터미널 사업자다.")

    save("fertilizer", "질소비료 (요소 · UAN)", "$/톤", "daily",
         {"요소 NOLA": urea_nola, "요소 브라질(CFR)": urea_brz, "UAN": uan},
         "Yahoo Finance (UFV=F/UFB=F/UME=F)",
         default=["요소 NOLA", "요소 브라질(CFR)"],
         description=(
             "질소비료는 천연가스를 원료로 암모니아를 만들어 생산한다. 그래서 가스값이 오르면 원가가 "
             "밀려 올라가고, 특히 유럽처럼 가스가 비싼 지역은 감산으로 이어져 요소 가격을 밀어올린다. "
             "NOLA는 미국 미시시피강 하구 인도 기준, 브라질은 수입 도착도(CFR) 기준이다."
         ),
         note="UAN(UME=F)은 거래가 뜸해 값이 한동안 멈춰 있을 수 있다.")


if __name__ == "__main__":
    run()
