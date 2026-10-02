"""Japan MOF/e-Stat monthly exports; public CSV downloads, no API key.

The annual files contain individual monthly columns AND year-to-date totals.
Only months explicitly published in the table title enter the charts. Values
are thousand JPY and Quantity2 is square metres for these two export codes.
Parsed country records and source metadata are versioned for reproducibility;
unchanged releases require no CSV download. --refresh forces a re-download.
"""
import argparse
import calendar
import csv
from datetime import date
import io
import json
from pathlib import Path
import re
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data/_japan_customs/exports.json"
OUT = ROOT / "data/semicon"
SOURCE = "https://www.customs.go.jp/toukei/info/tsdl_e.htm"
LIST_URL = ("https://www.e-stat.go.jp/en/stat-search/files?cycle=1&layout=datalist"
            "&tclass1=000001013180&tclass2=000001013181"
            "&toukei=00350300&tstat=000001013141")
PRODUCTS = {
    "370199000": ("jp_blank", "일본 블랭크마스크 관련 품목", "감광성·미노광 플레이트/평면 필름 중 기타(비컬러, 각 변 255mm 이하). KOTRA가 일본 블랭크마스크 수출 분석에 사용한 코드입니다."),
    "370130000": ("jp_plate_large", "일본 대형 감광 플레이트", "감광성·미노광 플레이트/평면 필름 중 한 변이 255mm를 넘는 품목. 디스플레이용 마스크 외 인쇄용 등도 포함할 수 있는 보조지표입니다."),
}
COUNTRIES = {"106": "대만", "103": "한국", "105": "중국", "304": "미국", "112": "싱가포르", "113": "말레이시아"}
MONTHS = list(calendar.month_abbr)[1:]
NOTE = ("일본의 수출통계이며 회사별 매출이나 순수 블랭크마스크/EUV 물량을 뜻하지 않습니다. "
        "EUV·DUV 및 제조사를 구분할 수 없고 일본 밖 생산은 제외됩니다. "
        "한국의 반도체 전용 HS 및 USD/kg 단가와 범위·단위가 다릅니다.")


def get(session, url):
    response = session.get(url, timeout=(20, 90))
    response.raise_for_status()
    return response


def discover_years(session):
    soup = BeautifulSoup(get(session, LIST_URL).content, "html.parser")
    years = {}
    for anchor in soup.select("a[href]"):
        query = parse_qs(urlparse(anchor["href"]).query)
        value = query.get("year", [""])[0]
        if re.fullmatch(r"\d{4}0", value) and "month" in query:
            years[int(value[:4])] = urljoin(LIST_URL, anchor["href"])
    if not years:
        raise ValueError("No annual export releases discovered")
    return years


def discover_release(session, year, url):
    soup = BeautifulSoup(get(session, url).content, "html.parser")
    candidates = [a for a in soup.select("a[href]") if "Section VI Chapter 28-38" in a.get_text()]
    if len(candidates) != 1:
        raise ValueError(f"{year}: expected one Section VI export table, got {len(candidates)}")
    anchor = candidates[0]
    title = anchor.get_text(" ", strip=True)
    match = re.search(r"Export Jan(?:-([A-Za-z]{3}))?:", title)
    end_month = (match[1] or "Jan") if match else None
    if end_month not in MONTHS:
        raise ValueError(f"Unknown release period: {title}")
    container = anchor.parent.parent
    download = container.select_one('a[data-file_type="CSV"]')
    if not download:
        raise ValueError(f"Missing CSV link for {year}")
    updated = re.search(r"Update date\s*(\d{4}-\d{2}-\d{2})", container.get_text(" ", strip=True))
    if not updated:
        raise ValueError(f"Missing revision date for {year}")
    return {"year": year, "published_month": MONTHS.index(end_month) + 1,
            "title": title, "release_date": updated[1],
            "csv_url": urljoin(url, download["href"]),
            "file_id": download.get("data-file_id"), "table_url": urljoin(url, anchor["href"])}


def parse_csv(content, year, published_month):
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
    required = {"Exp or Imp", "Year", "HS", "Country", "Unit2", "Value-Year", "Quantity2-Year"}
    required |= {f"{field}-{month}" for month in MONTHS for field in ["Value", "Quantity2"]}
    if not required.issubset(reader.fieldnames or []):
        raise ValueError("Unexpected CSV schema")
    records, seen, found = [], set(), set()
    for row in reader:
        hs = row["HS"].strip().strip("'")
        if hs not in PRODUCTS:
            continue
        if row["Exp or Imp"] != "1" or int(row["Year"]) != year or row["Unit2"].strip() != "SM":
            raise ValueError(f"Wrong direction/year/quantity unit: {hs}")
        country = row["Country"].strip()
        # Country-by-commodity CSV must contain partner countries only. Never
        # add a world/region subtotal to the sum of individual countries.
        if not country.isdigit() or not 100 <= int(country) <= 703:
            raise ValueError(f"Unexpected country/subtotal code: {country}")
        key = (hs, country)
        if key in seen:
            raise ValueError(f"Duplicate country row: {key}")
        seen.add(key)
        found.add(hs)
        values = [int(row[f"Value-{m}"]) for m in MONTHS]
        areas = [int(row[f"Quantity2-{m}"]) for m in MONTHS]
        if min(values + areas) < 0:
            raise ValueError("Negative trade data")
        if any(values[published_month:] + areas[published_month:]):
            raise ValueError("Nonzero data beyond the published period")
        if sum(values) != int(row["Value-Year"]) or sum(areas) != int(row["Quantity2-Year"]):
            raise ValueError(f"Monthly values do not reconcile with YTD: {key}")
        for month in range(1, published_month + 1):
            records.append([hs, f"{year}-{month:02d}-01", country, values[month - 1], areas[month - 1]])
    if found != set(PRODUCTS):
        raise ValueError(f"Missing product rows: {set(PRODUCTS) - found}")
    return records


def point_series(months, rows, field, countries=None):
    buckets = {m: 0 for m in months}
    for hs, month, country, value, area in rows:
        if countries is None or country in countries:
            buckets[month] += value if field == "value" else area
    # Value column: thousand yen -> million yen; quantity: m² unchanged.
    scale = 1000 if field == "value" else 1
    return [[m, round(buckets[m] / scale, 3)] for m in months]


def unit_values(values, areas):
    # Ratios use original amounts, not a mean of country unit values.
    return [[v[0], round(v[1] * 1_000_000 / a[1], 2) if a[1] > 0 else None]
            for v, a in zip(values, areas)]


def build_docs(cache, today):
    all_rows = [r for entry in cache["years"].values() for r in entry["records"]]
    months = sorted({r[1] for r in all_rows})
    sources = [entry["release"] for _, entry in sorted(cache["years"].items())]
    docs = []
    for hs, (prefix, name, description) in PRODUCTS.items():
        rows = [r for r in all_rows if r[0] == hs]
        values = point_series(months, rows, "value")
        areas = point_series(months, rows, "area")
        value_countries = {name: point_series(months, rows, "value", {code}) for code, name in COUNTRIES.items()}
        area_countries = {name: point_series(months, rows, "area", {code}) for code, name in COUNTRIES.items()}
        other = set(r[2] for r in rows) - set(COUNTRIES)
        value_countries["기타"] = point_series(months, rows, "value", other)
        area_countries["기타"] = point_series(months, rows, "area", other)
        cards = [
            ("amount", "세계 수출액", "백만 엔", {"세계 수출액": values}, ["세계 수출액"]),
            ("area", "세계 수출 면적", "㎡", {"세계 수출 면적": areas}, ["세계 수출 면적"]),
            ("price", "세계 면적당 수출액", "엔/㎡", {"면적당 수출액": unit_values(values, areas)}, ["면적당 수출액"]),
        ]
        if prefix == "jp_blank":
            cards += [
                ("country", "목적지별 수출액", "백만 엔", value_countries, ["대만", "한국", "중국", "미국"]),
                ("country_area", "목적지별 수출 면적", "㎡", area_countries, ["대만", "한국", "중국", "미국"]),
                ("country_price", "목적지별 면적당 수출액", "엔/㎡", {c: unit_values(value_countries[c], area_countries[c]) for c in COUNTRIES.values()}, ["대만", "한국", "중국", "미국"]),
            ]
        for suffix, label, unit, series, defaults in cards:
            note = NOTE
            if "price" in suffix:
                note += " 면적당 수출액은 수출금액÷신고면적이며 제품 구성에 따라 변합니다. 장당 ASP가 아니며, 면적 0이면 단가를 표시하지 않습니다."
            docs.append({"id": f"{prefix}_{suffix}", "name": f"{name} · {label}",
                         "unit": unit, "frequency": "monthly", "source": "일본 재무성 무역통계 · e-Stat 공개 CSV",
                         "source_url": sources[-1]["table_url"], "updated": months[-1], "fetched": today,
                         "default_series": defaults, "series": series, "description": f"HS {hs} · {description}",
                         "note": note, "monthly_trade_summary": True, "span_gaps": False, "source_releases": sources,
                         "collection_status": {"ok": True, "checked": today, "message": f"{months[0][:7]}~{months[-1][:7]} · {len(months)}개월 · 최신 공표 {sources[-1]['release_date']} · 월별 원자료"}})
    return docs


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-year", type=int, default=2021)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    today = date.today().isoformat()
    session = requests.Session()
    session.headers["User-Agent"] = "IndustryKPIDashboard/1.0 (public Japan trade statistics)"
    session.mount("https://", HTTPAdapter(max_retries=Retry(total=3, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504])))
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {"schema_version": 1, "years": {}}
    urls = discover_years(session)
    expected = set(range(args.start_year, max(urls) + 1))
    if not expected.issubset(urls):
        raise ValueError("Missing annual releases")
    # Keep one release per year: a new CSV replaces the entire year's rows,
    # including any downward revisions and deleted country/month values.
    for year in sorted(expected):
        release = discover_release(session, year, urls[year])
        existing = cache["years"].get(str(year))
        if args.refresh or not existing or existing["release"] != release:
            records = parse_csv(get(session, release["csv_url"]).content, year, release["published_month"])
            cache["years"][str(year)] = {"release": release, "records": records}
            print(f"{year}: downloaded {len(records)} product/country/month records ({release['title']})")
        else:
            print(f"{year}: release unchanged")
    # No writes until every requested release has passed parsing/validation.
    cache["years"] = {str(y): cache["years"][str(y)] for y in sorted(expected)}
    docs = build_docs(cache, today)
    write_json(CACHE, cache)
    for doc in docs:
        write_json(OUT / f"{doc['id']}.json", doc)
    print(f"Saved {len(docs)} indicators; latest month {docs[0]['updated']}")


if __name__ == "__main__":
    main()
