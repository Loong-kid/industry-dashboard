# -*- coding: utf-8 -*-
"""미국 LNG 프로젝트·FLNG 원장 → 기업별 용량 막대 자료 (천연가스 탭 LNG).

입력: manual/lng_us_projects.csv, manual/flng_fleet.csv — 공시·보도를 대조해 손으로 관리한다.
EIA 워크북은 2025-06-30 뒤로 멈췄고 GEM 터미널 원장은 2025-09 판이라, 그 뒤 FID·가동은 여기에서 고친다.
상태를 고치면 REVIEWED도 함께 고치고 이 스크립트를 다시 돌린다.

    python scripts/build_lng_capacity.py
"""
import csv
import datetime as dt
import json
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
US_SRC = ROOT / "manual" / "lng_us_projects.csv"
FLNG_SRC = ROOT / "manual" / "flng_fleet.csv"
OUT_DIR = ROOT / "data" / "natgas"

REVIEWED = "2026-11-04"
STATUSES = {
    "operating": "가동",
    "commissioning": "시운전",
    "construction": "건설중 (FID 완료)",
    "prefid": "FID 전",
    "suspended": "보류·중단",
}
FLNG_STATUS = {"가동중": "operating", "건조중": "construction", "개조중": "construction", "FID 전": "prefid", "보류": "suspended"}
FLNG_LABELS = {**STATUSES, "construction": "건조·개조중 (FID 완료)"}


def check_url(url, where):
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError(f"{where}: 출처 주소가 https가 아니다: {url!r}")


def read_us():
    rows = []
    with US_SRC.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            where = f"{r['company']} / {r['project']}"
            if r["status"] not in STATUSES:
                raise ValueError(f"{where}: 모르는 상태 {r['status']!r}")
            mtpa = float(r["mtpa"])
            if mtpa <= 0:
                raise ValueError(f"{where}: 용량이 0 이하")
            check_url(r["source_url"], where)
            rows.append({"company": r["company"], "project": r["project"], "unit": r["unit"], "mtpa": mtpa,
                         "status": r["status"], "start": r["start"], "fid": r["fid"], "note": r["note"],
                         "source": r["source"], "source_url": r["source_url"]})
    return rows


def read_flng():
    rows = []
    with FLNG_SRC.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            where = r["vessel"]
            if r["status"] not in FLNG_STATUS:
                raise ValueError(f"{where}: 모르는 상태 {r['status']!r}")
            mtpa = float(r["mtpa"])
            if mtpa <= 0:
                raise ValueError(f"{where}: 용량이 0 이하")
            check_url(r["source_url"], where)
            rows.append({"company": r["operator"], "project": r["vessel"], "unit": r["country"], "mtpa": mtpa,
                         "status": FLNG_STATUS[r["status"]], "start": r["start_year"], "fid": "", "note": r["note"],
                         "source": urlparse(r["source_url"]).netloc.removeprefix("www."), "source_url": r["source_url"]})
    return rows


def totals(rows):
    out = {k: 0.0 for k in STATUSES}
    for r in rows:
        out[r["status"]] = round(out[r["status"]] + r["mtpa"], 3)
    return out


def save(cid, doc):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f"{cid}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")


def run():
    today = dt.date.today().isoformat()
    base = {"unit": "MTPA", "updated": REVIEWED, "fetched": today, "manual": True, "status_order": list(STATUSES)}
    us, flng = read_us(), read_flng()
    save("lng_us_by_company", {
        **base, "id": "lng_us_by_company", "name": "미국 LNG 프로젝트 용량", "row_noun": "기업",
        "project_noun": "프로젝트", "status_labels": STATUSES, "totals": totals(us),
        "source": "회사 공시·DOE·EIA·GEM·업계 보도 대조",
        "source_url": "https://globalenergymonitor.org/projects/global-gas-infrastructure-tracker/",
        "note": ("막대 한 칸이 프로젝트(단계) 하나다. 지분을 나누지 않고 운영·주도 회사에 용량 전체를 넣었다. "
                 "기존 설비는 EIA 기준 명판 용량, 새 프로젝트는 회사·GEM 표기라 회사 홍보용 피크 용량보다 작을 수 있다. "
                 "FID 전 물량은 상당수가 지연되거나 취소된다. 기존 EIA 차트·표는 2025-06 기준이라 이 막대와 다르다."),
        "rows": us,
    })
    save("flng_by_company", {
        **base, "id": "flng_by_company", "name": "FLNG 선단 용량", "row_noun": "기업", "project_noun": "선박",
        "status_labels": FLNG_LABELS, "totals": totals(flng),
        "source": "회사 공시·GEM·업계 보도 대조",
        "source_url": "https://globalenergymonitor.org/projects/global-gas-infrastructure-tracker/",
        "note": ("막대 한 칸이 FLNG 한 척(또는 사업) 하나다. 운영사에 용량 전체를 넣었다. Delfin은 미국 차트에도 들어 있다. "
                 "Hilli는 2026-07 카메룬 계약을 끝내고 아르헨티나 투입 전 개조 중이라 건조·개조중으로 분류했다. "
                 "GEM이 해상으로 표시한 Ichthys는 육상 액화라, Browse는 파이프라인 안으로 바뀌어 뺐다."),
        "rows": flng,
    })
    print(f"  미국 {len(us)}건 {totals(us)}")
    print(f"  FLNG {len(flng)}건 {totals(flng)}")


if __name__ == "__main__":
    run()
