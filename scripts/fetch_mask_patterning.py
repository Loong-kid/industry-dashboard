"""Photronics SEC product revenue tables -> cached facts and mask-patterning charts.

Public company IR PDFs, no API key. Q1-Q3 use reported three-month values;
Q4 = annual product revenue - the same year's reported nine-month revenue.
Tekscend facts are reviewed snapshots. Mix amounts are explicitly approximate
allocations of consolidated photomask-business revenue, not disclosed product sales.
Run --backfill once, normally check recent filings, or --offline to rebuild.
"""
import argparse
import datetime as dt
import json
import re
from pathlib import Path
from urllib.parse import urljoin

import pymupdf
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data/_mask_patterning/photronics_filings.json"
TEKSCEND = ROOT / "manual/tekscend_sales_mix.json"
TEKSCEND_FINANCIALS = ROOT / "manual/tekscend_financials.json"
OUT = ROOT / "data/semicon"
BASE = "https://photronicsinc.gcs-web.com"
START_YEAR = 2021
MONTHS = "January February March April May June July August September October November December".split()
DATE_RE = r"(" + "|".join(MONTHS) + r")\s+(\d{1,2}),?\s+(\d{4})"
PRODUCTS = ("ic_high", "ic_main", "ic_total", "fpd_high", "fpd_main", "fpd_total")


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf8")


def iso_date(match):
    month, day, year = match.groups()
    return dt.date(int(year), MONTHS.index(month) + 1, int(day)).isoformat()


def read_pdf(url):
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    return pymupdf.open(stream=response.content, filetype="pdf")


def parse_photronics(pdf, filing):
    cover = pdf[0].get_text()
    end_match = re.search(r"(?:quarterly period|fiscal year) ended\s+" + DATE_RE, cover, re.I)
    if not end_match:
        raise ValueError("Missing fiscal period on SEC cover")
    date = iso_date(end_match)
    year, month = int(date[:4]), int(date[5:7])
    quarter = 4 if filing["form"] == "10-K" else {1: 1, 2: 1, 4: 2, 5: 2, 7: 3, 8: 3}.get(month)
    if not quarter:
        raise ValueError(f"Unexpected fiscal quarter end: {date}")
    all_text = " ".join(p.get_text() for p in pdf)
    if not re.search(r"\(in\s+(?:\$\s*)?thousands", all_text, re.I):
        raise ValueError("Unverified SEC financial statement unit")
    for page_index, page in enumerate(pdf):
        text = page.get_text()
        if "Revenue by Product Type" not in text or "Changes in Revenue" in text:
            continue
        block = text.split("Revenue by Product Type", 1)[1].split("Revenue by Geographic", 1)[0]
        if "Percent" in block or re.search(r"\d+\.\d+", block):
            continue  # MD&A tables are rounded $millions; use the financial note.
        # The note's numeric table is in $thousands (not the rounded MD&A table).
        rows = re.split(r"High[-\s]end|Mainstream|Total\s+IC|Total\s+FPD", block, flags=re.I)
        if len(rows) != 7:
            raise ValueError(f"Expected six product rows, got {len(rows)-1}")
        cols = 3 if quarter == 4 else 2 if quarter == 1 else 4
        numbers = {
            key: [int(v.replace(",", "")) for v in re.findall(r"\b\d[\d,]*\b", row)[:cols]]
            for key, row in zip(PRODUCTS, rows[1:])
        }
        if any(len(v) != cols for v in numbers.values()):
            raise ValueError("Truncated product revenue table")
        for col in range(cols):
            for prefix in ("ic", "fpd"):
                if numbers[prefix + "_high"][col] + numbers[prefix + "_main"][col] != numbers[prefix + "_total"][col]:
                    raise ValueError("High-end + mainstream does not reconcile with reported total")
        return {**filing, "fiscal_year": year, "quarter": quarter, "period_end": date,
                "pdf_page": page_index + 1, "unit": "thousand_usd", "table": numbers}
    raise ValueError("SEC product revenue note not found")


def list_filings(backfill=False):
    filings = []
    for group in ("496", "471"):
        response = requests.get(BASE + "/financial-information/sec-filings", params={
            "field_nir_sec_form_group_target_id[]": group, "items_per_page": 100,
        }, timeout=45)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        for row in soup.select("tbody tr"):
            form_link = row.select_one('a[href*="/sec-filing/10-q/"], a[href*="/sec-filing/10-k/"]')
            pdf_link = next((a for a in row.select("a[href]") if ".pdf" in a.get_text()), None)
            if not form_link or not pdf_link:
                continue
            filed = dt.datetime.strptime(row.select_one("td").get_text(strip=True), "%b %d, %Y").date().isoformat()
            if int(filed[:4]) < START_YEAR:
                continue
            if form_link.get_text(strip=True) == "10-K" and filed < f"{START_YEAR}-10-01":
                continue
            if not backfill and int(filed[:4]) < dt.date.today().year - 1:
                continue
            filings.append({"url": urljoin(BASE, pdf_link["href"]), "filed": filed,
                            "form": form_link.get_text(strip=True)})
    if not filings:
        raise ValueError("No Photronics SEC filings found")
    return sorted(filings, key=lambda f: (f["filed"], f["url"]))


def photronics_quarters(cache):
    filings = sorted(cache["filings"], key=lambda f: f["filed"])
    selected = {}
    for filing in filings:
        if filing["fiscal_year"] >= START_YEAR:
            selected[(filing["fiscal_year"], filing["quarter"])] = filing
    quarters = []
    for (year, q), filing in sorted(selected.items()):
        if q == 4:
            q3 = selected.get((year, 3))
            if not q3:
                continue
            vals = {key: filing["table"][key][0] - q3["table"][key][2] for key in PRODUCTS}
            sources = [source_ref(filing), source_ref(q3)]
        else:
            vals = {key: filing["table"][key][0] for key in PRODUCTS}
            sources = [source_ref(filing)]
        if any(v < 0 for v in vals.values()):
            raise ValueError(f"Negative product revenue in FY{year} Q{q}")
        for prefix in ("ic", "fpd"):
            if vals[prefix + "_high"] + vals[prefix + "_main"] != vals[prefix + "_total"]:
                raise ValueError("Quarter product totals do not reconcile")
        quarters.append({"fiscal_year": year, "quarter": q, "period_end": filing["period_end"],
                         "values": vals, "sources": sources, "derived": q == 4})
    if not quarters:
        raise ValueError("No usable Photronics product revenue observations")
    # Independent annual reconciliation. The notes round to $thousands, and
    # FY2022 has a published IC high-end/mainstream classification discrepancy.
    # Preserve the reported three-month facts; do not force the categories to fit.
    for (year, q), annual in selected.items():
        if q != 4:
            continue
        values = [r for r in quarters if r["fiscal_year"] == year]
        if len(values) == 4:
            differences = {key: sum(r["values"][key] for r in values) - annual["table"][key][0]
                           for key in PRODUCTS}
            for key in ("ic_total", "fpd_total"):
                if abs(differences[key]) > 2:
                    raise ValueError(f"FY{year} {key}: quarter sum differs from annual report")
            classification = {key: diff for key, diff in differences.items() if abs(diff) > 2}
            if classification:
                next(r for r in values if r["quarter"] == 4)["reconciliation_differences_thousand_usd"] = classification
    return quarters


def source_ref(filing):
    return {"url": filing["url"], "pdf_page": filing["pdf_page"], "published": filing["filed"],
            "label": f"{filing['form']} · {filing['period_end']} 종료"}


def build_documents(cache, tek, financials=None):
    rows = photronics_quarters(cache)
    dates = [r["period_end"] for r in rows]
    labels = {r["period_end"]: f"FY{r['fiscal_year']} Q{r['quarter']}" for r in rows}
    by_period = {(r["fiscal_year"], r["quarter"]): r["period_end"] for r in rows}
    comparisons = {}
    for r in rows:
        y, q = r["fiscal_year"], r["quarter"]
        comparisons[r["period_end"]] = {
            "year_ago": by_period.get((y-1, q)),
            "quarter_ago": by_period.get((y-1, 4) if q == 1 else (y, q-1)),
        }
    refs = {r["period_end"]: {**r["sources"][0], "supporting_sources": r["sources"],
            "calculation": "연간 − 9개월 누적" if r["derived"] else "공시된 3개월 매출"} for r in rows}
    docs = {}
    for prefix, title, scope in (
        ("ic", "반도체용", "고급은 28nm 이하, 범용은 28nm 초과 공정용 포토마스크입니다. 고급 제품 매출은 EUV 단독 매출이 아닙니다."),
        ("fpd", "디스플레이용", "고급은 AMOLED·LTPS·G10.5+ 제품군, 범용은 그 외 회사 분류입니다. 디스플레이 블랭크의 면적·판매 장수와는 다릅니다."),
    ):
        id_ = f"photronics_{prefix}_revenue"
        names = {"high": "고급 (High-end)", "main": "범용 (Mainstream)", "total": "합계"}
        docs[id_] = dict(id=id_, name=f"Photronics · {title} 포토마스크 매출 · 고급·범용",
            unit="백만 달러", frequency="quarterly", source="Photronics 공식 SEC 10-Q·10-K 제품별 매출",
            source_url=BASE + "/financial-information/sec-filings", updated=dates[-1], fetched=cache["checked"],
            span_gaps=False, series={name: [[r["period_end"], r["values"][prefix+"_"+key]/1000] for r in rows]
                                     for key, name in names.items()},
            default_series=[names["high"], names["main"]], quarterly_revenue_summary=True,
            period_labels=labels, comparison_dates=comparisons, point_sources=refs,
            description=f"완성 포토마스크의 제품별 분기 매출입니다. {scope}",
            note="미국 달러 명목 금액입니다. 회사 회계분기와 실제 종료일을 표시합니다. 달력 분기로 치환하지 않습니다. 블랭크마스크 매출이나 출하량이 아니며 외주 시장의 참고 지표입니다.",
            basis_details=[
                {"label": "Q1~Q3", "value": "분기보고서 매출 주석의 3개월 실적을 사용합니다. 천 달러 공표값을 백만 달러로 변환했습니다."},
                {"label": "Q4", "value": "같은 회계연도 연차보고서 금액에서 Q3 보고서의 9개월 누적값을 뺍니다. 분기 합계는 연간 실적과 대조합니다."},
                {"label": "비교 기준", "value": "YoY·QoQ는 종료일의 월·일이 아닌 회사 회계연도와 분기 번호로 대조합니다."},
                {"label": "확보 기간", "value": f"{labels[dates[0]]}~{labels[dates[-1]]} · {len(rows)}개 분기"},
            ])
        differences = {str(r["fiscal_year"]): {k: v for k, v in r.get("reconciliation_differences_thousand_usd", {}).items()
                       if k.startswith(prefix)} for r in rows}
        differences = {y: v for y, v in differences.items() if v}
        if differences:
            docs[id_]["reconciliation_differences_thousand_usd"] = differences
            docs[id_]["basis_details"].append({"label": "공표값 대조 차이", "value":
                "FY2022 고급·범용의 공시된 3개월 금액 합과 누적 금액에는 약 0.39백만 달러의 분류 차이가 있습니다. 원문 금액을 유지했습니다. 반도체·디스플레이 각각의 전체 분기 합계는 연간 실적과 천 달러 반올림 범위 안에서 일치합니다."})
    tek_rows = tek["quarters"]
    if len({r["date"] for r in tek_rows}) != len(tek_rows):
        raise ValueError("Duplicate Tekscend quarter")
    for r in tek_rows:
        if any(not 0 <= v <= 100 for v in r["node"] + r["application"]):
            raise ValueError("Invalid Tekscend percentage")
        if any(abs(sum(r[k])-100) > 1 for k in ("node", "application")):
            raise ValueError("Tekscend percentages do not sum to 100 within rounding")
    for metric, title, names, description in (
        ("node", "공정별", ["선단 (≤28nm)", "중간 (28~90nm)", "성숙 (>90nm)"],
         "포토마스크 제품 매출의 공정별 비중입니다. 회사의 선단 분류는 28nm 이하를 포함하며 EUV 단독 비중이 아닙니다."),
        ("application", "용도별", ["로직·기타", "메모리"],
         "포토마스크 제품 매출의 로직·기타 및 메모리 비중입니다. 구성비 변화만으로 해당 용도의 절대 매출 증감을 판단할 수 없습니다."),
    ):
        id_ = f"tekscend_{metric}_mix"
        docs[id_] = dict(id=id_, name=f"Tekscend · 포토마스크 {title} 매출 비중", unit="%",
            frequency="quarterly", manual=True, source="Tekscend 공식 IR · 제품 매출 구성",
            source_url="https://www.photomask.com/en/ir/results-briefing/", updated=tek_rows[-1]["date"],
            fetched=tek["checked"], span_gaps=False, quarter_labels=True, change_mode="none", zero_baseline=True,
            series={name: [[r["date"], r[metric][i]] for r in tek_rows] for i, name in enumerate(names)},
            default_series=names, description=description,
            note="옛 TOPPAN Photomask입니다. 달력 분기로 표시하며 2026 Q2는 회사 FY2026 Q1(4~6월)입니다. 비중은 회사가 반올림해 공표한 값으로 합계가 100%와 1%p 차이 날 수 있습니다. 금액 보기에서는 연결 매출에 비중을 적용한 근사 추정치를 별도로 표시합니다.",
            point_sources={r["date"]: {"url": r["source_url"], "pdf_page": r[metric+"_page"],
                "label": r["fiscal_period"]} for r in tek_rows},
            basis_details=[{"label": "자료 기준", "value": "2026년 6월 19일 정정된 연간 설명자료와 이후 분기 발표자료를 대조했습니다. 그래프의 연간 막대는 분기 시계열에 포함하지 않습니다."},
                {"label": "갱신", "value": "분기 발표 시 그래프의 숫자·분기 축을 확인해 스냅샷을 갱신합니다."}])
    add_tekscend_amounts(docs, tek, financials or json.loads(TEKSCEND_FINANCIALS.read_text(encoding="utf8")))
    return docs


def add_tekscend_amounts(docs, tek, financials):
    if financials.get("unit") != "million_jpy" or financials.get("scope") != "consolidated_photomask_business":
        raise ValueError("Unverified Tekscend financial unit or scope")
    rows = financials["quarters"]
    dates = [r["date"] for r in rows]
    if not rows or dates != sorted(set(dates)):
        raise ValueError("Tekscend financial quarters must be unique and sorted")
    for r in rows:
        date = dt.date.fromisoformat(r["date"])
        calendar_q = (date.month - 1) // 3 + 1
        fiscal_q = (calendar_q + 2) % 4 + 1
        fiscal_y = date.year - (date.month <= 3)
        if r["fiscal_period"] != f"FY{fiscal_y} Q{fiscal_q}" or r["revenue"] <= 0:
            raise ValueError("Invalid Tekscend fiscal mapping or revenue")
    for annual in financials["annual_totals"]:
        year_rows = [r for r in rows if r["fiscal_period"].startswith(f"FY{annual['fiscal_year']} ")]
        if len(year_rows) == 4:
            for key in ("revenue", "operating_profit"):
                # Public amounts are floored to JPY millions, so four quarters
                # may sum up to three million below the full-year observation.
                gap = annual[key] - sum(r[key] for r in year_rows)
                if not 0 <= gap <= 3:
                    raise ValueError("Tekscend quarter sum differs from annual report")
    by_date = {r["date"]: r for r in rows}
    mix_rows = tek["quarters"]
    if any(r["date"] not in by_date for r in mix_rows):
        raise ValueError("Missing same-quarter Tekscend revenue for mix estimate")
    refs = {r["date"]: {"url": r["source_url"], "pdf_page": r["pdf_page"],
            "label": r["fiscal_period"]} for r in rows}
    scope_note = "포토마스크 단일 사업의 연결 실적입니다. 포토마스크 제품 판매만의 별도 공시 금액과 동일하다고 단정하지 않습니다. 블랭크마스크 매출이 아닙니다."
    for key, title in (("revenue", "매출"), ("operating_profit", "영업이익")):
        id_ = f"tekscend_{key}"
        docs[id_] = dict(id=id_, name=f"Tekscend · 포토마스크 사업 {title} · 공시", unit="억 엔",
            frequency="quarterly", manual=True, quarter_labels=True, span_gaps=False,
            company_kpi=True, source="Tekscend 공식 IR · IFRS 연결 실적",
            source_url=refs[dates[-1]]["url"], updated=dates[-1], fetched=financials["checked"],
            series={title: [[r["date"], r[key] / 100] for r in rows]}, default_series=[title],
            point_sources=refs, description=scope_note,
            note="달력 분기 기준입니다. 2026 Q2는 회사 FY2026 Q1(4~6월)입니다. 백만 엔 공시값을 억 엔으로 변환했으며, 분기값 합과 연간값에는 백만 엔 미만 절사 차이가 있습니다.",
            basis_details=[{"label": "공시 범위", "value": "회사는 포토마스크 사업을 단일 부문으로 보고합니다. 회사 전체 연결 실적을 해당 사업의 실적으로 표시했습니다."},
                {"label": "원문", "value": "2026년 6월 19일 정정 연간 자료의 IFRS 분기표(PDF p.26)와 FY2026 Q1 자료(PDF p.5)를 사용했습니다. 비IFRS 조정 이익이 아닙니다."}])
        docs[id_]["quarterly_revenue_summary" if key == "revenue" else "quarterly_profit_summary"] = True
    caveat = "연결 매출 × 공표 비중으로 계산한 근사 추정치입니다. 회사가 공시한 공정별·용도별 매출 금액이 아닙니다. 비중의 실제 분모는 포토마스크 제품 매출이며, 해당 제품 매출 금액을 별도로 확인하지 못해 단일 포토마스크 사업의 연결 매출을 대용했습니다."
    for metric, title in (("node", "공정별"), ("application", "용도별")):
        doc = docs[f"tekscend_{metric}_mix"]
        amount_refs = {}
        for r in mix_rows:
            ref = doc["point_sources"][r["date"]]
            amount_refs[r["date"]] = {**refs[r["date"]], "source_separator": " × ",
                "supporting_sources": [refs[r["date"]], ref], "calculation": "연결 매출 × 공표 비중"}
        amounts = {name: [[r["date"], round(by_date[r["date"]]["revenue"] * r[metric][i] / 10000, 2)]
                          for r in mix_rows] for i, name in enumerate(doc["series"])}
        ratio_view = {key: doc[key] for key in ("name", "unit", "series", "description", "note", "point_sources", "basis_details")}
        ratio_view.update(label="비중 (%)", quarterly_revenue_summary=False, point_annotations={})
        doc["series_views"] = {
            "amount": dict(label="금액 (근사 추정)", name=f"Tekscend · 포토마스크 {title} 매출 · 근사 추정",
                unit="억 엔", series=amounts, company_kpi=True, quarterly_revenue_summary=True,
                description=caveat, point_sources=amount_refs,
                note="원래 비중을 재정규화하지 않았습니다. 정수 비중의 반올림 오차와 대용 분모의 차이가 있으며, 합계가 연결 매출과 다를 수 있습니다. 선단 공정은 EUV 단독이 아닙니다. 달력 2026 Q2=회사 FY2026 Q1입니다.",
                point_annotations={r["date"]: "연결 매출을 분모로 대용한 근사 추정" for r in mix_rows},
                basis_details=[{"label": "금액 산식", "value": "공시 연결 매출(백만 엔) × 비중(%) ÷ 10,000 = 억 엔. 같은 분기의 자료끼리 계산하며 비중 또는 매출이 없는 분기는 추정하지 않습니다."},
                    {"label": "분모 차이", "value": caveat},
                    {"label": "공시 비중", "value": "비중 (%) 버튼으로 회사가 발표한 원래 구성비를 볼 수 있습니다. 표의 원문 두 개는 각각 연결 매출과 구성비 자료입니다."}]),
            "ratio": ratio_view,
        }
        doc["default_view"] = "amount"


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backfill", action="store_true")
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    cache = json.loads(CACHE.read_text(encoding="utf8")) if CACHE.exists() else {"filings": []}
    if not args.offline:
        known = {f["url"]: f for f in cache["filings"]}
        for filing in list_filings(args.backfill or not known):
            if filing["url"] in known:
                continue
            with read_pdf(filing["url"]) as pdf:
                known[filing["url"]] = parse_photronics(pdf, filing)
            print(f"Parsed {filing['filed']} {filing['form']}")
        cache = {"checked": dt.date.today().isoformat(), "filings": sorted(known.values(), key=lambda f: f["filed"])}
    tek = json.loads(TEKSCEND.read_text(encoding="utf8"))
    docs = build_documents(cache, tek)
    # Validate everything before replacing either the archive or chart data.
    write_json(CACHE, cache)
    for id_, doc in docs.items():
        write_json(OUT / f"{id_}.json", doc)
    print(f"Mask patterning: {len(docs)} charts, {len(photronics_quarters(cache))} Photronics quarters")


if __name__ == "__main__":
    run()
