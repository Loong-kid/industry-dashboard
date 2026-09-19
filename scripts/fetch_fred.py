# -*- coding: utf-8 -*-
"""FRED 매크로 지표 → data/macro/*.json (일반 시계열 카드).

수집: FRED JSON API(api.stlouisfed.org). 키는 env FRED_API_KEY(로컬)/GitHub Secret(CI).
units=pc1 로 전년동기비 서버계산. 관련 시리즈를 한 카드(다중)로 묶어 기존 카드/차트 재사용.

    FRED_API_KEY=... python scripts/fetch_fred.py
"""
import json
import os
import time
from datetime import date
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "macro"
API_URL = "https://api.stlouisfed.org/fred/series/observations"
API_KEY = os.environ.get("FRED_API_KEY", "").strip()
START = os.environ.get("FRED_START", "2010-01-01")  # 전체 이력

# 카드별: id, 이름, 단위, 빈도, [(시리즈명, FRED_id, 변환)], 기본표시 시리즈
# 변환: "pc1"=전년동기비%, "lin"=원값
CARDS = [
    {
        "id": "inflation_yoy", "name": "물가 (전년동월비)", "unit": "%", "freq": "monthly",
        "series": [
            ("CPI", "CPIAUCSL", "pc1"),
            ("근원 CPI", "CPILFESL", "pc1"),
            ("PCE", "PCEPI", "pc1"),
            ("근원 PCE", "PCEPILFE", "pc1"),
            ("PPI(최종수요)", "PPIFIS", "pc1"),
        ],
        "default": ["CPI", "근원 PCE"],
    },
    {
        # 일간 BEI 카드. TIPS 시장이 2003년에 생겨 그 이전은 존재하지 않는다(START 2010이 아니라 시리즈 시작).
        "id": "inflation_exp", "name": "기대 인플레이션 (시장·BEI)", "unit": "%", "freq": "daily",
        "start": "1900-01-01",
        "series": [
            ("5년 BEI", "T5YIE", "lin"),
            ("10년 BEI", "T10YIE", "lin"),
            ("5년후 5년", "T5YIFR", "lin"),
        ],
        "default": ["5년 BEI", "10년 BEI"],
        "description": (
            "BEI(손익분기 인플레이션) = 같은 만기의 일반 국채 금리 − 물가연동채(TIPS) 금리. 시장이 값을 매긴 "
            "기대 인플레이션이다. '5년후 5년'은 향후 5년이 아니라 5년 뒤부터 5년간의 기대치로, 단기 유가 충격을 "
            "걷어낸 장기 기대를 본다. TIPS 시장이 생긴 2003년부터만 존재한다 — 그 이전은 아래 장기 카드 참고."
        ),
    },
    {
        # 1978년까지 올라가는 장기 카드. 일간 BEI와 한 카드에 섞으면 x축이 칸 번호 기준이라
        # 월간만 있는 25년 구간이 화면 5%로 눌려 왜곡된다 → 월간끼리 묶어 간격을 고르게 유지한다.
        "id": "inflation_exp_long", "name": "기대 인플레이션 (장기 · 월간)", "unit": "%", "freq": "monthly",
        "start": "1900-01-01", "monthly": True,
        "series": [
            ("미시간대 1년(설문)", "MICH", "lin"),
            ("클리블랜드 1년(모형)", "EXPINF1YR", "lin"),
            ("클리블랜드 10년(모형)", "EXPINF10YR", "lin"),
            ("5년 BEI(월평균)", "T5YIE", "lin"),
            ("10년 BEI(월평균)", "T10YIE", "lin"),
        ],
        "default": ["미시간대 1년(설문)", "클리블랜드 10년(모형)"],
        "description": (
            "BEI 이전 시대까지 보기 위한 월간 카드. 미시간대는 가계 설문(1978~), 클리블랜드 연은은 국채·스왑·"
            "설문을 결합한 모형 추정치(1982~)이며, BEI는 같은 축에 놓으려고 월평균으로 환산했다(2003~). "
            "70~80년대 고인플레와 그 이후 기대가 가라앉는 과정을 한 화면에서 볼 수 있다."
        ),
        "note": (
            "설문 기대는 시장·모형 기대보다 꾸준히 높게 나온다(가계가 체감물가를 반영) — 수준 자체보다 방향과 "
            "변화폭을 비교하는 게 낫다. 일간 움직임은 위 BEI 카드에서 본다. 기간 버튼 '전체' 기준."
        ),
    },
    {
        "id": "rates_curve", "name": "미 국채 금리 · 커브", "unit": "%", "freq": "daily",
        "series": [
            ("연방기금(실효)", "DFF", "lin"),
            ("국채 2년", "DGS2", "lin"),
            ("국채 10년", "DGS10", "lin"),
            ("국채 30년", "DGS30", "lin"),
            ("장단기차(10Y-2Y)", "T10Y2Y", "lin"),
        ],
        "default": ["국채 10년", "국채 30년"],
    },
]


def fetch_series(session, fred_id, transform, start=None, monthly=False):
    last_err = None
    for _ in range(5):
        try:
            params = {
                "series_id": fred_id, "api_key": API_KEY, "file_type": "json",
                "observation_start": start or START, "units": transform or "lin",
            }
            if monthly:
                # 일간 시리즈를 월평균으로 서버에서 집계(월간 시리즈엔 영향 없음)
                params.update({"frequency": "m", "aggregation_method": "avg"})
            r = session.get(API_URL, params=params, timeout=(5, 30))
            r.raise_for_status()
            pts = []
            for o in r.json().get("observations", []):
                v = (o.get("value") or "").strip()
                if v and v != ".":
                    try:
                        pts.append([o["date"], round(float(v), 3)])
                    except ValueError:
                        pass
            return pts
        except Exception as e:  # noqa
            last_err = e
            time.sleep(1.2)
    raise RuntimeError(f"{fred_id} 실패: {last_err}")


def run():
    if not API_KEY:
        raise SystemExit("FRED_API_KEY 미설정: env(로컬) 또는 GitHub Secret(CI)로 주입하세요.")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0"
    today = date.today().isoformat()

    for card in CARDS:
        series = {}
        last_dt = ""
        for name, fid, tr in card["series"]:
            pts = fetch_series(session, fid, tr, card.get("start"), card.get("monthly", False))
            series[name] = pts
            if pts:
                last_dt = max(last_dt, pts[-1][0])
            time.sleep(0.15)
        doc = {
            "id": card["id"],
            "name": card["name"],
            "unit": card["unit"],
            "frequency": card["freq"],
            "source": "FRED (세인트루이스 연은)",
            "source_url": "https://fred.stlouisfed.org/",
            "updated": last_dt or today,
            "fetched": today,
            "default_series": card["default"],
            "series": series,
        }
        for k in ("description", "note"):
            if card.get(k):
                doc[k] = card[k]
        out = OUT_DIR / f"{card['id']}.json"
        # 일간 시계열이 커서 compact(무들여쓰기)로 저장
        out.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        n = sum(len(v) for v in series.values())
        print(f"  {card['id']}: {len(series)}시리즈 {n:,}점 (~{last_dt}) → {out.relative_to(ROOT)}")


if __name__ == "__main__":
    run()
