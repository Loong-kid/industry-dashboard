"""Collect public U.S. power costs and solar market data for the dashboard."""

import argparse
import calendar
import io
import json
import math
import re
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from openpyxl import load_workbook


OUT = Path(__file__).resolve().parents[1] / "data" / "energy-market"
S3 = "https://oedi-data-lake.s3.amazonaws.com/"
ATB_PREFIX = "ATB/electricity/parquet/"
ATB_SITE = "https://atb.nlr.gov/electricity/"
BERKELEY_SITE = "https://eta-publications.lbl.gov/publications/us-utility-scale-solar-{}-edition"
EIA_PAGE = "https://www.eia.gov/electricity/monthly/epm_table_grapher.php?t=table_6_01_b"
EIA_BOOK = "https://www.eia.gov/electricity/monthly/xls/table_6_01_b.xlsx"
SCENARIOS = {"Moderate": "중간", "Conservative": "보수", "Advanced": "낙관"}
GAS = ("NaturalGas_FE", "NG 2-on-1 Combined Cycle (H-Frame)", "H-Frame CC")
POWER_TYPES = {
    ("UtilityPV", "Class5", "Tracking PV"): "대형 태양광",
    ("Utility-Scale PV-Plus-Battery", "Class5", "Utility-Scale PV-Plus Battery"): "태양광+ESS",
    ("LandbasedWind", "Class4", "Wind Turbine Technology 1"): "육상풍력",
    ("OffShoreWind", "Class3", "Fixed-Bottom"): "고정식 해상풍력",
    GAS: "H급 가스복합",
}
BATTERY = ("Utility-Scale Battery Storage", "4Hr Battery Storage", "Lithium Ion - 4 Hr")
METRIC_UNITS = {
    "CAPEX": "$/kW", "Fixed O&M": "$/kW-yr", "LCOE": "$/MWh", "CF": "", "Heat Rate": "MMBtu/MWh",
}
POWER_METRICS = {
    "CAPEX": ("atb_power_capex", "발전원별 설치비 (CAPEX)", "$/kW", 1),
    "Fixed O&M": ("atb_power_fixed_om", "발전원별 고정 운영비", "$/kW·년", 1),
    "LCOE": ("atb_power_lcoe", "발전원별 균등화발전비용 (LCOE)", "$/MWh", 1),
    "CF": ("atb_power_capacity_factor", "발전원별 설비이용률", "%", 100),
    "Heat Rate": ("atb_gas_heat_rate", "H급 가스복합 열소비율", "MMBtu/MWh", 1),
}
MONTHS = {name[:3].lower(): number for number, name in enumerate(calendar.month_name) if number}
SECTORS = ("주택용", "상업용", "산업용", "전체")


def get(url, **kwargs):
    response = requests.get(url, timeout=(12, 75), headers={"User-Agent": "Industry Dashboard data collector"}, **kwargs)
    response.raise_for_status()
    return response


def end_of_year(year):
    return f"{year}-12-31"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def annual_card(indicator, name, unit, series, **metadata):
    require(series and all(len(points) >= 2 for points in series.values()), f"Incomplete series: {indicator}")
    return {
        "id": indicator, "name": name, "unit": unit, "frequency": "yearly",
        "year_labels": True, "annual_axis": True, "span_gaps": False,
        "series": series, "default_series": list(series), **metadata,
    }


def latest_atb_key(index):
    versions = []
    for item in ET.fromstring(index).findall("{*}Contents"):
        key = item.findtext("{*}Key")
        match = re.fullmatch(rf"{ATB_PREFIX}(\d{{4}})/v(\d+)\.(\d+)\.(\d+)/ATBe\.parquet", key or "")
        if match:
            versions.append((tuple(map(int, match.groups())), key, item.findtext("{*}LastModified")))
    require(versions, "Could not locate a versioned Electricity ATB Parquet file")
    version, key, modified = max(versions)
    return version[0], key, date.fromisoformat(modified[:10]).isoformat()


def atb_rows(data):
    import pyarrow.compute as pc
    import pyarrow.parquet as pq

    columns = ["atb_year", "technology", "techdetail", "techdetail2", "core_metric_case", "crpyears",
               "core_metric_parameter", "core_metric_variable", "scenario", "units", "value"]
    table = pq.read_table(io.BytesIO(data), columns=columns)
    technologies = pc.field("technology").isin([item[0] for item in (*POWER_TYPES, BATTERY)])
    mask = (technologies & (pc.field("core_metric_case") == "R&D") & (pc.field("crpyears") == 30)
            & pc.field("scenario").isin(list(SCENARIOS)) & pc.field("core_metric_parameter").isin(list(METRIC_UNITS)))
    return table.filter(mask).to_pylist()


def build_atb(rows, edition, source_file, published, fetched):
    samples = {}
    for row in rows:
        tech = (row["technology"], row["techdetail"], row["techdetail2"])
        if tech not in POWER_TYPES and tech != BATTERY:
            continue
        metric = row["core_metric_parameter"]
        year = row["core_metric_variable"]
        scenario = row["scenario"]
        expected_unit = METRIC_UNITS[metric]
        value = row["value"]
        require(row["atb_year"] == edition and (row["units"] or "") == expected_unit
                and isinstance(year, int) and value is not None and math.isfinite(value) and value >= 0
                and (metric != "CF" or value <= 1),
                f"Unexpected ATB observation: {tech}, {metric}, {scenario}, {year}")
        series = samples.setdefault((tech, metric, scenario), {})
        require(year not in series, f"Duplicate ATB observation: {tech}, {metric}, {scenario}, {year}")
        series[year] = value

    def points(tech, metric, scenario, scale):
        values = samples.get((tech, metric, scenario), {})
        years = sorted(values)
        require(len(years) >= 20 and years == list(range(years[0], years[-1] + 1)),
                f"Incomplete ATB projection: {tech}, {metric}, {scenario}")
        return [[end_of_year(year), round(values[year] * scale, 2)] for year in years]

    base_year = min(samples.get((BATTERY, "CAPEX", "Moderate"), {}), default=0)
    require(2000 <= base_year <= edition, "Missing ATB base year")
    methodology = f"{ATB_SITE}{edition}/data"
    revision = source_file.rsplit("/", 2)[1]
    common = {
        "source": f"NLR {edition} Electricity ATB ({revision})", "source_url": source_file,
        "source_version": f"{edition} {revision}", "methodology_url": methodology,
        "updated": published, "fetched": fetched, "stale_days": 45,
        "forecast_from": f"{base_year + 1}-01-01", "forecast_baseline_label": "기준연도 추정",
        "point_annotations": {end_of_year(base_year): "ATB 기준연도 추정"},
        "forecast_label": "ATB 시나리오", "full_range": True, "change_mode": "none",
        "frequency_label": "연간 모형",
    }
    basis = [
        {"label": "자료 판본", "value": f"{edition} Electricity ATB {revision} · 원본 파일 기준일 {published}"},
        {"label": "비용 기준", "value": f"{base_year}년 실질 미국 달러. {base_year}년은 기준연도 추정이며 이후는 모형값입니다."},
    ]
    battery_basis = basis + [{"label": "설비", "value": "미국 60MW / 240MWh, 4시간 리튬인산철(LFP) 배터리 시스템."}]
    costs = {label: points(BATTERY, "CAPEX", scenario, 1 / 4) for scenario, label in SCENARIOS.items()}
    reference = {period[:4]: value for period, value in costs["중간"]}
    docs = [annual_card(
        "atb_ess_4h_capex", "미국 4시간 ESS 설치비 전망", "$/kWh", costs, **common,
        description=f"중간 시나리오 · {base_year}년 ${reference[str(base_year)]:,.0f}/kWh · 2035년 ${reference['2035']:,.0f}/kWh",
        basis_details=battery_basis + [{"label": "환산", "value": "전체 시스템 CAPEX($/kW)를 4시간으로 나눠 저장용량당 비용으로 환산했습니다."}],
    ), annual_card(
        "atb_ess_4h_fixed_om", "미국 4시간 ESS 고정 운영비 전망", "$/kW·년",
        {label: points(BATTERY, "Fixed O&M", scenario, 1) for scenario, label in SCENARIOS.items()},
        **common, basis_details=battery_basis,
    )]
    generation = [tech for tech in POWER_TYPES if tech != GAS]
    eligible_tech = {"LCOE": generation, "CF": generation, "Heat Rate": [GAS]}
    for metric, (indicator, title, unit, scale) in POWER_METRICS.items():
        kinds = eligible_tech.get(metric, POWER_TYPES)
        series = {POWER_TYPES[tech]: points(tech, metric, "Moderate", scale) for tech in kinds}
        detail = basis + [{"label": "모형 조건", "value": "중간 기술 시나리오, R&D 금융 조건, 30년 비용회수, 세액공제 미적용."}]
        if metric == "Heat Rate":
            detail += [{"label": "설비", "value": "탄소 포집 장치가 없는 H급 2-on-1 천연가스 복합 발전."}]
        else:
            detail += [{"label": "설비", "value": "태양광과 태양광+ESS는 Class 5, 육상풍력은 Class 4, 고정식 해상풍력은 Class 3, 가스복합은 H급 2-on-1 설비입니다. 차트별 가용 지표를 표시합니다."}]
        docs.append(annual_card(indicator, title, unit, series, **common, basis_details=detail))
    return docs


def load_atb(fetched):
    index = get(S3, params={"list-type": 2, "prefix": ATB_PREFIX}).content
    edition, key, modified = latest_atb_key(index)
    url = S3 + key
    return build_atb(atb_rows(get(url).content), edition, url, modified, fetched)


def sheet_rows(book, sheet, max_col):
    return list(book[sheet].iter_rows(max_col=max_col, values_only=True))


def find_header(rows, first_label, required_labels):
    for i, row in enumerate(rows):
        labels = [" ".join(cell.split()) if isinstance(cell, str) else cell for cell in row]
        if first_label in labels and all(label in labels for label in required_labels):
            return i, labels
    raise ValueError(f"Missing worksheet headers: {first_label}, {required_labels}")


def workbook_series(rows, year_col, value_cols, end_year, scale=1):
    series = {label: [] for label in value_cols}
    for row in rows:
        year = row[year_col]
        if type(year) is not int or not 1990 <= year <= end_year:
            continue
        for label, col in value_cols.items():
            value = row[col]
            if type(value) in (int, float) and math.isfinite(value):
                series[label].append([end_of_year(year), round(value * scale, 2)])
    for label, values in series.items():
        dates = [period for period, _ in values]
        require(dates == sorted(set(dates)), f"Duplicate or unordered project years: {label}")
    return series


def build_berkeley(book, edition, url, fetched):
    end_year = edition - 1
    intro = sheet_rows(book, "Introduction", 6)
    period_pattern = re.compile(r"([A-Za-z]+) " + str(edition))
    issue_month = next((period_pattern.fullmatch(row[5]) for row in intro
                        if isinstance(row[5], str) and period_pattern.fullmatch(row[5])), None)
    require(issue_month, "Berkeley Lab edition date is missing")
    issue = datetime.strptime(issue_month[0], "%B %Y").strftime("%Y-%m")
    publication = BERKELEY_SITE.format(edition)
    common = {
        "source": f"Berkeley Lab · Utility-Scale Solar {edition}", "source_url": url,
        "methodology_url": publication, "source_version": str(edition), "updated": end_of_year(end_year),
        "fetched": fetched, "stale_days": 45, "license": "CC BY 4.0", "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "full_range": True,
    }
    basis = [{"label": "발표", "value": f"Berkeley Lab {edition}년판 · {issue}"},
             {"label": "범위", "value": "미국 5MWac 초과 지상 설치 프로젝트를 대상으로 합니다."}]

    capacity = sheet_rows(book, "PV Capacity over Time", 80)
    i, _ = find_header(capacity, "Months", ["Monthly Cumulative Capacity Additions (GWAC)"])
    year_headers = capacity[i + 1]
    december = next(row for row in capacity[i + 2:] if row[0] == 12)
    additions = [[end_of_year(year), december[col]] for col, year in enumerate(year_headers)
                 if type(year) is int and 1990 <= year <= end_year and type(december[col]) in (int, float)]
    require(additions and additions[-1][0] == end_of_year(end_year), "Latest completed solar deployment year missing")
    docs = [annual_card(
        "berkeley_solar_additions", "미국 대형 태양광 연간 준공량", "GWac", {"준공 용량": additions}, **common,
        description="준공연도별 신규 설비 용량. 태양광 단독과 태양광+저장장치 프로젝트의 태양광 설비를 포함합니다.",
        basis_details=basis + [{"label": "원본 시트", "value": "PV Capacity over Time의 각 연도 12월 누적 준공량."}],
    )]

    capex = sheet_rows(book, "CapEx Trend (PV-only)", 17)
    i, headers = find_header(capex, "Solar COD", ["All Capacity (MWAC)", "All Median", "All Capacity-Weighted Mean"])
    ac_label = capex[i - 1][0]
    require(isinstance(ac_label, str) and re.fullmatch(rf"Installed Costs {end_year} \$/WAC", ac_label),
            "Unexpected Berkeley Lab CAPEX dollar-year or dimension")
    capex_data = workbook_series(capex[i + 1:], headers.index("Solar COD"), {
        "중앙값": headers.index("All Median"), "설비용량 가중평균": headers.index("All Capacity-Weighted Mean"),
    }, end_year)
    prelim = f"{end_year - 1}~{end_year}년 설치비에는 EIA 잠정치가 포함되어 후속 판본에서 수정될 수 있습니다."
    docs.append(annual_card(
        "berkeley_solar_capex", "미국 대형 태양광 단독 설치비", "$/Wac", capex_data, **common,
        description=f"준공연도별 프로젝트 설치비 · {end_year}년 실질 달러",
        note=prelim, basis_details=basis + [{"label": "원본 시트", "value": "CapEx Trend (PV-only)의 AC 용량 기준 요약표."}],
    ))

    ppa = sheet_rows(book, "LCOE vs. PPA Price (PV only)", 13)
    price_header = f"Generation-Weighted PPA ({end_year}$/MWh)"
    i, headers = find_header(ppa, "COD Year", [price_header])
    require(ppa[i - 1][7] == "project-level match of LCOE and PPA data" and headers[7] == "COD Year"
            and headers[12] == price_header, "Could not identify matched PPA sample")
    ppa_data = workbook_series(ppa[i + 1:], 7, {"발전량 가중평균": 12}, end_year)
    sample = [row[8] for row in ppa[i + 1:] if row[7] == end_year]
    require(len(sample) == 1 and type(sample[0]) is int and sample[0] > 0, "Latest PPA sample count missing")
    docs.append(annual_card(
        "berkeley_solar_ppa", "미국 대형 태양광 전력구매계약 가격", "$/MWh", ppa_data, **common,
        description=f"태양광 단독 프로젝트 준공연도별 균등화 PPA 가격 · {end_year}년 실질 달러",
        basis_details=basis + [{"label": "표본", "value": f"PPA와 LCOE가 모두 있는 프로젝트. {end_year}년 준공 표본 {sample[0]}개."},
                               {"label": "원본 시트", "value": "LCOE vs. PPA Price (PV only)의 프로젝트 매칭 표."}],
    ))

    cf = sheet_rows(book, "CF by Project Vintage", 8)
    annual_cf = f"Average Capacity-Weighted Capacity Factor in {end_year}"
    cumulative_cf = "Capacity-Weighted Cumulative Capacity Factor"
    i, headers = find_header(cf, "Project Vintage", [annual_cf, cumulative_cf])
    # The second table starts after this cohort table and uses different columns.
    cohort_end = next(j for j in range(i + 1, len(cf)) if cf[j][0] == "Project Vintage")
    utilization = workbook_series(cf[i + 1:cohort_end], headers.index("Project Vintage"), {
        "누적 이용률": headers.index(cumulative_cf), f"{end_year}년 운영 이용률": headers.index(annual_cf),
    }, end_year, 100)
    docs.append(annual_card(
        "berkeley_solar_capacity_factor", "미국 대형 태양광 설비이용률", "%", utilization, **common,
        description="같은 해에 준공된 설비를 묶어 비교한 용량 가중평균입니다. 가로축은 설비 준공연도입니다.",
        basis_details=basis + [{"label": "원본 시트", "value": "CF by Project Vintage의 준공연도별 요약표."}],
    ))
    for doc in docs[:3]:
        require(all(points[-1][0] == end_of_year(end_year) for points in doc["series"].values()),
                f"Latest completed year missing: {doc['id']}")
    return docs


def load_berkeley(fetched):
    year = int(fetched[:4])
    for edition in range(year, max(year - 2, 2025), -1):
        url = BERKELEY_SITE.format(edition)
        try:
            page = get(url).text
        except requests.HTTPError as exc:
            if exc.response.status_code in {403, 404} and edition > 2026:
                continue
            raise
        links = BeautifulSoup(page, "html.parser").find_all("a", href=True)
        expected = re.compile(rf"utility_scale_solar_{edition}_edition_datafile\.xlsx$", re.I)
        source = next((urljoin(url, a["href"]) for a in links if expected.search(a["href"])), None)
        require(source, f"Berkeley Lab workbook link missing for edition {edition}")
        with io.BytesIO(get(source).content) as data:
            book = load_workbook(data, read_only=True, data_only=True)
            try:
                return build_berkeley(book, edition, source, fetched)
            finally:
                book.close()
    raise ValueError("No current Berkeley Lab Utility-Scale Solar workbook found")


def eia_series(rows):
    i, _ = find_header(rows, "Period", ["Residential", "Commercial", "Industrial", "Total"])
    require(tuple(rows[i]) == ("Period", "Residential", "Commercial", "Industrial", "Total"), "EIA sector order changed")
    annual, monthly = ({sector: {} for sector in SECTORS} for _ in range(2))
    year = None
    for period, *values in rows[i + 1:]:
        label = str(period).strip()
        group = re.fullmatch(r"Year\s+(\d{4})", label)
        if group:
            year = int(group[1])
            continue
        if type(period) is int and 2000 <= period <= 2100:
            target, day = annual, end_of_year(period)
        elif year and label[:3].lower() in MONTHS:
            month = MONTHS[label[:3].lower()]
            target, day = monthly, date(year, month, calendar.monthrange(year, month)[1]).isoformat()
        else:
            continue
        require(all(type(value) in (int, float) and math.isfinite(value) and value >= 0 for value in values)
                and abs(sum(values[:3]) - values[3]) < 0.3, f"Unexpected sector capacity at {day}")
        for sector, value in zip(SECTORS, values):
            require(day not in target[sector], f"Duplicate EIA capacity at {day}")
            target[sector][day] = round(value / 1000, 4)
    require(len(annual["전체"]) >= 8 and len(monthly["전체"]) >= 24, "Incomplete EIA solar history")
    return annual, monthly


def load_eia(fetched):
    with io.BytesIO(get(EIA_BOOK).content) as data:
        book = load_workbook(data, read_only=True, data_only=True)
        try:
            annual, monthly = eia_series(sheet_rows(book, "Table_6_01_B", 5))
        finally:
            book.close()
    latest = max(monthly["전체"])
    current = date.fromisoformat(latest)
    page = BeautifulSoup(get(EIA_PAGE).text, "html.parser").get_text(" ", strip=True)
    release_line = re.search(rf"Data for {calendar.month_name[current.month]} {current.year}\s+Release Date:\s*([A-Za-z]+ \d{{1,2}}, \d{{4}})", page)
    require(release_line, "EIA workbook and publication page do not agree on the latest month")
    release = datetime.strptime(release_line[1], "%B %d, %Y").date().isoformat()
    existing = OUT / "eia_solar_small_scale_capacity.json"
    old = json.loads(existing.read_text(encoding="utf-8")) if existing.exists() else {}
    require(latest >= old.get("updated", ""), "EIA returned an older release")
    for sector in SECTORS:
        history = dict(old.get("series", {}).get(sector, []))
        monthly[sector] = history | monthly[sector]

    def series(observations):
        return {sector: list(sorted(observations[sector].items())) for sector in ("전체", *SECTORS[:-1])}

    provisional = {day: "EIA 잠정치" for day in monthly["전체"] if day[:4] == str(current.year)}
    monthly_view = {"label": "월간", "frequency": "monthly", "month_labels": True, "monthly_axis": True,
                    "series": series(monthly), "point_annotations": provisional}
    annual_view = {"label": "연말", "frequency": "yearly", "year_labels": True, "annual_axis": True,
                   "series": series(annual), "point_annotations": {}}
    return [{
        "id": "eia_solar_small_scale_capacity", "name": "미국 소규모 태양광 설비용량", "unit": "GWac",
        "frequency": "monthly", "series": monthly_view["series"], "default_series": ["전체"],
        "series_views": {"monthly": monthly_view, "annual": annual_view}, "default_view": "monthly",
        "span_gaps": False, "updated": latest, "fetched": fetched, "stale_days": 45,
        "source": "EIA Electric Power Monthly 6.1.B", "source_url": EIA_PAGE,
        "description": "1MW 미만 설비의 여름철 순설비용량을 추정한 월말·연말 집계입니다.",
        "basis_details": [{"label": "발표일", "value": release},
                          {"label": "원본", "value": "Electric Power Monthly 표 6.1.B. 부문별 MW를 GW로 환산했습니다."}],
    }]


def save(docs):
    OUT.mkdir(parents=True, exist_ok=True)
    for doc in docs:
        path = OUT / (doc["id"] + ".json")
        pending = path.with_suffix(".tmp")
        pending.write_text(json.dumps(doc, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n", encoding="utf-8")
        pending.replace(path)
        print(f"{doc['id']} · {doc['updated']}")


def main():
    sources = {"atb": load_atb, "berkeley": load_berkeley, "eia": load_eia}
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", choices=sources)
    args = parser.parse_args()
    fetched = datetime.now(timezone(timedelta(hours=9))).date().isoformat()
    save(sources[args.source](fetched))


if __name__ == "__main__":
    main()
