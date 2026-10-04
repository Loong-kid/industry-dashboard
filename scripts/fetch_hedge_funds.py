"""Public hedge-fund statistics, licensed strategy indices and SEC adviser RAUM.

Sources are independent cohorts: a bad response preserves that cohort. Adviser
observations are filing dates, never inferred valuation dates or year-end AUM.
"""
import calendar
import argparse
import csv
import hashlib
import io
import json
import math
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import fitz
import requests

from fetch_liquidity import get

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/institution"
PIVOTAL = "https://github.com/pivotalpath/publicdata"
OFR = "https://www.financialresearch.gov/hedge-fund-monitor/datasets/fpf/"
ADV = "https://adviserinfo.sec.gov/adv"
MANAGERS = [
    ("bridgewater", "Bridgewater Associates", "BRIDGEWATER ASSOCIATES, LP", 105129, "글로벌 매크로"),
    ("citadel", "Citadel Advisors", "CITADEL ADVISORS LLC", 148826, "멀티전략"),
    ("point72", "Point72 Asset Management", "POINT72 ASSET MANAGEMENT, L.P.", 283077, "멀티전략"),
    ("two_sigma", "Two Sigma Investments", "TWO SIGMA INVESTMENTS, LP", 137137, "시스템 / 퀀트"),
    ("de_shaw", "D. E. Shaw & Co.", "D. E. SHAW & CO., L.P.", 108679, "멀티전략 / 퀀트"),
    ("pershing", "Pershing Square Capital Management", "PERSHING SQUARE CAPITAL MANAGEMENT, L.P.", 132982, "집중 주식 / 기업 관여"),
]
INDEX_NAMES = {
    "iHFC": "종합 / 자산가중", "iCRD": "크레딧", "iEQD": "분산 주식 롱숏",
    "iQNT": "주식 퀀트", "iEQS": "섹터 주식", "iEVD": "이벤트 드리븐",
    "iGBM": "글로벌 매크로", "iMFT": "CTA / 매니지드 퓨처스",
    "iMST": "멀티전략", "iVOL": "변동성",
}
STRATEGIES = {"CREDIT": "크레딧", "EQUITY": "주식", "MACRO": "매크로",
              "MULTI": "멀티전략", "EVENT": "이벤트", "RV": "상대가치",
              "OTHER": "기타", "FUTURES": "매니지드 퓨처스", "FOF": "펀드 오브 펀드"}
RAUM_NOTE = "Form ADV Item 5.F.(2)(c)의 운용사 신고 규제상 AUM(RAUM)입니다. 부채를 차감하지 않는 계산이며 사모펀드 미납입 약정 등을 포함할 수 있습니다. 투자자 순자산·회사 발표 AUM·13F 보유액과 다르며 운용사 간 합산하지 않습니다."


def number(value, minimum=0):
    if isinstance(value, bool):
        raise ValueError("Boolean amount")
    n = float(value)
    if not math.isfinite(n) or n < minimum:
        raise ValueError("Invalid numeric observation")
    return n


def put(points, day, value, today, minimum=0):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day) or date.fromisoformat(day) > today:
        raise ValueError("Invalid/future date")
    n = number(value, minimum)
    if day in points and points[day] != n:
        raise ValueError("Conflicting duplicate observation")
    points[day] = n


def doc(cid, name, series, today, source, url, frequency, **extra):
    if not series or any(not pts for pts in series.values()):
        raise ValueError("Empty series")
    return {"id": cid, "name": name, "unit": "십억 달러", "frequency": frequency,
            "series": series, "updated": max(p[0] for pts in series.values() for p in pts),
            "fetched": today.isoformat(), "source": source, "source_url": url,
            "compact_ticks": True, "span_gaps": False, "strict_range": True, "table_limit": 10000, **extra}


def write_cohort(documents, out=OUT):
    # Validate all histories before replacing any card in this source cohort.
    for cid, new in documents.items():
        old_path = out / (cid + ".json")
        if not old_path.exists():
            continue
        old = json.loads(old_path.read_text(encoding="utf-8"))
        if old.get("updated", "") > new["updated"]:
            raise ValueError("Latest observation regressed: " + cid)
        for name, pts in old.get("series", {}).items():
            if name not in new.get("series", {}):
                raise ValueError("Series disappeared: " + name)
            if {p[0] for p in pts} - {p[0] for p in new["series"][name]}:
                raise ValueError("Historical dates disappeared: " + cid)
    out.mkdir(parents=True, exist_ok=True)
    for cid, value in documents.items():
        path = out / (cid + ".json")
        payload = json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n"
        temp = path.with_suffix(".tmp")
        temp.write_text(payload, encoding="utf-8")
        temp.replace(path)


def parse_ofr(payload, mnemonic, today):
    entry = payload[mnemonic]
    meta = entry["metadata"]
    if meta["mnemonic"] != mnemonic or meta["schedule"]["observation_frequency"] != "Quarterly":
        raise ValueError("OFR series/frequency changed")
    if meta["unit"]["type"] != "Value" or meta["unit"]["name"] != "U.S. dollars" or meta["unit"].get("magnitude") != 0:
        raise ValueError("OFR dollar unit changed")
    points = {}
    for day, value in entry["timeseries"]["aggregation"]:
        dt = date.fromisoformat(day)
        if dt.month not in (3, 6, 9, 12) or dt.day != calendar.monthrange(dt.year, dt.month)[1]:
            raise ValueError("OFR non-quarter-end date")
        # Confidential/masked observations remain null, not zero or interpolated.
        if value is None:
            if dt > today:
                raise ValueError("Future masked date")
            if day in points:
                raise ValueError("Duplicate masked date")
            points[day] = None
        else:
            put(points, day, value, today)
    if len(points) < 20 or not any(v is not None for v in points.values()):
        raise ValueError("Insufficient OFR history")
    return [[day, None if v is None else v / 1e9] for day, v in sorted(points.items())], meta


def collect_ofr(session, today):
    result, metadata = {}, {}
    for suffix in ("NAV", "GAV"):
        names = [("합계", f"FPF-ALLQHF_{suffix}_SUM")] + [(name, f"FPF-STRATEGY_{key}_{suffix}_SUM") for key, name in STRATEGIES.items()]
        for name, mnemonic in names:
            payload = get(session, "https://data.financialresearch.gov/hf/v1/series/full", {"mnemonic": mnemonic}).json()
            pts, meta = parse_ofr(payload, mnemonic, today)
            result[(suffix, name)] = pts
            metadata[mnemonic] = {"name": meta["description"]["name"], "notes": meta["description"]["notes"], "schedule": meta["schedule"]}
    if len({pts[-1][0] for pts in result.values()}) != 1:
        raise ValueError("OFR cohort has mixed latest quarters")
    for name in ["합계", *STRATEGIES.values()]:
        nav, gav = dict(result[("NAV", name)]), dict(result[("GAV", name)])
        if set(nav) != set(gav) or any(nav[d] is not None and gav[d] is not None and nav[d] > gav[d] + .001 for d in nav):
            raise ValueError("OFR NAV/GAV history does not reconcile")
    note = "SEC 보고 운용사가 운용하는 Qualifying Hedge Funds(순자산 5억 달러 이상 등 조건 충족)의 분기 집계입니다. 미국 소재 펀드만의 통계나 전체 헤지펀드 모집단이 아니며 해외 소재 펀드도 포함될 수 있습니다. 전략은 OFR 분류이고 PivotalPath의 성과 표본과 다릅니다. 공시 정정으로 과거 값이 바뀔 수 있고 비공개 값은 빈칸으로 유지합니다."
    common = {"note": note, "methodology_url": OFR, "data_stale_days": 180,
              "series_colors": {"펀드 오브 펀드": "#9c6d33"},
              "basis_details": [{"label": "순자산 / 총자산", "value": "NAV는 총자산에서 부채를 차감한 투자자 지분입니다. GAV는 대차대조표 자산의 시장가치입니다. GAV/NAV는 참고 비율이며 파생상품까지 반영한 총 명목 익스포저 레버리지와 다릅니다."},
                                {"label": "전략 분류", "value": "9개 전략으로 집계합니다. 자산의 75% 이상이 한 전략에 집중되지 않으면 OFR는 멀티전략으로 분류합니다. 펀드의 전략별 신고 비중을 이용한 집계이며 비공개 값은 합산으로 역산하지 않습니다."}]}
    docs = {}
    for cid, title, series in [
        ("hf_assets", "헤지펀드 표본 / 순자산·총자산", {"순자산 / NAV": result[("NAV", "합계")], "총자산 / GAV": result[("GAV", "합계")]}),
        ("hf_strategy_nav", "전략별 순자산 / OFR", {name: result[("NAV", name)] for name in STRATEGIES.values()}),
        ("hf_strategy_gav", "전략별 총자산 / OFR", {name: result[("GAV", name)] for name in STRATEGIES.values()}),
    ]:
        docs[cid] = doc(cid, title, series, today, "미 재무부 OFR · SEC Form PF", OFR, "quarterly", default_series=list(series)[:4], **common)
        ids = ([f"FPF-ALLQHF_{suffix}_SUM" for suffix in ("NAV", "GAV")] if cid == "hf_assets"
               else [f"FPF-STRATEGY_{key}_{'NAV' if cid.endswith('nav') else 'GAV'}_SUM" for key in STRATEGIES])
        docs[cid]["source_series"] = {key: "https://data.financialresearch.gov/hf/v1/series/full?mnemonic=" + key for key in ids}
        docs[cid]["source_updates"] = {key: metadata[key]["schedule"]["last_update"] for key in ids}
    return docs


def parse_pivotal(text, today, as_of):
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames != ["date", "id", "mtd"]:
        raise ValueError("PivotalPath schema changed")
    result = {key: {} for key in INDEX_NAMES}
    for row in reader:
        if row["id"] not in result:
            raise ValueError("Unreviewed index appeared")
        if not re.fullmatch(r"\d{4}-\d{2}", row["date"]) or row["date"] > as_of:
            raise ValueError("Invalid month/vintage")
        year, month = map(int, row["date"].split("-"))
        day = date(year, month, calendar.monthrange(year, month)[1]).isoformat()
        put(result[row["id"]], day, row["mtd"], today, -1)
    for points in result.values():
        days = sorted(points)
        if len(days) < 120 or days[-1][:7] != as_of:
            raise ValueError("Incomplete index history/latest vintage")
        for a, b in zip(days, days[1:]):
            ay, am = map(int, a[:7].split("-")); by, bm = map(int, b[:7].split("-"))
            if by * 12 + bm != ay * 12 + am + 1:
                raise ValueError("Missing monthly return; do not compound across gap")
    return result


def annual_returns(points):
    grouped = {}
    for day, value in sorted(points.items()):
        grouped.setdefault(day[:4], []).append((day, value))
    return [[year + "-12-31", round((math.prod(1 + v for _, v in pts) - 1) * 100, 5)]
            for year, pts in sorted(grouped.items()) if len(pts) == 12]


def cumulative_indices(series):
    # All strategies start at the same month so levels can be compared.
    start = max(min(pts) for pts in series.values())
    baseline = (date.fromisoformat(start).replace(day=1) - timedelta(days=1)).isoformat()
    result = {}
    for key, points in series.items():
        value, pts = 100.0, [[baseline, 100.0]]
        for day, r in sorted(points.items()):
            if day >= start:
                value *= 1 + r
                pts.append([day, round(value, 6)])
        result[INDEX_NAMES[key]] = pts
    return result, baseline


def collect_pivotal(session, today):
    revision = get(session, "https://api.github.com/repos/pivotalpath/publicdata/commits/main", {}).json()["sha"]
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Invalid source revision")
    base = f"https://raw.githubusercontent.com/pivotalpath/publicdata/{revision}/"
    meta = get(session, base + "metadata.json", {}).json()
    if meta.get("license") != "CC BY 4.0":
        raise ValueError("Source license changed")
    catalog = list(csv.DictReader(io.StringIO(get(session, base + "index_catalog.csv", {}).text)))
    by_id = {row["id"]: row for row in catalog}
    if any(key not in by_id for key in INDEX_NAMES):
        raise ValueError("Missing index definitions")
    for key in INDEX_NAMES:
        abstract = by_id[key]["abstract"].lower()
        if "net of" not in abstract:
            raise ValueError("Net return definition changed")
    if "usd" not in by_id["iHFC"]["abstract"].lower():
        raise ValueError("Composite currency definition changed")
    points = parse_pivotal(get(session, base + "index_return.csv", {}).text, today, meta["as_of"])
    common = {"unit": "%", "monthly_axis": True, "source_revision": revision,
              "license": "CC BY 4.0 · Source: PivotalPath", "license_url": "https://creativecommons.org/licenses/by/4.0/", "source_as_of": meta["as_of"],
              "data_stale_days": 100, "change_mode": "percentage_points",
              "series_colors": {INDEX_NAMES["iMST"]: "#9c6d33", INDEX_NAMES["iVOL"]: "#197b90"}}
    common["note"] = "PivotalPath의 글로벌 기관투자용 펀드 표본입니다. 미국 펀드만의 성과나 개별 운용사의 성과가 아닙니다. 보수 차감 후 USD 수익률이며 월별 펀드 보고·연간 구성종목 선정·월간 리밸런싱을 반영합니다. 각 지수의 표본·가중 방식이 다르고 OFR 자산 통계와 표본을 공유하지 않습니다."
    common["basis_details"] = [{"label": "표본 / 가중", "value": "최소 운용 이력 18개월·최소 AUM 5천만 달러 등 기관투자용 표본 기준입니다. 종합·크레딧·분산 주식·섹터 주식·이벤트·매크로·변동성은 원문의 자산가중 지수, CTA·멀티전략은 동일가중 지수입니다. 퀀트는 원문에 가중 방식이 명시되지 않아 단정하지 않습니다. 자발적 보고와 표본 선정에 따른 편향이 있을 수 있습니다."},
                               {"label": "주기 / 수정", "value": "월별 관측값이며 최근 확정 월은 현재보다 보통 1~2개월 늦습니다. 파일의 갱신일과 성과 기준월을 구분하고 과거 정정도 반영합니다."},
                               {"label": "출처 / 이용", "value": "Source: PivotalPath. 월별 보수 차감 후 USD 헤지펀드 지수. CC BY 4.0에 따라 출처를 표시하며 연간 성과와 기준 100 곡선은 월별 수익률에서 계산합니다."}]
    monthly = {INDEX_NAMES[key]: [[d, round(r * 100, 6)] for d, r in sorted(pts.items())] for key, pts in points.items()}
    groups = [
        ("hf_returns_composite", "헤지펀드 종합 / 월별 수익률", ["iHFC"]),
        ("hf_returns_equity", "주식·이벤트 전략 / 월별 수익률", ["iEQD", "iQNT", "iEQS", "iEVD"]),
        ("hf_returns_other", "매크로·크레딧·멀티전략 / 월별 수익률", ["iGBM", "iCRD", "iMFT", "iMST", "iVOL"]),
    ]
    docs = {}
    for cid, name, keys in groups:
        series = {INDEX_NAMES[key]: monthly[INDEX_NAMES[key]] for key in keys}
        docs[cid] = doc(cid, name, series, today, "PivotalPath", PIVOTAL, "monthly", default_series=list(series)[:3], **common)
    annual = {INDEX_NAMES[key]: annual_returns(pts) for key, pts in points.items()}
    docs["hf_returns_annual"] = doc("hf_returns_annual", "헤지펀드 전략 / 연간 수익률", annual, today, "PivotalPath · 월별 수익률에서 계산", PIVOTAL, "yearly", **{**common, "monthly_axis": False, "change_mode": "none", "data_stale_days": 550},
                                    default_series=[INDEX_NAMES[k] for k in ("iHFC", "iGBM", "iMST")],
                                    description="1~12월 자료가 모두 있는 해만 복리 계산합니다. 진행 중인 해와 미공표 월은 연간 수익률로 표시하지 않습니다.")
    cumulative, baseline = cumulative_indices(points)
    docs["hf_growth"] = doc("hf_growth", "헤지펀드 전략 / 누적 성과", cumulative, today, "PivotalPath · 월별 수익률에서 계산", PIVOTAL, "monthly",
                            **{**common, "unit": "지수", "change_mode": "none"}, default_series=[INDEX_NAMES[k] for k in ("iHFC", "iGBM", "iMST")],
                            description=f"모든 전략에 자료가 있는 공통 기간의 직전 월말({baseline})을 100으로 놓고 월별 수익률을 복리로 누적합니다. 화면 기간 필터를 바꿔도 기준 100 날짜는 유지됩니다.")
    return docs


def parse_adv(text, legal_name, crd, today):
    header = text[:2000]
    if "Primary Business Name: " + legal_name not in header or not re.search(r"CRD Number:\s*" + str(crd) + r"\b", header):
        raise ValueError("Wrong legal entity/CRD")
    match = re.search(r"\b(\d{1,2}/\d{1,2}/\d{4})\s+\d{1,2}:\d{2}", header)
    if not match:
        raise ValueError("Missing filing date")
    day = datetime.strptime(match[1], "%m/%d/%Y").date().isoformat()
    position = text.find("Regulatory Assets Under Management")
    if position < 0:
        raise ValueError("Missing Item 5.F")
    block = text[position:position + 2100]
    amounts = []
    for label in ("Discretionary:", "Non-Discretionary:", "Total:"):
        m = re.search(re.escape(label) + r"\s*\([abc]\)\s*\$\s*([\d,]+)", block)
        if not m:
            raise ValueError("Missing labeled RAUM amount")
        amounts.append(int(m[1].replace(",", "")))
    if amounts[0] + amounts[1] != amounts[2] or amounts[2] <= 0:
        raise ValueError("RAUM components do not reconcile")
    values = {}
    put(values, day, amounts[2], today)
    return {"date": day, "value": amounts[2], "discretionary": amounts[0], "non_discretionary": amounts[1],
            "valuation_date": None, "filing_type": "Annual amendment" if "\nAnnual Amendment" in header else "Other-than-annual amendment",
            "sha256": hashlib.sha256(text.encode()).hexdigest()}


def collect_manager(session, today, manager, out=OUT):
    key, name, legal, crd, style = manager
    url = f"https://reports.adviserinfo.sec.gov/reports/ADV/{crd}/PDF/{crd}.pdf"
    response = get(session, url, {})
    if not response.content.startswith(b"%PDF"):
        raise ValueError("SEC PDF response changed")
    with fitz.open(stream=response.content, filetype="pdf") as pdf:
        # Item 5.F can span pages and follow long schedules. Preserve page order.
        pages = [page.get_text() for page in pdf]
    point = parse_adv("\n".join(pages), legal, crd, today)
    point["source"] = url
    point["pdf_sha256"] = hashlib.sha256(response.content).hexdigest()
    path = out / ("us_raum_" + key + ".json")
    old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    history = {p["date"]: p for p in old.get("filings", [])}
    if history and point["date"] < max(history):
        raise ValueError("SEC filing regressed")
    history[point["date"]] = point
    cid = "us_raum_" + key
    card = doc(cid, name + " / SEC 신고 RAUM", {"규제상 AUM / RAUM": [[d, p["value"] / 1e9] for d, p in sorted(history.items())]},
               today, "SEC Form ADV · Item 5.F.(2)(c)", url, "irregular",
               filings=list(history.values()), crd=crd, legal_name=legal, style=style,
               description=RAUM_NOTE,
               note="가로축은 신고일이며 자산 평가일이 아닙니다. 일반적으로 연간 갱신하며 연중 변경 신고도 있습니다. 신고가 바뀌어도 AUM이 새로 평가됐다는 뜻은 아닙니다. 현재 확보한 신고부터 이력을 누적하며 과거 연말 잔고는 추정하지 않습니다.",
               basis_details=[{"label": "집계 범위", "value": legal + f" (CRD {crd})의 공시 범위입니다. 그룹 전체의 모든 법인·모든 상품을 합친 값으로 간주하지 않습니다."},
                              {"label": "성과", "value": "운용사 전체의 동일 기준 공식 수익률 시계열 미확인. AUM 증감은 자금 유출입·집계 범위 변화 등이 포함되어 투자수익률이 아닙니다."},
                              {"label": "과거 이력", "value": "SEC 과거 벌크 CSV/XLSX는 공개되어 있으나 현재 수집 환경에서 다운로드가 거부되어 아직 연결하지 못했습니다. 최신 공식 PDF 신고값부터 누적합니다."}],
               default_series=["규제상 AUM / RAUM"])
    return {cid: card}


def collect_psh_manual(today):
    rows = list(csv.DictReader((ROOT / "manual/psh_performance.csv").open(encoding="utf-8")))
    series = {"PSH NAV / 보수 차감 후": [], "S&P 500 / 총수익": []}
    for row in rows:
        day = row["year"] + "-12-31"
        for name, key in zip(series, ("psh", "sp500")):
            pts = {}; put(pts, day, row[key], today, -100)
            if any(p[0] == day for p in series[name]):
                raise ValueError("Duplicate PSH annual year")
            series[name].append([day, pts[day]])
    cid = "psh_returns_annual"
    annual = doc(cid, "Pershing Square Holdings / 연간 NAV 수익률", series, today,
                     "PSH 2025 연차보고서 · 공식 확인값", rows[0]["source"], "yearly", unit="%", manual=True, change_mode="none",
                     default_series=list(series),
                     description="PSH 개별 상품의 USD NAV 총수익률이며 보수·배당 재투자를 반영합니다. Pershing Square 운용사 전체 성과나 PSH 상장주가 수익률과 다릅니다.",
                     note="2025 연차보고서의 PSH 구간(2013년부터)만 옮겼습니다. 2004~2012년 다른 펀드(PSLP) 성과를 연결하지 않습니다. S&P 500은 동일 보고서의 배당 포함 총수익 비교값입니다. 이 카드는 공식 보고서 확인 후 수동 갱신하며 새 연도·월 자료의 자동 수집을 뜻하지 않습니다.",
                     methodology_url="https://pershingsquareholdings.com/performance/nav/",
                     basis_details=[{"label": "원문 위치", "value": "2025 Annual Report 인쇄 페이지 2 / PDF 4페이지 Company Performance 표. 첫 번째 PSLP/PSH Net Return 열은 2013년부터 PSH입니다. PSLP Net Return 열과 구분합니다."}])
    monthly_rows = list(csv.DictReader((ROOT / "manual/psh_monthly.csv").open(encoding="utf-8")))
    monthly = {}
    for row in monthly_rows:
        put(monthly, row["date"], row["return"], today, -100)
    cid_monthly = "psh_returns_monthly"
    month_doc = doc(cid_monthly, "Pershing Square Holdings / 월별 NAV 수익률", {"PSH NAV / 월간 수익률": sorted(monthly.items())}, today,
                    "PSH 공식 NAV·성과 표 · 확인값", monthly_rows[0]["source"], "monthly", unit="%", manual=True, monthly_axis=True,
                    change_mode="percentage_points", default_series=["PSH NAV / 월간 수익률"],
                    description="2026년 월말 공식 MTD 수익률입니다. USD NAV 기준, 보수 차감·배당 재투자를 반영하며 운용사 전체나 상장주가 성과와 다릅니다.",
                    note="공식 웹 표에서 확인한 2026년 1~9월 값이며 2026-09-30 공표 YTD는 -9.6%입니다. MTD 공표값은 소수 첫째 자리로 반올림되어 복리 계산값과 공식 YTD가 다를 수 있습니다. 웹 자동 다운로드가 거부되어 현재는 공식 자료 확인 후 수동 갱신합니다.")
    return {cid: annual, cid_monthly: month_doc}


def refresh_directory(today, out=OUT):
    managers = []
    for key, name, legal, crd, style in MANAGERS:
        path = out / ("us_raum_" + key + ".json")
        if path.exists():
            card = json.loads(path.read_text(encoding="utf-8"))
            managers.append({"id": key, "name": name, "legal_name": legal, "crd": crd, "style": style,
                             "latest": max(card["filings"], key=lambda p: p["date"]), "fetched": card["fetched"],
                             "observations": len(card["filings"]), "performance": "PSH 개별 상품 성과를 아래에 별도 표시" if key == "pershing" else "운용사 전체 공식 성과 시계열 미확인"})
    if not managers:
        raise ValueError("No adviser observations")
    value = {"id": "us_managers", "name": "미국 주요 운용사 / 신고 AUM", "managers": managers,
             "updated": max(m["latest"]["date"] for m in managers),
             "fetched": min(m["fetched"] for m in managers), "source_url": ADV, "note": RAUM_NOTE}
    write_cohort({"us_managers": value}, out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=["all", "ofr", "pivotal", "adv", "psh"], default="all")
    selected = parser.parse_args().source
    today = datetime.now(timezone(timedelta(hours=9))).date()
    session = requests.Session()
    failures = []
    jobs = []
    if selected in ("all", "ofr"):
        jobs.append(("OFR", lambda: collect_ofr(session, today)))
    if selected in ("all", "pivotal"):
        jobs.append(("PivotalPath", lambda: collect_pivotal(session, today)))
    if selected in ("all", "adv"):
        jobs += [(m[1], lambda m=m: collect_manager(session, today, m)) for m in MANAGERS]
    if selected in ("all", "psh"):
        jobs.append(("PSH official snapshots", lambda: collect_psh_manual(today)))
    for name, job in jobs:
        try:
            docs = job(); write_cohort(docs)
            print(name + ": " + str(len(docs)) + " documents validated")
        except Exception as exc:
            failures.append(name)
            print(name + ": preserved prior data: " + str(exc), file=sys.stderr)
    refresh_directory(today)
    if failures:
        raise SystemExit("Failed sources: " + ", ".join(failures))


if __name__ == "__main__":
    main()
