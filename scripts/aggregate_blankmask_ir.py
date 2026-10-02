"""공식 IR에서 확인한 일본 3사 관측값을 대시보드 카드로 변환한다.

수치와 PDF 페이지는 manual/blankmask_japan_ir.json에 보관한다.
단독 분기 매출의 추정, 성장률의 금액 역산, 연간 금액의 분기 배분은 하지 않는다.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "manual" / "blankmask_japan_ir.json"
OUT = ROOT / "data" / "semicon"
QEND = {1: "03-31", 2: "06-30", 3: "09-30", 4: "12-31"}
METRICS = {
    ("HOYA", "it_revenue"), ("HOYA", "lsi_yoy"),
    ("AGC", "electronic_materials_revenue"), ("AGC", "euv_blanks_annual_revenue"),
    ("Shin-Etsu", "electronics_revenue"),
}


def period_date(period):
    if re.fullmatch(r"\d{4}Q[1-4]", period):
        return f"{period[:4]}-{QEND[int(period[-1])]}"
    if re.fullmatch(r"\d{4}", period):
        return f"{period}-12-31"
    raise ValueError(f"Invalid period: {period}")


def validate(raw):
    seen = set()
    for r in raw["records"]:
        key = (r["company"], r["metric"], r["period"])
        if key in seen:
            raise ValueError(f"Duplicate observation: {key}")
        seen.add(key)
        assert key[:2] in METRICS, key
        assert r["status"] == "actual", key
        assert period_date(r["period"]) <= raw["checked"], key
        assert r["source_url"].startswith("https://"), key
        assert isinstance(r["pdf_page"], int) and r["pdf_page"] > 0, key
        assert isinstance(r["value"], (int, float)), key
        if r["metric"] == "lsi_yoy":
            assert r["unit"] == "percent", key
        else:
            assert r["unit"] == "billion_jpy" and r["value"] >= 0, key
        assert ("Q" not in r["period"]) == (r["metric"] == "euv_blanks_annual_revenue"), key

    # 独立した会社公表の通期額との照合。丸め誤差だけを許容。
    for check in raw["annual_checks"]:
        rows = [r for r in raw["records"] if r["company"] == check["company"] and r["metric"] == check["metric"]]
        if "calendar_year" in check:
            rows = [r for r in rows if r["period"].startswith(str(check["calendar_year"]))]
        else:
            fy = check["fiscal_year_start"]
            periods = {f"{fy}Q2", f"{fy}Q3", f"{fy}Q4", f"{fy+1}Q1"}
            rows = [r for r in rows if r["period"] in periods]
        assert len(rows) == 4, check
        total = sum(r["value"] for r in rows)
        assert abs(total - check["value_billion_jpy"]) <= check["tolerance"] + 1e-8, (check, total)


def build_docs(raw):
    validate(raw)
    def rows(company, metric):
        return sorted([r for r in raw["records"] if r["company"] == company and r["metric"] == metric], key=lambda r:r["period"])

    common = {"manual": True, "fetched": raw["checked"], "span_gaps": False}
    docs = {}
    def card(id_, name, unit, frequency, source, url, data, description, note, **extra):
        last = max(period_date(r["period"]) for r in data)
        docs[id_] = dict(id=id_, name=name, unit=unit, frequency=frequency,
            source=source, source_url=url, updated=last, **common,
            description=description, note=note,
            point_sources={period_date(r["period"]): {"url":r["source_url"], "pdf_page":r["pdf_page"]} for r in data}, **extra)

    segments = [
        ("HOYA", "it_revenue", "hoya_it_revenue", "HOYA · Information Technology 분기 매출", "IT 사업부 매출",
         "https://www.hoya.com/en/investor/kessan/",
         "반도체 블랭크마스크(LSI) 외에 FPD 포토마스크·HDD 유리기판·광학 제품을 포함합니다."),
        ("AGC", "electronic_materials_revenue", "agc_materials_revenue", "AGC · 전자부재 분기 매출", "전자부재 매출",
         "https://www.agc.com/en/ir/pdf/data_all.pdf",
         "EUV 블랭크스 외에 광전자 소재·CMP 슬러리·합성 석영·SiC 제품 등을 포함합니다. Display 사업은 제외합니다."),
        ("Shin-Etsu", "electronics_revenue", "shinetsu_materials_revenue", "신에츠화학 · 전자재료 분기 매출", "전자재료 매출",
         "https://www.shinetsu.co.jp/en/ir/ir-data/ir-results/",
         "블랭크마스크 외에 실리콘 웨이퍼·포토레지스트·희토류 자석 등을 포함합니다. 2021년은 회사가 현재 사업부 기준으로 재작성한 비교 수치입니다."),
    ]
    for company,metric,id_,name,label,url,scope in segments:
        data=rows(company,metric)
        card(id_,name,"억 엔","quarterly",f"{company} 공식 분기 IR",url,data,
             f"상위 사업부 참고 지표 · {scope}",
             "블랭크마스크 단독 매출액이 아닙니다. 회사별 포함 제품이 달라 매출 합계나 비중을 블랭크마스크 시장으로 해석할 수 없습니다. 실제 3개월 매출이며 누적 실적이 아닙니다. 달력 분기 기준, 엔화 명목 금액입니다. 회사 공표값의 반올림 차이가 있습니다. 분기 발표 때 IR을 확인해 수기 갱신합니다.",
             series={label:[[period_date(r["period"]),round(r["value"]*10,3)] for r in data]},
             default_series=[label],quarter_labels=True,quarterly_revenue_summary=True)

    data=rows("HOYA","lsi_yoy")
    card("hoya_blank_growth","HOYA · LSI 블랭크마스크 매출 성장률","%","quarterly",
         "HOYA 공식 분기 실적 설명자료 · LSI 제품군","https://www.hoya.com/en/investor/kessan/",data,
         "반도체용 EUV·DUV 블랭크마스크 제품군의 전년 동기 대비 매출 성장률입니다. 금액 추이가 아닌 수요·매출 성장 추이입니다.",
         "명목 엔화 기준과 환율 영향을 제거한 CC(Constant Currency) 기준을 구분합니다. 매출 절대액은 확인되지 않아 성장률로 금액을 역산하지 않았습니다. FPD 제품군은 제외합니다. 달력 분기로 통일했으므로 2026 Q2는 회사 표기의 FY26 Q1에 해당합니다.",
         series={"명목 YoY":[[period_date(r["period"]),r["value"]] for r in data],
                 "환율 제외 YoY (CC)":[[period_date(r["period"]),r["constant_currency_yoy"]] for r in data]},
         default_series=["명목 YoY","환율 제외 YoY (CC)"],quarter_labels=True,change_mode="none")

    data=rows("AGC","euv_blanks_annual_revenue")
    card("agc_euv_annual_revenue","AGC · EUV 블랭크스 연간 매출 공개값","억 엔","yearly",
         "AGC FY2024 실적 발표 · p.45",data[0]["source_url"]+"#page=45",data,
         "AGC가 공식 IR에서 공개한 2024년 EUV 블랭크스 매출 400억 엔입니다. 2026년 6월 설명회에서도 같은 금액을 재확인했습니다.",
         "공개된 실적 한 점만 표시합니다. 연간 금액을 4로 나눠 분기 매출을 만들지 않았습니다. 2025년은 감소했다는 설명만 확인했으며 금액은 미확인입니다. EUV 제품만의 금액으로 DUV·디스플레이를 포함한 전체 블랭크마스크 시장과 다릅니다. 회사가 제시한 반올림된 금액입니다.",
         series={"EUV 블랭크스 연간 매출":[[period_date(r["period"]),r["value"]*10] for r in data]},
         default_series=["EUV 블랭크스 연간 매출"],chart_type="bar",full_range=True,zero_baseline=True,change_mode="none")

    docs["blankmask_ir_disclosure"] = dict(id="blankmask_ir_disclosure", name="일본 3사 · 블랭크마스크 매출 공개 범위",
        updated="2026-06-30",**common,
        description="블랭크마스크 총시장을 매출액으로 추적하기 위해 3사 공식 IR을 확인했습니다. 현재는 단독 분기 매출액을 3사 모두 확보하지 못해 총시장·시장점유율을 계산하지 않습니다.",
        rows=[
            dict(company="HOYA",quarterly="단독 분기 금액 미확인",direct="LSI 제품군 분기 매출 YoY · 2023 Q2~2026 Q2",reference="Information Technology 사업부 매출",source_url=segments[0][5]),
            dict(company="AGC",quarterly="단독 분기 금액 미확인",direct="2024년 EUV 블랭크스 연간 매출 400억 엔",reference="전자부재(Electronic Materials) 매출",source_url="https://www.agc.com/en/ir/library/briefing/pdf/2025_0207e_1.pdf#page=45"),
            dict(company="신에츠화학",quarterly="단독 분기 금액 미확인",direct="블랭크마스크 단독 금액·정량 성장률 미확인",reference="전자재료(Electronics Materials) 사업부 매출",source_url=segments[2][5]),
        ],
        note=f"공식 자료 확인일 {raw['checked']} · 3사 사업부 합계는 블랭크마스크 총시장이 아닙니다. 사업부 범위가 서로 다르고 다른 제품의 매출도 포함됩니다. 3사의 단독 금액을 확보하더라도 다른 공급사와 제품 범위를 확인해야 글로벌 총시장으로 볼 수 있습니다.")
    return docs


def run():
    raw=json.loads(INPUT.read_text(encoding="utf8"))
    docs=build_docs(raw)
    OUT.mkdir(parents=True,exist_ok=True)
    for id_,doc in docs.items():
        (OUT/f"{id_}.json").write_text(json.dumps(doc,ensure_ascii=False,indent=1)+"\n",encoding="utf8")
    print(f"일본 3사 IR: {len(raw['records'])}개 실제 관측값 · {len(docs)}개 카드 · 확인일 {raw['checked']}")


if __name__=="__main__":
    run()
