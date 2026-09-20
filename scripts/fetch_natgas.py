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


def save(cid, name, unit, freq, series, source, default=None, description=None, note=None):
    last = max((p[-1][0] for p in series.values() if p), default="")
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

    save("ng_spread", "지역 간 가격차 (아시아·유럽 − 미국)", "$/MMBtu", "daily",
         {"JKM − 헨리허브": spread(jkm, hh_front), "TTF − 헨리허브": spread(ttf, hh_front)},
         "Yahoo Finance (계산)",
         description=(
             "아시아·유럽 가격에서 미국 가격을 뺀 차이. 미국에서 가스를 사서 액화·수송해 파는 LNG 차익의 "
             "크기를 가늠하는 값이라, 이 차이가 벌어질수록 LNG 수출·운반선 수요 이야기가 강해진다. "
             "조선 탭의 LNG선 수주·신조선가와 같이 보면 맥락이 잡힌다."
         ),
         note="액화·수송·재기화 비용을 빼지 않은 단순 차이다. 실제 차익은 이보다 작다.")

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
