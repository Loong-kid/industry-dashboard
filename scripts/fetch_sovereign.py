# -*- coding: utf-8 -*-
"""국가별 정부부채·GDP·재정수지·10년 국채금리 → 매크로 탭 '국가별 부채·금리' 서브탭.

소스(전부 무료):
  - IMF World Economic Outlook — DataMapper API(키 없음, 연간, 전망 포함)
      GGXWDG_NGDP 일반정부 총부채/GDP(%) · NGDPD GDP(십억 달러) · GGXCNL_NGDP 재정수지/GDP(%)
      **User-Agent를 브라우저처럼 보내면 403(Akamai)** — 연락처를 적은 일반 UA로 보내야 열린다.
  - BIS 정부 신용/GDP(%) — FRED `Q{국가2}GAN770A`(분기, 한국은 없음)
  - OECD 장기(10년) 국채금리 — FRED `IRLTLT01{국가2}M156N`(월간, OECD 회원국+남아공)
  - 중국 10년 국채 — ChinaMoney(중국외환거래센터) 수익률곡선. **날짜 지정이 안 돼 최신값만 준다** →
    매일 받아 data/_macro/cn_10y.json에 쌓는다(과거 이력은 쌓인 만큼만).
인도·인도네시아·브라질·터키·아르헨티나 금리는 무료 공식 소스가 없어 뺐다(IMF MFS에도 국채금리 없음).

    FRED_API_KEY=... python scripts/fetch_sovereign.py
"""
import datetime as dt
import json
import os
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "macro"
CN_CACHE = ROOT / "data" / "_macro" / "cn_10y.json"
FRED_KEY = os.environ.get("FRED_API_KEY", "").strip()
UA = {"User-Agent": "industry-dashboard (personal research) wkorotk@gmail.com", "Accept": "application/json"}
TODAY = dt.date.today()
PROJ_FROM = TODAY.year  # IMF WEO는 대략 작년까지 실적(추정 포함), 올해부터 전망

# (ISO3, ISO2, 한글명) — 기본 12개국 + 신흥국 5 + 선진국 4
COUNTRIES = [
    ("USA", "US", "미국"), ("JPN", "JP", "일본"), ("DEU", "DE", "독일"), ("FRA", "FR", "프랑스"),
    ("ITA", "IT", "이탈리아"), ("ESP", "ES", "스페인"), ("GBR", "GB", "영국"), ("GRC", "GR", "그리스"),
    ("NLD", "NL", "네덜란드"), ("CHE", "CH", "스위스"), ("CAN", "CA", "캐나다"), ("AUS", "AU", "호주"),
    ("KOR", "KR", "한국"), ("CHN", "CN", "중국"), ("IND", "IN", "인도"), ("IDN", "ID", "인도네시아"),
    ("BRA", "BR", "브라질"), ("MEX", "MX", "멕시코"), ("ZAF", "ZA", "남아공"), ("ARG", "AR", "아르헨티나"),
    ("TUR", "TR", "터키"),
]
NAME = {c[0]: c[2] for c in COUNTRIES}
IMF_SRC = "IMF World Economic Outlook (DataMapper)"
IMF_URL = "https://www.imf.org/external/datamapper/"


def get_json(url, headers=UA, tries=3):
    for i in range(tries):
        try:
            return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60).read())
        except Exception:  # noqa
            time.sleep(1.5 * (i + 1))
    return None


def imf(indicator):
    """IMF DataMapper — 한 번에 전 국가가 온다. {ISO3: {연도: 값}}."""
    d = get_json(f"https://www.imf.org/external/datamapper/api/v1/{indicator}")
    vals = (d or {}).get("values", {}).get(indicator, {})
    return {c: {int(y): float(v) for y, v in vals.get(c, {}).items() if v is not None} for c, _, _ in COUNTRIES}


def fred(series_id):
    d = get_json("https://api.stlouisfed.org/fred/series/observations?"
                 f"series_id={series_id}&api_key={FRED_KEY}&file_type=json&observation_start=1990-01-01")
    out = []
    for o in (d or {}).get("observations", []):
        if o.get("value") not in (None, "", "."):
            out.append([o["date"], round(float(o["value"]), 2)])
    return out


def china_10y():
    """ChinaMoney 중국 국채 수익률곡선 최신일 10년물 → 캐시에 하루씩 쌓는다."""
    cache = json.loads(CN_CACHE.read_text(encoding="utf-8")) if CN_CACHE.exists() else {}
    d = get_json("https://www.chinamoney.com.cn/ags/ms/cm-u-bk-currency/ClsYldCurvHis?lang=EN&reference=1"
                 "&bondType=CYCC000&termId=10&pageNum=1&pageSize=20", headers={"User-Agent": "Mozilla/5.0"})
    try:
        date = d["data"]["dateList"][0]
        ten = next(r for r in d["records"] if r["yearTermStr"] in ("10.0", "10"))
        cache[date] = round(float(ten["maturityYieldStr"]), 3)
    except Exception:  # noqa — 접속 실패해도 쌓인 값은 그대로 쓴다
        print("  중국 10년: 이번 실행에서 못 받음(캐시 유지)")
    CN_CACHE.parent.mkdir(parents=True, exist_ok=True)
    CN_CACHE.write_text(json.dumps(dict(sorted(cache.items())), indent=1), encoding="utf-8")
    return [[k, v] for k, v in sorted(cache.items())]


def save(cid, doc):
    doc.setdefault("fetched", TODAY.isoformat())
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{cid}.json").write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":"), allow_nan=False),
                                     encoding="utf-8")


def yearly(d, scale=1.0, nd=1, to=None):
    return [[f"{y}-01-01", round(v * scale, nd)] for y, v in sorted(d.items()) if y >= 1990 and (to is None or y <= to)]


def run():
    if not FRED_KEY:
        raise SystemExit("FRED_API_KEY 미설정")
    debt, gdp, bal = imf("GGXWDG_NGDP"), imf("NGDPD"), imf("GGXCNL_NGDP")
    last_imf = max((y for c in debt.values() for y in c), default=TODAY.year)
    common_y = {"frequency": "yearly", "full_range": True, "source": IMF_SRC, "source_url": IMF_URL,
                "updated": f"{PROJ_FROM - 1}-12-31", "year_labels": True,
                "forecast_from": f"{PROJ_FROM}-01-01", "forecast_label": "IMF 전망"}
    proj_note = (f"{PROJ_FROM}년 이후(~{last_imf})는 IMF 전망치로 점선 표시한다. "
                 "이전 구간은 실적·추정이며 추정치가 포함될 수 있다.")

    # ① IMF 부채/GDP (실적+전망)
    save("sov_debt_imf", {
        **common_y, "id": "sov_debt_imf", "name": "정부부채/GDP — IMF (전망 포함)", "unit": "%",
        "default_series": ["미국", "일본", "이탈리아", "프랑스", "중국", "한국"],
        "series": {NAME[c]: yearly(v) for c, v in debt.items() if v},
        "description": (
            "일반정부(중앙+지방+사회보장기금) 총부채를 GDP로 나눈 비율. 국가 간 비교의 표준 지표다. IMF가 반기마다 "
            "내는 세계경제전망(WEO) 값이라 향후 5~6년 전망까지 한 선으로 이어 볼 수 있다. 일본은 250%대, 미국·"
            "이탈리아·프랑스는 100%를 넘고, 중국은 빠르게 오르는 중이다."
        ),
        "note": proj_note + " 총부채(gross) 기준이라 정부가 가진 금융자산을 빼지 않았다(순부채와 다르다).",
    })

    # ② 부채 규모(조 달러) = 부채비율 × GDP
    usd = {}
    for c, v in debt.items():
        pts = {y: v[y] / 100 * gdp[c][y] / 1000 for y in v if y in gdp.get(c, {})}
        if pts:
            usd[NAME[c]] = yearly(pts, nd=2)
    save("sov_debt_usd", {
        **common_y, "id": "sov_debt_usd", "name": "정부부채 규모 (조 달러)", "unit": "$tn",
        "default_series": ["미국", "중국", "일본", "이탈리아", "프랑스", "영국"],
        "series": usd,
        "description": (
            "부채비율 × 달러 GDP로 계산한 정부부채의 절대 규모. 비율로는 작아 보여도 경제가 큰 나라(중국)는 금액으로 "
            "크게 잡히고, 엔화·유로 약세는 달러 환산 규모를 줄여 보이게 한다."
        ),
        "note": proj_note + " 달러 환산이라 환율 변동이 섞인다.",
    })

    # ③ GDP
    save("sov_gdp", {
        **common_y, "id": "sov_gdp", "name": "GDP (조 달러)", "unit": "$tn",
        "default_series": ["미국", "중국", "독일", "일본", "인도", "한국"],
        "series": {NAME[c]: yearly(v, scale=1 / 1000, nd=2) for c, v in gdp.items() if v},
        "description": "명목 GDP(시장환율 달러 환산). 부채비율의 분모다.",
        "note": proj_note,
    })

    # ④ 재정수지/GDP
    save("sov_deficit", {
        **common_y, "id": "sov_deficit", "name": "재정수지/GDP (적자는 음수)", "unit": "%",
        "default_series": ["미국", "프랑스", "중국", "영국", "이탈리아", "일본"],
        "series": {NAME[c]: yearly(v) for c, v in bal.items() if v},
        "description": (
            "한 해 정부 수입 − 지출을 GDP로 나눈 것(IMF 'net lending/borrowing'). 적자(음수)가 클수록 부채비율이 "
            "빨리 오른다 — 부채 '수준'보다 증가 '속도'를 보는 지표다."
        ),
        "note": proj_note,
    })

    # ⑤ BIS 분기 정부부채/GDP
    bis = {}
    for c3, c2, nm in COUNTRIES:
        pts = fred(f"Q{c2}GAN770A")
        if pts:
            bis[nm] = pts
        time.sleep(0.1)
    last_q = max(p[-1][0] for p in bis.values())
    save("sov_debt_q", {
        "id": "sov_debt_q", "name": "정부부채/GDP — 분기 (BIS)", "unit": "%", "frequency": "quarterly",
        "source": "BIS 정부 신용 통계 (FRED 경유)", "source_url": "https://data.bis.org/topics/TOTAL_CREDIT",
        "updated": last_q,
        "default_series": ["미국", "일본", "프랑스", "이탈리아", "중국", "영국"],
        "series": bis,
        "description": (
            "국제결제은행(BIS)이 분기마다 집계하는 일반정부 부채(명목가)/GDP. IMF 연간보다 빨리, 분기 단위로 움직임을 "
            "잡는다. 정의가 IMF와 조금 달라 수준은 몇 %p 차이 날 수 있다."
        ),
        "note": f"최신 {last_q[:7]} 분기. 한국은 BIS 정부부채 시리즈가 없어 IMF 카드에서 본다.",
    })

    # ⑥ 10년 국채금리
    ylds = {}
    for c3, c2, nm in COUNTRIES:
        pts = fred(f"IRLTLT01{c2}M156N")
        if pts:
            ylds[nm] = pts
        time.sleep(0.1)
    cn = china_10y()
    if cn:
        ylds["중국"] = cn
    save("sov_yield_10y", {
        "id": "sov_yield_10y", "name": "10년 국채금리", "unit": "%", "frequency": "monthly",
        "source": "OECD 장기금리(FRED) · ChinaMoney(중국)", "source_url": "https://fred.stlouisfed.org/",
        "updated": max(p[-1][0] for p in ylds.values()),
        "default_series": ["미국", "독일", "프랑스", "이탈리아", "일본", "중국"],
        "series": ylds,
        "description": (
            "각국 10년 국채 금리(월평균). 부채가 많아도 금리가 낮으면 이자 부담이 버틸 만하고, 부채비율과 금리가 "
            "함께 오르면 위험 신호다. 프랑스·이탈리아와 독일의 금리 차이는 유로존 재정 불안의 온도계다."
        ),
        "note": ("OECD 월평균은 한두 달 늦다. 중국은 일별 최신값을 매일 쌓아 가는 중이라 이력이 짧다(공개 이력 API 없음). "
                 "인도·인도네시아·브라질·터키·아르헨티나는 무료 공식 소스가 없어 뺐다."),
    })

    # ⑦ 요약 표
    def at(d, y):
        return round(d[y], 1) if y in d else None
    y0 = PROJ_FROM - 1
    rows = []
    for c3, c2, nm in COUNTRIES:
        dd, gg, bb = debt.get(c3, {}), gdp.get(c3, {}), bal.get(c3, {})
        yl = ylds.get(nm, [])
        bq = bis.get(nm, [])
        rows.append({
            "country": nm,
            "gdp": round(gg[y0] / 1000, 2) if y0 in gg else None,
            "debt": at(dd, y0),
            "chg19": round(dd[y0] - dd[2019], 1) if y0 in dd and 2019 in dd else None,
            "debt_proj": at(dd, last_imf),
            "debt_usd": round(dd[y0] / 100 * gg[y0] / 1000, 2) if y0 in dd and y0 in gg else None,
            "bal": at(bb, y0),
            "bis": bq[-1][1] if bq else None,
            "yld": yl[-1][1] if yl else None,
            "yld_at": yl[-1][0][:7] if yl else "",
        })
    rows.sort(key=lambda r: -(r["debt"] or 0))
    save("sov_table", {
        "id": "sov_table", "name": f"국가별 부채·금리 요약 ({y0}년 기준)",
        "source": "IMF WEO · BIS · OECD · ChinaMoney", "source_url": IMF_URL, "updated": f"{y0}-12-31",
        "note": (f"부채/GDP·GDP·재정수지는 IMF {y0}년(최근 실적·추정), '2019 대비'는 코로나 직전 대비 증감(2020년 일시 급등은 기준에서 뺌), "
                 f"'IMF {last_imf}'은 전망. BIS는 최신 분기 값. 금리는 가장 최근 월(중국은 일). 부채비율 순 정렬."),
        "cols": [
            {"key": "country", "label": "국가"},
            {"key": "debt", "label": "부채/GDP(%)", "align": "right", "fmt": "num"},
            {"key": "chg19", "label": "2019 대비(%p)", "align": "right", "fmt": "num"},
            {"key": "debt_proj", "label": f"IMF {last_imf} 전망(%)", "align": "right", "fmt": "num"},
            {"key": "bis", "label": "BIS 최신(%)", "align": "right", "fmt": "num"},
            {"key": "debt_usd", "label": "부채($tn)", "align": "right", "fmt": "num"},
            {"key": "gdp", "label": "GDP($tn)", "align": "right", "fmt": "num"},
            {"key": "bal", "label": "재정수지(%)", "align": "right", "fmt": "num"},
            {"key": "yld", "label": "10년 금리(%)", "align": "right", "fmt": "num"},
            {"key": "yld_at", "label": "금리 기준"},
        ],
        "rows": rows,
    })
    print(f"  IMF {len([v for v in debt.values() if v])}개국(~{last_imf}) · BIS {len(bis)}개국(~{last_q[:7]}) · "
          f"금리 {len(ylds)}개국 · 중국 금리 {len(cn)}일 쌓임")


if __name__ == "__main__":
    run()
