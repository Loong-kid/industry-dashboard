"""S&S Tech production disclosures: public DART HTML, no API key.

Backfill: python scripts/fetch_snstech_production.py --backfill
Daily:    python scripts/fetch_snstech_production.py
Rebuild:  python scripts/fetch_snstech_production.py --offline

Preserves normalized source tables and report receipts in data/_snstech.
Only compares the blank-mask business. Never mixes pieces with KRW or treats
annual rated capacity as a quarterly flow. See docs/SNSTECH_PRODUCTION.md.
"""
import argparse
import calendar
import csv
import datetime as dt
import io
import json
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "data" / "_snstech" / "production_reports.json"
OUT = ROOT / "data" / "semicon"
DART = "https://dart.fss.or.kr"
CORP_CODE = "00411048"
MONETARY_UNITS = {"천원": 100_000, "백만원": 100, "원": 100_000_000}


def compact(value):
    return re.sub(r"\s+", "", value)


def text(node):
    return " ".join(node.get_text(" ", strip=True).split())


def number(value):
    value = compact(value).replace(",", "").replace("%", "")
    if value in ("", "-", "–"):
        return None
    if not re.fullmatch(r"\d+(?:\.\d+)?", value):
        raise ValueError(f"Unexpected numeric cell: {value!r}")
    return float(value) if "." in value else int(value)


def period_end(year, month):
    return f"{year}-{month:02d}-{calendar.monthrange(year, month)[1]}"


def category(label):
    label = compact(label)
    if "반도체" in label:
        return "반도체용"
    if "TFT-LCD" in label:
        return "디스플레이용"
    if "블랭크마스크" in label:
        return "블랭크마스크"
    return None


def report_url(receipt):
    return f"{DART}/dsaf001/main.do?rcpNo={receipt}"


def parse_report(html, report, viewer_url):
    soup = BeautifulSoup(html, "html.parser")
    body = text(soup)
    start = body.index("생산능력")
    end = body.index("생산실적", start)
    capacity_text = body[start:end]
    capacity = {}
    for label, pattern in [
        ("반도체용", r"반도체용.*?생산능력은\s*([\d,]+)\s*장"),
        ("디스플레이용", r"TFT-LCD용.*?생산능력은\s*([\d,]+)\s*장"),
    ]:
        match = re.search(pattern, capacity_text)
        if match:
            capacity[label] = number(match[1])
    if not capacity:
        match = re.search(r"블랭크\s*마스크.*?생산능력은\s*([\d,]+)\s*장", capacity_text)
        if match:
            capacity["블랭크마스크"] = number(match[1])
    capacity_basis = "annual_rated" if capacity and "연간" in capacity_text else "ytd" if capacity else "undisclosed"
    if report["month"] == 12 and capacity:
        capacity_basis = "annual_rated"

    production_tables = [table for table in soup.find_all("table")
                         if all(word in compact(text(table)) for word in ("품목", "사업소", "블랭크마스크"))]
    if len(production_tables) != 1:
        raise ValueError(f"Expected one production table, found {len(production_tables)}")
    table = production_tables[0]
    rows = [[text(c) for c in row.find_all(["td", "th"], recursive=False)]
            for row in table.find_all("tr")]
    header = rows[0]
    year_headers = header[-3:]
    years = [int(re.search(r"(\d{4})년", value)[1]) for value in year_headers]
    # 2015 interim reports misprint their current-year label as 2014; fiscal
    # term 15 and the report title establish 2015. Preserve the original header.
    header_issue = years[0] != report["year"]
    if header_issue and not (report["year"] == 2015 and years[0] == 2014 and "제15기" in compact(year_headers[0])):
        raise ValueError(f"Unexpected report/table year mismatch: {year_headers[0]}")
    years[0] = report["year"]
    unit = next((compact(c) for row in rows[1:] for c in row if compact(c) in MONETARY_UNITS), None)
    if unit is None and re.search(r"생산실적.{0,100}?단위\s*:\s*장", body[end:]):
        unit = "장"
    if unit is None:
        raise ValueError("Unrecognized production unit")
    production = {}
    for row in rows[1:]:
        label = category(" ".join(row[:-3]))
        if label:
            if label in production:
                raise ValueError(f"Duplicate production category {label}")
            production[label] = [number(c) for c in row[-3:]]
    if not production or any(values[0] is None for values in production.values()):
        raise ValueError("Missing current production figures")

    hours_tables = [t for t in soup.find_all("table") if "실제가동시간" in compact(text(t))]
    if len(hours_tables) != 1:
        raise ValueError("Missing/ambiguous operating-hours table")
    hours_rows = [[text(c) for c in row.find_all(["td", "th"], recursive=False)]
                  for row in hours_tables[0].find_all("tr")]
    hours = {}
    for row in hours_rows[1:]:
        label = category(" ".join(row[:-3]))
        if label:
            available, actual, utilization = [number(c) for c in row[-3:]]
            if not available or actual is None or actual > available:
                raise ValueError(f"Invalid hours {row}")
            hours[label] = {"available": available, "actual": actual, "reported_utilization": utilization}
    if not hours:
        raise ValueError("Missing blank-mask hours")
    hours_issue = None
    if report["year"] == 2020 and report["month"] == 3 and hours.get("블랭크마스크", {}).get("available") == 53_856 and hours["블랭크마스크"]["actual"] == 41_969:
        hours_issue = "2020 Q1 원문의 시간 두 값이 2019년 연간값과 동일하며 2020년 반기 누적값보다 큼. 원문 보존, 분기 계산 제외."
    return {
        **report, "title": " ".join(report["title"].split()),
        "period": period_end(report["year"], report["month"]),
        "report_url": report_url(report["receipt"]), "viewer_url": viewer_url,
        "capacity": {"basis": capacity_basis, "unit": "장", "values": capacity, "disclosure_text": capacity_text},
        "production": {"unit": unit, "years": years, "values": production, "table_rows": rows},
        "hours": {"values": hours, "table_rows": hours_rows, "valid": hours_issue is None, "issue": hours_issue},
        "header_issue": "당기 연도 오기: 보고서 기간·제15기를 기준으로 2015년 적용" if header_issue else None,
    }


class DartClient:
    def __init__(self, cache_dir=None):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "Mozilla/5.0"
        self.session.mount("https://", HTTPAdapter(max_retries=Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["GET", "POST"])))
        self.cache_dir = cache_dir

    def get(self, path, params=None, cache_name=None):
        cached = self.cache_dir / cache_name if self.cache_dir and cache_name else None
        if cached and cached.exists():
            return cached.read_text(encoding="utf8")
        r = self.session.get(DART + path, params=params, timeout=(10, 45))
        r.raise_for_status()
        r.encoding = "utf8"
        time.sleep(.3)
        if cached:
            cached.parent.mkdir(parents=True, exist_ok=True)
            cached.write_text(r.text, encoding="utf8")
        return r.text

    def list_reports(self, start, end):
        self.get("/dsab007/main.do")
        reports = []
        # DART's public search silently returns no results for an overlong range.
        for year in range(start.year, end.year + 1, 4):
            first = max(start, dt.date(year, 1, 1))
            last = min(end, dt.date(year + 3, 12, 31))
            page = 1
            while True:
                params = {"currentPage": page, "maxResults": 100, "maxLinks": 10,
                          "textCrpCik": CORP_CODE, "textCrpNm": "101490", "option": "corp",
                          "startDate": first.strftime("%Y%m%d"), "endDate": last.strftime("%Y%m%d"),
                          "businessCode": "all", "corporationType": "all", "closingAccountsMonth": "all",
                          "finalReport": "recent", "publicType": ["A001", "A002", "A003"]}
                r = self.session.post(DART + "/dsab007/detailSearch.ax", data=params, timeout=(10, 45))
                r.raise_for_status(); r.encoding = "utf8"
                soup = BeautifulSoup(r.text, "html.parser")
                links = soup.select('a[id^="r_"]')
                for a in links:
                    title = text(a)
                    match = re.search(r"\((\d{4})\.(\d{2})\)", title)
                    if not match:
                        raise ValueError(f"Unrecognized filing period: {title}")
                    if int(match[2]) not in (3, 6, 9, 12):
                        raise ValueError(f"Unexpected fiscal year: {title}")
                    reports.append({"receipt": a["id"][2:], "title": title, "year": int(match[1]), "month": int(match[2])})
                time.sleep(.3)
                if len(links) < 100:
                    if not links and "조회 결과가 없습니다" not in text(soup):
                        raise ValueError("DART search did not return a valid results page")
                    break
                page += 1
                if page > 10:
                    raise ValueError("Unexpected report pagination")
        if not reports:
            raise ValueError("No periodic reports returned; keeping existing data")
        return sorted({r["receipt"]: r for r in reports}.values(), key=lambda r: r["receipt"])

    def fetch_report(self, report):
        receipt = report["receipt"]
        html = self.get("/dsaf001/main.do", {"rcpNo": receipt}, f"{receipt}_main.html")
        candidates = []
        for match in re.finditer(r'node\d+\[\'text\'\] = "([^"]+)";(.*?)(?=node\d+\[\'text\'\]|treeData.push|node\d+\[\'children\'\])', html, re.S):
            if "사업의 내용" in match[1]:
                params = dict(re.findall(r'node\d+\[\'(rcpNo|dcmNo|eleId|offset|length|dtd)\'\] = "([^"]*)"', match[2]))
                if len(params) == 6:
                    candidates.append(params)
        if not candidates:
            raise ValueError(f"Business section not found: {receipt}")
        params = candidates[0]
        url = requests.Request("GET", DART + "/report/viewer.do", params=params).prepare().url
        return parse_report(self.get("/report/viewer.do", params, f"{receipt}_business.html"), report, url)


def selected_reports(records):
    selected = {}
    for r in sorted(records, key=lambda r: r["receipt"]):
        selected[r["period"]] = r
    return selected


def total(values):
    if not values or any(v is None for v in values):
        return None
    return sum(values)


def cumulative(r, field):
    if field == "amount" and r["production"]["unit"] in MONETARY_UNITS:
        return total([v[0] for v in r["production"]["values"].values()]) / MONETARY_UNITS[r["production"]["unit"]]
    if field == "pieces" and r["production"]["unit"] == "장":
        return total([v[0] for v in r["production"]["values"].values()])
    if field in ("available", "actual") and r["hours"].get("valid", True):
        return total([v[field] for v in r["hours"]["values"].values()])
    if field == "capacity" and r["capacity"]["basis"] == "ytd":
        return total(list(r["capacity"]["values"].values()))
    return None


def quarter_value(reports, period, field):
    r = reports[period]
    prev = reports.get(period_end(r["year"], r["month"] - 3)) if r["month"] > 3 else None
    current = cumulative(r, field)
    # A full-year total can be differenced only against a YTD capacity value.
    if field == "capacity" and r["month"] == 12 and prev and prev["capacity"]["basis"] == "ytd":
        current = total(list(r["capacity"]["values"].values()))
    if current is None:
        return None, []
    if r["month"] == 3:
        return round(current, 6), [r]
    if not prev:
        return None, []
    previous = cumulative(prev, field)
    if previous is None:
        return None, []
    value = round(current - previous, 6)
    if value < 0:
        raise ValueError(f"Negative quarter value: {period} {field} {value}")
    return value, [r, prev]


def source_ref(records, label):
    return {"url": records[0]["viewer_url"], "label": label,
            "reports": [{"title": r["title"], "url": r["report_url"], "viewer_url": r["viewer_url"], "receipt": r["receipt"]} for r in records]}


def build_documents(records, fetched):
    reports = selected_reports(records)
    docs = {}

    def save(cid, name, unit, series, refs, description, note, **extra):
        # Keep gaps inside the disclosure window; do not extend old series with
        # absent future values (which would also produce a misleading headline).
        for label, pts in series.items():
            populated = [i for i, (_, v) in enumerate(pts) if v is not None]
            series[label] = pts[populated[0]:populated[-1] + 1] if populated else []
        valid = [d for points in series.values() for d, value in points if value is not None]
        docs[cid] = {"id": cid, "name": name, "unit": unit, "frequency": "quarterly",
                     "source": "DART · 에스앤에스텍 정기보고서", "source_url": refs[max(refs)]["url"],
                     "updated": max(valid), "fetched": fetched, "span_gaps": False, "zero_baseline": True,
                     "quarter_labels": True, "series": series, "default_series": list(series),
                     "point_sources": refs, "description": description, "note": note,
                     "basis_details": [{"label": "집계 대상", "value": "본사 및 공장의 블랭크마스크. 기타 Chemical·투자·컨설팅·부동산 사업 제외."},
                                       {"label": "분기 변환", "value": "Q1=3개월 누적, Q2=반기−Q1, Q3=9개월−반기, Q4=연간−9개월. 같은 해 직전 누적값·같은 단위가 없으면 결측."},
                                       {"label": "원문·재계산 자료", "value": "각 기간의 원문 링크는 표에 표시됩니다. 차감에 사용한 두 보고서와 누적 입력값은 공개 수집 기록에 보존합니다."}], **extra}

    def quarterly(field, label):
        pts, refs = [], {}
        for period in sorted(reports):
            value, sources = quarter_value(reports, period, field)
            pts.append([period, value])
            if sources:
                refs[period] = source_ref(sources, f'{reports[period]["year"]} Q{reports[period]["month"] // 3} · '+("3개월 누적" if len(sources) == 1 else "누적값 차감"))
            elif field in ("available", "actual"):
                r = reports[period]
                prev = reports.get(period_end(r["year"], r["month"] - 3)) if r["month"] > 3 else None
                refs[period] = source_ref([r] + ([prev] if prev else []), "원문 불일치 · 분기 계산 제외")
        return {label: pts}, refs

    series, refs = quarterly("amount", "블랭크마스크 생산실적")
    save("snstech_production_amount", "에스앤에스텍 · 분기 생산실적 · 금액", "억 원", series, refs,
         "공시 생산실적을 분기별 금액으로 환산한 값입니다. 마스크 장수나 매출액과는 다른 지표입니다.",
         "2012년 Q1부터 3개월 금액을 계산할 수 있습니다. 2011년 연간 보고서부터 단위가 장→천원으로 바뀌어 2011년 Q4 금액은 계산하지 않습니다. 천원÷100,000=억원.",
         quarterly_revenue_summary=True)

    hours, refs = quarterly("available", "가동가능시간")
    actual, _ = quarterly("actual", "실제가동시간")
    hours.update(actual)
    save("snstech_production_hours", "에스앤에스텍 · 분기 가동가능시간·실제가동시간", "시간", hours, refs,
         "공시된 생산설비의 가동가능시간과 실제가동시간입니다. 최근 생산 여력의 변화를 살펴볼 수 있습니다.",
         "가동가능시간은 생산능력 장수를 뜻하지 않습니다. 설비·공정의 시간 기준으로, 증설·집계 범위·작업일수 변화에 영향을 받습니다. 2009~2010년 품목별 시간은 블랭크마스크 범위에서 합산했습니다. 2020 Q1은 원문 시간값이 전년 연간값과 같고 반기 누적보다 커서, Q1·Q2의 분기 시간을 결측 처리했습니다.")

    utilization, cumulative_utilization = [], []
    for period in sorted(reports):
        available, _ = quarter_value(reports, period, "available")
        actual, _ = quarter_value(reports, period, "actual")
        utilization.append([period, round(actual / available * 100, 2) if available and actual is not None else None])
        r = reports[period]
        ca, cb = cumulative(r, "available"), cumulative(r, "actual")
        cumulative_utilization.append([period, round(cb / ca * 100, 2) if ca and cb is not None else None])
    save("snstech_production_utilization", "에스앤에스텍 · 분기 가동률", "%",
         {"분기 가동률(시간 기준)": utilization, "연초 누적 가동률(시간 기준)": cumulative_utilization}, refs,
         "각 분기의 실제가동시간÷가동가능시간입니다. 2·3·4분기도 해당 3개월의 가동률로 다시 계산합니다.",
         "공시에 나오는 평균가동률은 연초 누적 기준입니다. 누적 가동률끼리 빼지 않고, 누적 시간을 차감한 뒤 비율을 계산합니다. 품목별 시간 합산·공시 반올림 때문에 원문 %와 소폭 다를 수 있습니다. 2020 Q1 원문 시간값에 불일치가 있어 Q1·Q2 분기 가동률은 결측입니다.",
         change_mode="none", default_series=["분기 가동률(시간 기준)"])

    # Backward annual comparisons extend monetary history to 2009. The latest
    # filing's comparable value replaces earlier annual values (2011, 2021).
    annual = {}
    for r in sorted(reports.values(), key=lambda r: r["receipt"]):
        p = r["production"]
        if p["unit"] not in MONETARY_UNITS:
            continue
        for col, year in enumerate(p["years"]):
            if col == 0 and r["month"] != 12:
                continue
            value = total([v[col] for v in p["values"].values()])
            if value is not None:
                annual[period_end(year, 12)] = (round(value / MONETARY_UNITS[p["unit"]], 6), r, col)
    annual_refs = {d: source_ref([r], f'{d[:4]}년 연간 · {r["title"]}의 '+("당기값" if col == 0 else "비교연도 값")) for d, (_, r, col) in annual.items()}
    save("snstech_production_annual", "에스앤에스텍 · 연간 생산실적 · 과거 비교값 포함", "억 원",
         {"연간 블랭크마스크 생산실적": [[d, annual[d][0]] for d in sorted(annual)]}, annual_refs,
         "분기 금액을 계산할 수 없는 초기 연도도 후속 보고서의 연간 비교값으로 확인할 수 있습니다.",
         "2009년부터의 연간 금액입니다. 같은 연도·단위·블랭크마스크 범위의 값 중 가장 최근 정기보고서의 비교값을 적용합니다. 분기 차트는 해당 연도 당시 공시 누적값을 사용하므로 후속 연간 비교값과 차이가 있을 수 있습니다.",
         frequency="yearly", year_labels=True, quarter_labels=False, annual_axis=True, full_range=True)

    pieces, refs = quarterly("pieces", "분기 생산실적(장)")
    capacity_points = []
    for period in sorted(reports):
        r = reports[period]
        if r["year"] == 2009:
            value, sources = quarter_value(reports, period, "capacity")
            capacity_points.append([period, value])
            if sources:
                refs[period] = source_ref(sources, f'2009 Q{r["month"] // 3} · 수량 누적값 차감')
        else:
            capacity_points.append([period, None])
    # Only show the historical disclosure window; future absent observations
    # would leave this full-range archival chart mostly empty.
    historical = [p for p in pieces["분기 생산실적(장)"] if p[0] <= "2011-09-30"]
    save("snstech_production_pieces", "에스앤에스텍 · 생산능력·생산실적 · 과거 분기 수량", "장",
         {"분기 생산실적(장)": historical, "분기 생산능력(장)": [p for p in capacity_points if p[0] <= "2011-09-30"]}, refs,
         "장수로 공개하던 기간의 분기 생산실적입니다. 2009년에는 누적 생산능력도 공시해 분기별로 차감했습니다.",
         "생산실적 수량: 2009 Q1~2011 Q3. 분기 생산능력: 2009 Q1~Q4만 표시. 2010~2011 Q3의 능력 공시는 연간 기준이므로 이 차트에 분기 장수로 넣지 않습니다. 반도체·디스플레이 마스크는 크기가 다르므로 합계 장수를 면적으로 해석할 수 없습니다.",
         full_range=True)

    rated, rated_refs = [], {}
    for period in sorted(reports):
        r = reports[period]
        if r["capacity"]["basis"] == "annual_rated":
            rated.append([period, total(list(r["capacity"]["values"].values()))])
            rated_refs[period] = source_ref([r], r["title"] + " · 연간 생산능력")
    save("snstech_production_capacity", "에스앤에스텍 · 연간 생산능력 · 분기 공시 시점", "장/년",
         {"공시된 연간 생산능력": rated}, rated_refs,
         "각 보고서가 명시한 연간 기준 생산능력입니다. 분기마다 확인한 값이며, 한 분기의 생산가능 장수가 아닙니다.",
         "2009년 연말~2011 Q3의 공개값. 2011년 연간 보고서부터 최신 보고서까지 생산능력 장수는 공개하지 않고 산정 방식만 설명합니다. 연간 장수를 4로 나눈 추정값이나 가동률로 역산한 장수를 실제 공시값으로 채우지 않습니다.",
         full_range=True)
    latest = reports[max(reports)]
    docs["snstech_production_capacity"]["collection_status"] = {
        "checked": fetched, "ok": True,
        "message": latest["title"] + "까지 확인 · 이후 생산능력 장수 비공개" if latest["capacity"]["basis"] == "undisclosed" else latest["title"] + " 확인",
    }
    return docs


def write_outputs(records, fetched):
    documents = build_documents(records, fetched)
    # Build and validate all outputs before writing any files.
    reports = selected_reports(records)
    buf = io.StringIO(newline="")
    fields = ["period", "production_100m_krw", "production_pieces", "capacity_pieces", "available_hours", "actual_hours", "quarter_utilization_pct", "annual_rated_capacity_pieces", "hours_issue", "receipt", "previous_receipt", "report_url", "viewer_url"]
    writer = csv.DictWriter(buf, fieldnames=fields, lineterminator="\n"); writer.writeheader()
    for period, r in sorted(reports.items()):
        values = {field: quarter_value(reports, period, field)[0] for field in ["amount", "pieces", "capacity", "available", "actual"]}
        prev = reports.get(period_end(r["year"], r["month"] - 3)) if r["month"] > 3 else None
        writer.writerow({"period": period, "production_100m_krw": values["amount"], "production_pieces": values["pieces"], "capacity_pieces": values["capacity"],
                         "available_hours": values["available"], "actual_hours": values["actual"],
                         "quarter_utilization_pct": round(values["actual"] / values["available"] * 100, 2) if values["available"] and values["actual"] is not None else None,
                         "annual_rated_capacity_pieces": total(list(r["capacity"]["values"].values())) if r["capacity"]["basis"] == "annual_rated" else None,
                         "hours_issue": r["hours"].get("issue") or ("직전 분기 누적 시간값 불일치로 분기 계산 제외" if prev and prev["hours"].get("issue") else None),
                         "receipt": r["receipt"], "previous_receipt": prev["receipt"] if prev else "", "report_url": r["report_url"], "viewer_url": r["viewer_url"]})
    ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    ARCHIVE.write_text(json.dumps({"corp_code": CORP_CODE, "records": sorted(records, key=lambda r: r["receipt"])}, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    (ARCHIVE.parent / "production_quarterly.csv").write_text(buf.getvalue(), encoding="utf8", newline="\n")
    for cid, doc in documents.items():
        (OUT / f"{cid}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
        points = [p for pts in doc["series"].values() for p in pts if p[1] is not None]
        print(f'{cid}: {len(points)} values, {min(p[0] for p in points)} ~ {max(p[0] for p in points)}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backfill", action="store_true")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--cache-dir", type=Path, help="Optional research HTML cache; never committed")
    parser.add_argument("--as-of", type=dt.date.fromisoformat, default=dt.date.today())
    args = parser.parse_args()
    records = json.loads(ARCHIVE.read_text(encoding="utf8"))["records"] if ARCHIVE.exists() else []
    if not args.offline:
        client = DartClient(args.cache_dir)
        start = dt.date(2000, 1, 1) if args.backfill or not records else dt.date(args.as_of.year - 2, 1, 1)
        known = {r["receipt"] for r in records}
        for report in client.list_reports(start, args.as_of):
            if report["receipt"] not in known:
                record = client.fetch_report(report)
                records.append(record)
                print(f'Collected {record["period"]} {record["receipt"]}', flush=True)
    if not records:
        raise ValueError("No production reports collected")
    write_outputs(records, args.as_of.isoformat())


if __name__ == "__main__":
    main()
