"""Official JEOL Data Book and Mycronic report archive; reviewed NuFlare/units.

--backfill loads four eight-quarter tables; --offline rebuilds cached facts.
No credentials. Validate all documents before replacing the cache or charts.
"""
import argparse
import calendar
import datetime as dt
import io
import json
import math
import posixpath
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from urllib.parse import urljoin

import pymupdf
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data/_mask_equipment/facts.json"
MANUAL = ROOT / "manual/mask_equipment.json"
JEOL = "https://www.jeol.com/ir/data_book/"
MYCRONIC = "https://www.mycronic.com/investors/financial-reports/"
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def get(url):
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    return r


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=1) + "\n", encoding="utf8")


def end_date(year, quarter=None):
    # Japanese FY is its April start year; calendar dates are never fabricated.
    if quarter is None:
        return f"{year+1}-03-31"
    month = {1: 6, 2: 9, 3: 12, 4: 3}[quarter]
    return f"{year+(quarter==4)}-{month:02}-{calendar.monthrange(year+(quarter==4), month)[1]}"


def read_xlsx(data):
    """Read cached values, not formulas; resolve workbook relationships by name."""
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        strings = ["".join(t.text or "" for t in x.findall(".//s:t", NS))
                   for x in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("s:si", NS)]
        rels = {r.get("Id"): r.get("Target") for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
        sheets = {}
        for sheet in ET.fromstring(z.read("xl/workbook.xml")).findall("s:sheets/s:sheet", NS):
            target = rels[sheet.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")]
            path = target.lstrip("/") if target.startswith("/") else posixpath.normpath("xl/"+target)
            cells = {}
            for c in ET.fromstring(z.read(path)).findall("s:sheetData/s:row/s:c", NS):
                v = c.find("s:v", NS)
                if v is not None and v.text:
                    cells[c.get("r")] = strings[int(v.text)] if c.get("t") == "s" else v.text
            sheets[sheet.get("name")] = cells
        return sheets


def number(value):
    if value is None or value.strip() in ("", "-", "—"):
        return None
    v = float(value.replace(",", "").rstrip("%"))
    if not math.isfinite(v):
        raise ValueError("Nonfinite source value")
    return int(v) if v.is_integer() else v


def columns(cells, year_row, period_row=None):
    cols = sorted({re.match(r"[A-Z]+", c)[0] for c in cells}, key=lambda c: (len(c), c))
    year = None
    for col in cols:
        header = cells.get(f"{col}{year_row}", "")
        if re.fullmatch(r"FY\d{4}", header):
            year = int(header[2:])
        if year is not None:
            yield col, year, cells.get(f"{col}{period_row}") if period_row else "FY"


def extract_jeol(data, url):
    sheets = read_xlsx(data)
    result = {"url": url, "quarters": [], "models": [], "model_years": [], "annual": []}
    for sheet_name, rows, target in (("2-1", {"sales": 9, "profit": 10}, "quarters"),
                                     ("4-2", {"mb_orders": 6, "mb_sales": 7, "sb_orders": 8, "sb_sales": 9}, "models")):
        cells = sheets[sheet_name]
        if not any("Unit:" in v and ("Units" if target == "models" else "Millions of yen") in v for v in cells.values()):
            raise ValueError("JEOL source unit changed")
        if "Industrial" not in cells.get("A1", "") and sheet_name == "4-2":
            raise ValueError("JEOL model sheet changed")
        if target == "quarters" and "Industrial Equipment" not in cells.get("A9", ""):
            raise ValueError("JEOL industrial segment row changed")
        for col, year, period in columns(cells, 4, 5):
            if period not in ("1Q", "2Q", "3Q", "4Q", "FY"):
                continue
            values = {key: number(cells.get(f"{col}{row}")) for key, row in rows.items()}
            if all(v is None for v in values.values()):
                continue
            row = dict(date=end_date(year, int(period[0]) if period != "FY" else None),
                       fiscal_year=year, period=f"FY{year}"+(f" Q{period[0]}" if period != "FY" else ""),
                       sheet=sheet_name, url=url, cells={k: f"{col}{r}" for k, r in rows.items()}, **values)
            if period == "FY":
                if target == "models":
                    result["model_years"].append(row)
                continue
            row["quarter"] = int(period[0])
            result[target].append(row)
        # Only compare complete years; blank cells are not zero.
        for col, year, period in columns(cells, 4, 5):
            if period != "FY":
                continue
            quarters = [r for r in result[target] if r["fiscal_year"] == year]
            for key, source_row in rows.items():
                annual = number(cells.get(f"{col}{source_row}"))
                if annual is not None and len(quarters) == 4 and all(r[key] is not None for r in quarters):
                    if abs(sum(r[key] for r in quarters)-annual) > (0 if target == "models" else 3):
                        raise ValueError(f"JEOL {year} {key} annual reconciliation failed")
    cells = sheets["12"]
    if "Orders Received" not in cells.get("A1", ""):
        raise ValueError("JEOL annual orders sheet changed")
    for col, year, _ in columns(cells, 5):
        orders, backlog = number(cells.get(col+"7")), number(cells.get(col+"23"))
        if orders is not None and backlog is not None:
            result["annual"].append(dict(date=end_date(year), period=f"FY{year}", orders=orders,
                                         backlog=backlog, sheet="12", url=url, cells={"orders": col+"7", "backlog": col+"23"}))
    if not result["quarters"] or not result["models"] or not result["annual"]:
        raise ValueError("Incomplete JEOL workbook")
    return result


def extract_mycronic(data, url):
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        if not any("SEK million" in p.get_text() for p in doc):
            raise ValueError("Mycronic source unit unverified")
        for i, page in enumerate(doc):
            text = page.get_text()
            if "Quarterly data" not in text or "Pattern Generators" not in text:
                continue
            headers = re.findall(r"Q([1-4])\s+(\d{2})\*?", text.split("Order", 1)[0])
            if len(headers) != 8:
                raise ValueError("Unexpected Mycronic quarterly header")
            metrics = {}
            for key, label in (("orders", "Order intake"), ("backlog", "Order Backlog"),
                               ("sales", "Net Sales"), ("gross_margin", "Gross Margin"),
                               ("profit", "Of which EBIT")):
                # Pre-2021 layout puts the division on the same line as the metric.
                pattern = label + (r"\s+Pattern Generators" if key == "profit" else r"(?:\s*\n| )Pattern Generators")
                match = re.search(pattern, text, re.I)
                if not match:
                    raise ValueError(f"Mycronic quarterly {key} missing")
                tail = text[match.end():].strip().splitlines()[:8]
                if len(tail) != 8 or any(not re.fullmatch(r"-?\d[\d,]*(?:\.\d+)?%?", v.strip()) for v in tail):
                    raise ValueError(f"Unexpected Mycronic {key} values")
                metrics[key] = [number(v.strip()) for v in tail]
            rows = []
            for j, (q, y) in enumerate(headers):
                year, quarter = 2000+int(y), int(q)
                month = quarter*3
                date = f"{year}-{month:02}-{calendar.monthrange(year, month)[1]}"
                rows.append(dict(date=date, url=url, pdf_page=i+1, **{k: v[j] for k, v in metrics.items()}))
            return rows
    raise ValueError("Mycronic eight-quarter table not found")


def collect(cache, backfill=False):
    soup = BeautifulSoup(get(JEOL).text, "html.parser")
    xlsx = next((urljoin(JEOL, a["href"]) for a in soup.select("a[href]") if a["href"].endswith(".xlsx")), None)
    if not xlsx:
        raise ValueError("JEOL official workbook not found")
    jeol = extract_jeol(get(xlsx).content, xlsx)
    previous = cache.get("jeol", {})
    for key in ("quarters", "models", "model_years", "annual"):
        known = {r["date"]: {"url": previous.get("url"), **r} for r in previous.get(key, [])}
        known.update({r["date"]: r for r in jeol[key]})
        jeol[key] = sorted(known.values(), key=lambda r: r["date"])
    html = get(MYCRONIC).text
    token = re.search(r'token:\s*[\"\']([a-f0-9-]{36})', html)
    if not token:
        raise ValueError("Mycronic public archive identifier missing")
    archive = BeautifulSoup(get("https://widget.datablocks.se/api/rose/widgets/archive?token="+token[1]+"&lang=en").text, "html.parser")
    reports = []
    for tr in archive.select("tr"):
        title, a = tr.select_one(".mfn-archive-event-title"), tr.select_one(".mfn-archive-item-type-report-pdf a")
        if title and a and re.search(r"(?:Interim Report|Year-end Report) Q[1-4] \d{4}", title.text):
            reports.append((title.text.strip(), a["href"]))
    if not reports:
        raise ValueError("Mycronic official reports missing")
    selected = reports[:1]
    if backfill or not cache.get("mycronic"):
        selected += [r for r in reports if r[0] in {f"Interim Report Q2 {y}" for y in (2020, 2022, 2024, 2026)} and r not in selected]
    fact_keys = ("date", "url", "pdf_page", "orders", "backlog", "sales", "gross_margin", "profit")
    known = {r["date"]: {k: r[k] for k in fact_keys} for r in cache.get("mycronic", [])}
    # Newer published tables override older values (including restatements).
    for title, url in reversed(selected):
        for row in extract_mycronic(get(url).content, url):
            known[row["date"]] = row
        print("Parsed", title)
    return dict(checked=dt.date.today().isoformat(), jeol=jeol, mycronic=sorted(known.values(), key=lambda r: r["date"]))


def build_documents(cache, manual):
    docs = {}

    def chart(id_, name, unit, rows, fields, source, url, scope, **options):
        if not rows:
            raise ValueError(f"Empty {id_}")
        dates = [r["date"] for r in rows]
        if dates != sorted(set(dates)):
            raise ValueError(f"Unsorted or duplicate {id_}")
        refs = {r["date"]: dict(url=r.get("url", url), label=r.get("period", r["date"]),
                 **({"pdf_page": r["pdf_page"]} if "pdf_page" in r else {})) for r in rows}
        for r in rows:
            if "sheet" in r:
                refs[r["date"]]["label"] += f" · Excel {r['sheet']} · " + ", ".join(r["cells"].values())
        doc = dict(id=id_, name=name, unit=unit, frequency="quarterly", quarter_labels=True,
                   span_gaps=False, source=source, source_url=url, fetched=cache["checked"],
                   updated=dates[-1], description=scope, point_sources=refs,
                   series={label: [[r["date"], round(r[key]*scale, 4) if r.get(key) is not None else None]
                                  for r in rows] for key, label, scale in fields},
                   default_series=[f[1] for f in fields], **options)
        docs[id_] = doc
        return doc

    j = cache["jeol"]
    js = "JEOL 공식 IR Data Book · Excel 원표"
    jscope = "산업기기 사업부 실적입니다. 마스크 라이터 외에 스폿빔 직접묘화 장비·기타 산업 장비를 포함하므로 마스크 장비 단독 매출이 아닙니다."
    jnote = "FY는 4월 시작 연도입니다. FY2025 Q4는 2026년 1~3월, FY2026 Q1은 2026년 4~6월입니다. Excel에 공시된 단일 분기값을 사용하며 백만 엔을 억 엔으로 변환했습니다."
    for key, label in (("sales", "매출"), ("profit", "영업이익")):
        chart(f"jeol_industrial_{key}", f"JEOL · 산업기기 {label} · 분기", "억 엔", j["quarters"],
              [(key, label, .01)], js, j["url"], jscope, note=jnote,
              period_labels={r["date"]: r["period"] for r in j["quarters"]},
              **{"quarterly_revenue_summary" if key == "sales" else "quarterly_profit_summary": True})
    for prefix, label, explanation in (
        ("mb", "MBMW 플랫폼", "JEOL의 멀티빔 마스크 라이터 플랫폼 수주·매출인식 대수입니다. IMS 완성 장비의 판매 대수나 전체 EUV 마스크 장비 시장 대수가 아닙니다."),
        ("sb", "싱글빔 마스크 라이터", "JEOL 3050/3200 시리즈의 수주·매출인식 대수입니다. 웨이퍼 직접묘화용 스폿빔 장비를 포함하지 않습니다.")):
        fields = [(prefix+"_orders", "수주", 1), (prefix+"_sales", "매출인식", 1)]
        rows = [r for r in j["models"] if r[prefix+"_orders"] is not None or r[prefix+"_sales"] is not None]
        annual = [r for r in j["model_years"] if r[prefix+"_orders"] is not None or r[prefix+"_sales"] is not None]
        doc = chart(f"jeol_{prefix}_units", f"JEOL · {label} · 수주·매출인식 대수", "대", rows, fields,
                    js, j["url"], explanation, zero_baseline=True, change_mode="none",
                    note="FY는 4월 시작 연도입니다. FY2026 Q1은 2026년 4~6월입니다. 단위는 대이며 공시된 단일 분기값을 사용합니다. 숫자 0은 실제 공시값이고 미공시 기간을 0으로 채우지 않았습니다.",
                    period_labels={r["date"]: r["period"] for r in rows})
        annual_doc = chart("_annual", f"JEOL · {label} · 연간 대수", "대", annual, fields, js, j["url"],
                           explanation, change_mode="none", zero_baseline=True, note="연간 실적이며 FY는 4월 시작 연도입니다. 공시 없는 기간은 채우지 않습니다.",
                           period_labels={r["date"]: r["period"] for r in annual})
        annual_doc.update(frequency="yearly", quarter_labels=False, full_range=True)
        doc["series_views"] = {"quarter": {**doc, "label": "분기"}, "annual": {**annual_doc, "id": doc["id"], "label": "연간·과거"}}
        doc["default_view"] = "quarter"
        del docs["_annual"]
    for key, label in (("orders", "수주액"), ("backlog", "수주잔고")):
        doc = chart(f"jeol_industrial_{key}", f"JEOL · 산업기기 {label} · 연간", "억 엔", j["annual"],
                    [(key, label, .01)], js, j["url"], jscope, full_range=True, change_mode="none",
                    note="산업기기 사업부의 연간 수주액 또는 3월 말 수주잔고입니다. 마스크 라이터 단독 수치가 아닙니다. FY는 4월 시작 연도입니다.",
                    period_labels={r["date"]: r["period"] for r in j["annual"]})
        doc.update(frequency="yearly", quarter_labels=False)

    n = manual["nuflare"]
    for key, label in (("sales", "매출"), ("profit", "영업이익")):
        rows = [{**r, "date": end_date(r["fiscal_year"]), "period": f"FY{r['fiscal_year']}"} for r in n["years"]]
        doc = chart(f"nuflare_{key}", f"NuFlare · 회사 전체 {label} · 연간", "억 엔", rows, [(key, label, 1)],
                    "NuFlare 공식 업적 추이", n[key+"_url"],
                    "회사 전체 연간 실적입니다. 전자빔 마스크 묘화·마스크 검사·에피택셜 성장 장비 사업을 포함하며 마스크 라이터 단독 매출이 아닙니다.",
                    manual=True, full_range=True, change_mode="none", note="공식 그래프의 정수 억 엔 표기를 그대로 옮겼습니다. FY2025는 2026년 3월 종료 연도입니다. 상장폐지 이후 동일 범위의 분기 실적을 확인하지 못해 연간만 표시합니다. 새 연간 그래프 발표 시 검토해 갱신합니다.",
                    period_labels={r["date"]: r["period"] for r in rows})
        doc.update(frequency="yearly", quarter_labels=False, fetched=n["checked"])

    rows = [dict(r) for r in cache["mycronic"]]
    scope = "Pattern Generators 사업부 실적입니다. 디스플레이·반도체용 레이저 마스크 라이터와 서비스 등을 포함합니다. 전자빔 EUV 장비 단독 수치가 아닙니다."
    source = "Mycronic 공식 분기보고서 · 8개 분기 원표"
    note = "공시된 단일 분기의 명목 SEK 금액입니다. 환율·제품 믹스와 인수 효과가 포함됩니다. 2026 Q2에는 Cowin DST 매출 26백만 SEK와 비반복 맞춤형 SLX 수주가 포함되어 전년·장비 대수와 단순 비교에 주의가 필요합니다."
    specs = [("orders_sales", "수주·매출", "백만 SEK", [("orders", "수주액", 1), ("sales", "매출", 1)]),
             ("backlog", "수주잔고", "백만 SEK", [("backlog", "수주잔고", 1)]),
             ("profit", "EBIT", "백만 SEK", [("profit", "EBIT", 1)]),
             ("margins", "이익률", "%", [("gross_margin", "매출총이익률", 1), ("ebit_margin", "EBIT 이익률", 1)]),
             ("book_to_bill", "수주/매출 · 분기·TTM", "배", [("book_to_bill", "분기 수주/매출", 1), ("ttm_book_to_bill", "TTM 수주/매출", 1)])]
    for i, row in enumerate(rows):
        row = row.copy()
        row["ebit_margin"] = row["profit"] / row["sales"] * 100
        row["book_to_bill"] = row["orders"] / row["sales"]
        window = rows[max(0, i-3):i+1]
        serials = [int(r["date"][:4])*4+(int(r["date"][5:7])-1)//3 for r in window]
        row["ttm_book_to_bill"] = (sum(r["orders"] for r in window)/sum(r["sales"] for r in window)
                                    if len(window) == 4 and serials == list(range(serials[0], serials[0]+4)) else None)
        rows[i] = row
    for id_, label, unit, fields in specs:
        doc = chart("mycronic_"+id_, "Mycronic · Pattern Generators · "+label, unit, rows, fields,
                    source, rows[-1]["url"], scope, note=note, change_mode="none")
        if id_ == "book_to_bill":
            doc["description"] = "수주액 ÷ 매출액입니다. TTM은 연속된 최근 4개 분기의 수주 합 ÷ 매출 합으로 계산합니다. 1배 이상은 해당 기간 수주액이 매출보다 크다는 의미이며 수주잔고의 실제 증감과 같지는 않습니다. " + scope
            doc["default_series"] = ["TTM 수주/매출", "분기 수주/매출"]
            doc["basis_details"] = [{"label": "TTM 원문", "value": "각 관측값은 표의 해당 분기와 직전 3개 분기 원문에 근거합니다. 초기 3개 분기 또는 연속 분기가 없는 경우 TTM은 비워 둡니다."}]
            doc["basis_details"].append({"label": "반올림 차이", "value": "정수 백만 SEK 분기값의 합을 사용합니다. 2026 Q2 TTM 매출 합은 3,258백만 SEK로, 회사가 별도로 공표한 TTM 3,257백만 SEK와 1백만 SEK 차이가 있습니다. 분기 원표를 유지하므로 비율에도 미세한 차이가 있습니다."})
            for i, row in enumerate(rows):
                if row["ttm_book_to_bill"] is None:
                    continue
                refs = {}
                for r in rows[i-3:i+1]:
                    refs[(r["url"], r["pdf_page"])] = dict(url=r["url"], pdf_page=r["pdf_page"], label="분기 원표")
                doc["point_sources"][row["date"]]["supporting_sources"] = list(refs.values())
                doc["point_sources"][row["date"]]["source_separator"] = " + "
    units = manual["mycronic_units"]
    doc = chart("mycronic_systems", "Mycronic · 마스크 라이터 · 납품·수주잔고 대수", "대", units["quarters"],
                [("delivered", "분기 납품", 1), ("backlog", "기말 수주잔고", 1)], "Mycronic 공식 분기보고서 · 본문 검토값", MYCRONIC,
                "레이저 마스크 라이터의 분기 납품 대수와 기말 미납품 장비 대수입니다. 납품은 기간 흐름, 잔고는 기말 누적량으로 서로 더하지 않습니다.",
                manual=True, change_mode="none", zero_baseline=True,
                note="2025 Q3·Q4의 qualification SLX 매출 인식은 당기 신규 납품으로 세지 않았습니다. 장비 대수만으로 매출을 역산하지 않습니다. 이 대수 자료는 분기 본문 확인 후 갱신하며 금액 차트의 자동 갱신과 별개입니다.",
                basis_details=[{"label": "예정 납품 · 2026 Q2 발표 기준", "value": "2026 Q3: 5대(1 FPS 6100 Evo·4 SLX), Q4: 3대(1 Prexision Lite 8 Evo·1 Prexision MMS·1 SLX), 2027 Q1: 3대(Prexision 8 Evo), Q2: 1대(SLX), 2028: 1대(맞춤형 SLX·분기 미공개). 합계 13대이며 확정 실적이 아닌 회사 일정입니다."}])
    doc["fetched"] = units["checked"]
    return docs


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--backfill", action="store_true")
    args = parser.parse_args()
    cache = json.loads(CACHE.read_text(encoding="utf8")) if CACHE.exists() else {}
    if not args.offline:
        cache = collect(cache, args.backfill)
    manual = json.loads(MANUAL.read_text(encoding="utf8"))
    docs = build_documents(cache, manual)
    write_json(CACHE, cache)
    for id_, doc in docs.items():
        write_json(ROOT / "data/semicon" / (id_+".json"), doc)
    print(f"Mask equipment: {len(docs)} charts; JEOL {len(cache['jeol']['quarters'])} and Mycronic {len(cache['mycronic'])} quarters")


if __name__ == "__main__":
    run()
