# -*- coding: utf-8 -*-
"""운임 선물 ETF 가격 → data/shipping/etf_*.json (일반 시계열 카드).

BWET(탱커 운임 선물)·BDRY(건화물 운임 선물). Yahoo Finance 일봉(키 없음).
두 ETF 모두 분배·분할 이벤트가 없어 close == adjclose (2026-09-14 확인) → close 사용.

구성·비중 설명은 운용사(Amplify) 공시 보유내역 기준이며 자동 갱신되지 않는다.
비중은 연 1회 리밸런싱이라 드물게 바뀌지만, 바뀌면 아래 DESCRIPTION을 손으로 고칠 것.

    python scripts/fetch_freight_etf.py
"""
import datetime as dt
import json
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_commodities import fetch_yahoo  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "shipping"  # 탭 id=shipping

ETFS = [
    {
        "id": "etf_bwet",
        "ticker": "BWET",
        "name": "BWET 탱커 운임 선물 ETF",
        "source_url": "https://amplifyetfs.com/bwet/",
        "description": (
            "Breakwave Tanker Shipping ETF(Amplify, 2023-05 상장). Breakwave Tanker Futures Index를 따라 "
            "원유 탱커 운임 선물을 담는다: TD3C(27만t VLCC, 중동 걸프→중국) 90% + TD20(13만t 수에즈막스, "
            "서아프리카→유럽) 10%, 연 1회 리밸런싱. 당월~3개월 뒤 4개 월물에 나눠 담고 매달 가까운 월물을 "
            "먼 월물로 굴린다(가중평균 만기 60~90일). 운임 선물은 해당 월 Baltic 일일 운임의 월평균으로 "
            "정산되므로, 가격은 '향후 1~3개월 VLCC 중동→중국 운임 기대치'에 가깝다."
        ),
        "note": (
            "현물 운임이 아니다. 롤오버 손익과 연 3.5% 보수(2026-12-31까지 일부 면제)가 쌓여 장기 차트는 "
            "실제 운임과 모양이 다르다 — 비교는 '탱커 운임' 카드의 VLCC 줄과. 운용자산 수천만$의 소형 펀드라 "
            "괴리·상장폐지 위험이 있다. 구성 기준일 2026-09-14(TD3C 85.7% · TD20 9.7% · 현금)."
        ),
    },
    {
        "id": "etf_bdry",
        "ticker": "BDRY",
        "name": "BDRY 건화물 운임 선물 ETF",
        "source_url": "https://amplifyetfs.com/bdry/",
        "description": (
            "Breakwave Dry Bulk Shipping ETF(Amplify, 2018-03 상장). Breakwave Dry Freight Futures Index를 "
            "따라 건화물선 용선료 선물(FFA)을 담는다: 케이프사이즈 5TC(18만t, 철광석) 50% + 파나막스 5TC"
            "(8.2만t, 석탄·곡물) 40% + 수프라막스 58TC(5.8만t, 자체 크레인 소형선) 10%, 연 1회 리밸런싱. "
            "당월~3개월 뒤 월물에 나눠 담는다(가중평균 만기 60~70일). 5TC 등은 여러 항로 일일 용선료의 "
            "가중평균이라 가격은 '향후 1~3개월 벌커 용선료 기대치'에 가깝다."
        ),
        "note": (
            "현물 운임이 아니다. 롤오버 손익과 연 3.5% 보수(2026-12-31까지 일부 면제)가 누적된다 — 비교는 "
            "'건화물 운임'의 BDI·벌커 운임 카드와. 운용자산 약 3,800만$(2026-09-11). "
            "구성 기준일 2026-09-14."
        ),
    },
]


def run():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0"
    today = dt.date.today().isoformat()

    for e in ETFS:
        series = fetch_yahoo(session, e["ticker"])
        doc = {
            "id": e["id"], "name": e["name"], "unit": "$/주", "frequency": "daily",
            "source": f"Yahoo Finance ({e['ticker']})", "source_url": e["source_url"],
            "description": e["description"], "note": e["note"],
            "updated": series[-1][0] if series else today, "fetched": today,
            "series": {e["ticker"]: series},
        }
        (OUT_DIR / f"{e['id']}.json").write_text(
            json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"  {e['id']}: {len(series)}점 (~{doc['updated']})")


if __name__ == "__main__":
    run()
