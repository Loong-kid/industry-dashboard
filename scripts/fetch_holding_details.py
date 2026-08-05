# -*- coding: utf-8 -*-
"""대량보유DB의 종목별 majorstock.json(대량보유 상황보고 상세) 수집.

list.json엔 없는 **보유비율(stkrt)·직전대비 증감(stkrt_irds)·보고사유** 를 붙인다.
majorstock.json은 corp_code당 그 회사의 대량보유 이력 전체를 반환 → rcept_no로 조인.

증분: 대량보유DB에 있는 rcept_no 중 상세DB에 없는 게 있는 corp만 재조회(신규 공시 발생 corp).

산출: data/_dart/대량보유상세DB.csv (rcept_no dedup)
    python scripts/fetch_holding_details.py [--api-key KEY]
"""
import argparse
import csv
import io
import os
import sys
import time
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import requests

MAJORSTOCK_URL = "https://opendart.fss.or.kr/api/majorstock.json"
CORP_CODE_URL = "https://opendart.fss.or.kr/api/corpCode.xml"

ROOT = Path(__file__).resolve().parent.parent
MAIN_DB = ROOT / "data" / "_dart" / "대량보유DB.csv"
DETAIL_DB = ROOT / "data" / "_dart" / "대량보유상세DB.csv"

FIELDS = ["rcept_no", "rcept_dt", "corp_code", "corp_name", "report_tp",
          "repror", "stkqy", "stkqy_irds", "stkrt", "stkrt_irds", "report_resn"]


def stock_to_corp_map(session, api_key) -> dict:
    resp = session.get(CORP_CODE_URL, params={"crtfc_key": api_key}, timeout=60)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        root = ET.parse(zf.open("CORPCODE.xml")).getroot()
    m = {}
    for it in root.findall("list"):
        sc = (it.findtext("stock_code") or "").strip()
        cc = (it.findtext("corp_code") or "").strip()
        if sc and cc:
            m[sc] = cc
    return m


def load_csv(path) -> dict:
    rows = {}
    if path.exists():
        with path.open(encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                rows[r["rcept_no"]] = r
    return rows


def save_detail(rows: dict):
    DETAIL_DB.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(rows.values(), key=lambda r: (r["rcept_dt"], r["rcept_no"]), reverse=True)
    with DETAIL_DB.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(ordered)


def run(api_key: str):
    if not MAIN_DB.exists():
        sys.exit("대량보유DB.csv 없음 — 먼저 fetch_major_holdings.py 실행")
    main = load_csv(MAIN_DB)
    detail = load_csv(DETAIL_DB)
    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0"

    # 종목코드 → corp_code
    s2c = stock_to_corp_map(session, api_key)

    # main DB를 stock_code(→corp_code)별로 묶고, 상세가 빠진 rcept_no가 있는 corp만 대상
    by_corp = {}  # corp_code -> set(rcept_no)
    for r in main.values():
        cc = s2c.get(r["stock_code"])
        if not cc:
            continue
        by_corp.setdefault(cc, set()).add(r["rcept_no"])

    targets = [cc for cc, rns in by_corp.items() if not rns.issubset(detail.keys())]
    print(f"대상 corp {len(targets):,} / 전체 {len(by_corp):,} (신규 공시 발생분만)")

    before = len(detail)
    for i, cc in enumerate(targets, 1):
        try:
            resp = session.get(MAJORSTOCK_URL, params={"crtfc_key": api_key, "corp_code": cc}, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"  ! {cc} 실패: {e}")
            continue
        if data.get("status") == "020":
            sys.exit("API 사용한도 초과(020). 나중에 재시도.")
        for it in data.get("list", []):
            no = it.get("rcept_no")
            if not no:
                continue
            detail[no] = {k: (it.get(k) or "").strip() for k in FIELDS}
        if i % 200 == 0:
            print(f"  ...{i}/{len(targets)} (누적 {len(detail):,})")
            save_detail(detail)  # 중간 저장(대량 백필 안전)
        time.sleep(0.08)

    save_detail(detail)
    print(f"완료: 신규 {len(detail) - before:,}건, 전체 {len(detail):,}건 → {DETAIL_DB.relative_to(ROOT)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--api-key", default=os.environ.get("DART_API_KEY", ""))
    args = ap.parse_args()
    if not args.api_key:
        sys.exit("DART_API_KEY 미설정")
    run(args.api_key)
