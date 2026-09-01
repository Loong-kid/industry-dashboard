# -*- coding: utf-8 -*-
"""관세청 수출입무역통계 → data/semicon/*.json (반도체 소부장 품목).

수집: 공공데이터포털 관세청 품목별 국가별 수출입실적(GW).
키는 env CUSTOMS_API_KEY(로컬)/GitHub Secret(CI). **Decoding 키**를 넣어야 한다
(params= 로 넘기면 requests가 인코딩하므로 Encoding 키를 쓰면 이중 인코딩 → 미등록키 에러).

    CUSTOMS_API_KEY=... python scripts/fetch_customs.py

API 함정(실측):
  - cntyCd는 명세상 필수지만 생략하면 전 세계 국가별로 한 번에 반환된다(국가 루프 불필요).
  - 조회구간은 1년 이내만 허용(초과 시 resultCode 99) → 연도 단위 루프.
  - 응답 첫 행이 year="총계", hsCd="-" 인 집계 행이라 거르지 않으면 수치가 2배가 된다.
  - year 형식은 "2025.01"(점 구분), 금액은 US$ 1달러 단위, 중량은 kg.
"""
import json
import os
import time
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "semicon"
API_URL = "https://apis.data.go.kr/1220000/nitemtrade/getNitemtradeList"
API_KEY = os.environ.get("CUSTOMS_API_KEY", "").strip()
SOURCE = "관세청 수출입무역통계 (공공데이터포털)"
SOURCE_URL = "https://www.data.go.kr/data/15100475/openapi.do"

# start: 해당 HSK 10단위가 실제로 데이터를 갖는 첫 해.
# 8486902030 / 3701304000 은 2022년 관세율표 개정으로 신설되어 2021년 이전 자료가 없다.
ITEMS = [
    {"key": "blank_semi", "hs": "3701991000",
     "name": "블랭크마스크 (반도체용)", "short": "반도체 블랭크", "start": 2000},
    {"key": "blank_disp", "hs": "3701304000",
     "name": "블랭크마스크 (디스플레이용)", "short": "디스플레이 블랭크", "start": 2022},
    {"key": "esc", "hs": "8486902030",
     "name": "정전척 ESC", "short": "정전척(ESC)", "start": 2022},
]

TOP_ORIGINS = 6   # 국가별 카드에 표시할 상위 수입국 수
USD_M = 1_000_000.0


def fetch_year(session, hs, year):
    """한 해치를 [(month, country, impDlr, expDlr, impWgt, expWgt)] 로 반환."""
    last_err = None
    for _ in range(5):
        try:
            r = session.get(API_URL, params={
                "serviceKey": API_KEY, "strtYymm": f"{year}01",
                "endYymm": f"{year}12", "hsSgn": hs,
            }, timeout=(5, 60))
            r.raise_for_status()
            root = ET.fromstring(r.text)
            code = root.findtext(".//resultCode")
            if code != "00":
                raise RuntimeError(f"resultCode={code} {root.findtext('.//resultMsg')}")
            rows = []
            for it in root.findall(".//item"):
                hs_cd = it.findtext("hsCd") or ""
                if hs_cd in ("", "-"):
                    continue  # 총계 행
                ym = (it.findtext("year") or "").replace(".", "-")
                if len(ym) != 7:
                    continue
                rows.append((
                    f"{ym}-01",
                    it.findtext("statCdCntnKor1") or "기타",
                    int(it.findtext("impDlr") or 0),
                    int(it.findtext("expDlr") or 0),
                    int(it.findtext("impWgt") or 0),
                    int(it.findtext("expWgt") or 0),
                ))
            return rows
        except Exception as e:  # noqa
            last_err = e
            time.sleep(1.2)
    raise RuntimeError(f"{hs} {year} 실패: {last_err}")


def collect(session, item):
    """품목 1개의 전 기간 원자료 수집."""
    rows = []
    this_year = date.today().year
    for y in range(item["start"], this_year + 1):
        got = fetch_year(session, item["hs"], y)
        rows.extend(got)
        time.sleep(0.15)
    return rows


def monthly_totals(rows):
    """월별 합계 {month: [imp, exp, impWgt, expWgt]} (국가 합산)."""
    agg = {}
    for m, _c, imp, exp, iw, ew in rows:
        a = agg.setdefault(m, [0, 0, 0, 0])
        a[0] += imp; a[1] += exp; a[2] += iw; a[3] += ew
    return dict(sorted(agg.items()))


def rolling12(months, values):
    """12개월 이동합계. 앞 11개월은 버린다."""
    out = []
    for i in range(11, len(months)):
        out.append([months[i], sum(values[i - 11:i + 1])])
    return out


def doc(ind_id, name, unit, series, default, updated, note=None):
    d = {
        "id": ind_id, "name": name, "unit": unit, "frequency": "monthly",
        "source": SOURCE, "source_url": SOURCE_URL,
        "updated": updated, "fetched": date.today().isoformat(),
        "default_series": default, "series": series,
    }
    if note:
        d["note"] = note
    return d


def write(ind_id, payload):
    out = OUT_DIR / f"{ind_id}.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                   encoding="utf-8")
    n = sum(len(v) for v in payload["series"].values())
    print(f"  {ind_id}: {len(payload['series'])}시리즈 {n:,}점 (~{payload['updated']})")


def run():
    if not API_KEY:
        raise SystemExit("CUSTOMS_API_KEY 미설정: env(로컬) 또는 GitHub Secret(CI)로 주입하세요.")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0"

    overview_imp, overview_price = {}, {}
    last_all = ""

    for item in ITEMS:
        rows = collect(session, item)
        if not rows:
            print(f"  {item['key']}: 데이터 없음 — 건너뜀")
            continue
        tot = monthly_totals(rows)
        months = list(tot.keys())
        last = months[-1]
        last_all = max(last_all, last)

        # 1) 월별 수출입 (백만$)
        imp = [[m, round(tot[m][0] / USD_M, 3)] for m in months]
        exp = [[m, round(tot[m][1] / USD_M, 3)] for m in months]
        bal = [[m, round((tot[m][1] - tot[m][0]) / USD_M, 3)] for m in months]
        write(f"{item['key']}_trade", doc(
            f"{item['key']}_trade", f"{item['name']} 수출입", "백만$",
            {"수입": imp, "수출": exp, "무역수지": bal}, ["수입", "수출"], last,
            note=f"HS {item['hs']}",
        ))

        # 2) 수입국별 (12개월 이동합계, 상위 N개국)
        by_c = {}
        for m, c, i_, _e, _iw, _ew in rows:
            by_c.setdefault(c, {}).setdefault(m, 0)
            by_c[c][m] += i_
        # 최근 12개월 수입액 기준 순위. 과거엔 컸어도 지금 0인 나라는 뺀다(평평한 0선 방지).
        recent = months[-12:]
        scored = [(c, sum(mm.get(m, 0) for m in recent)) for c, mm in by_c.items()]
        ranked = [c for c, v in sorted(scored, key=lambda kv: -kv[1]) if v > 0][:TOP_ORIGINS]
        origin = {}
        for c in ranked:
            vals = [by_c[c].get(m, 0) for m in months]
            pts = rolling12(months, vals)
            origin[c] = [[m, round(v / USD_M, 3)] for m, v in pts]
        if origin:
            write(f"{item['key']}_origin", doc(
                f"{item['key']}_origin", f"{item['name']} 수입국별 (12개월 누계)", "백만$",
                origin, ranked[:3], last,
                note=f"HS {item['hs']} · 최근 12개월 수입액 상위 {len(origin)}개국",
            ))

        # 3) 종합 카드용 시리즈
        imp_raw = [tot[m][0] for m in months]
        wgt_raw = [tot[m][2] for m in months]
        overview_imp[item["short"]] = [
            [m, round(v / USD_M, 3)] for m, v in rolling12(months, imp_raw)
        ]
        price = []
        for i in range(11, len(months)):
            amt = sum(imp_raw[i - 11:i + 1])
            kg = sum(wgt_raw[i - 11:i + 1])
            if kg > 0:
                price.append([months[i], round(amt / kg, 1)])
        if price:
            overview_price[item["short"]] = price

    if overview_imp:
        names = list(overview_imp.keys())
        write("semicon_import_ttm", doc(
            "semicon_import_ttm", "품목별 수입 (12개월 누계)", "백만$",
            overview_imp, names, last_all,
        ))
    if overview_price:
        names = list(overview_price.keys())
        write("semicon_unit_price", doc(
            "semicon_unit_price", "수입 단가 (12개월 누계 기준)", "$/kg",
            overview_price, names, last_all,
            note="수입금액 ÷ 수입중량. 제품 믹스 변화를 반영한다.",
        ))


if __name__ == "__main__":
    run()
