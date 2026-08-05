# -*- coding: utf-8 -*-
"""DART 주식등의 대량보유상황보고서(5% 룰) 시장 전체 수집기.

기관/대주주 수급 모니터링용. 조선 4사 계약 추출기(dart_extractor.py)와 달리
종목을 지정하지 않고 **시장 전체 지분공시(pblntf_ty=D)** 를 날짜범위로 훑는다.

방침(누락 0): 보고자로 사전 필터링하지 않고 코스피·코스닥의 모든 대량보유 공시를
저장한다. 개인/기관/대주주 분류는 저장 후 aggregate 단계에서 태깅(재분류 자유).

산출: data/_dart/대량보유DB.csv (rcept_no 기준 dedup 누적)
  list.json 이 이미 주는 필드만으로 이벤트 테이블 구성 가능(원문 파싱 없음):
  공시일·시장·종목명·종목코드·공시유형·보고자.

키 주입(공개 리포라 하드코딩 금지): 환경변수 DART_API_KEY(로컬) /
GitHub Secret DART_API_KEY(CI) / --api-key.

    python scripts/fetch_major_holdings.py            # 증분(마지막 수집일~오늘)
    python scripts/fetch_major_holdings.py --from 20240101   # 백필
    python scripts/fetch_major_holdings.py --days 30         # 최근 N일
"""
import argparse
import csv
import datetime as dt
import io
import json
import os
import sys
import time
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import requests

LIST_URL = "https://opendart.fss.or.kr/api/list.json"
CORP_CODE_URL = "https://opendart.fss.or.kr/api/corpCode.xml"
VIEWER_URL = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo={no}"

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "_dart" / "대량보유DB.csv"
CORP_NAMES_PATH = ROOT / "data" / "_dart" / "_corp_names.json"

CORP_CLS = {"Y": "코스피", "K": "코스닥", "N": "코넥스", "E": "기타"}
SCAN_CLS = ["Y", "K"]  # 코스피 + 코스닥 (시총 제한 없음)
FIELDS = ["rcept_no", "rcept_dt", "corp_cls", "corp_name", "stock_code", "report_nm", "flr_nm"]


class DartApiError(RuntimeError):
    pass


def load_db() -> dict:
    """rcept_no -> row dict."""
    rows = {}
    if DB_PATH.exists():
        with DB_PATH.open(encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                rows[r["rcept_no"]] = r
    return rows


def save_db(rows: dict) -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(rows.values(), key=lambda r: (r["rcept_dt"], r["rcept_no"]), reverse=True)
    with DB_PATH.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(ordered)


def refresh_corp_names(session, api_key) -> int:
    """DART 전체 기업명 집합을 받아 캐시(개인/법인 판별용 화이트리스트)."""
    resp = session.get(CORP_CODE_URL, params={"crtfc_key": api_key}, timeout=60)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        root = ET.parse(zf.open("CORPCODE.xml")).getroot()
    names = sorted({(it.findtext("corp_name") or "").strip() for it in root.findall("list")} - {""})
    CORP_NAMES_PATH.parent.mkdir(parents=True, exist_ok=True)
    CORP_NAMES_PATH.write_text(json.dumps(names, ensure_ascii=False), encoding="utf-8")
    return len(names)


def date_chunks(bgn_de: str, end_de: str, days: int = 89):
    """corp_code 없는 시장전체 조회는 최대 3개월 → 89일 단위로 분할."""
    b = dt.datetime.strptime(bgn_de, "%Y%m%d").date()
    e = dt.datetime.strptime(end_de, "%Y%m%d").date()
    cur = b
    while cur <= e:
        ce = min(cur + dt.timedelta(days=days - 1), e)
        yield cur.strftime("%Y%m%d"), ce.strftime("%Y%m%d")
        cur = ce + dt.timedelta(days=1)


def fetch_range(session, api_key, corp_cls, bgn_de, end_de) -> list:
    out, page_no = [], 1
    while True:
        params = {
            "crtfc_key": api_key,
            "bgn_de": bgn_de,
            "end_de": end_de,
            "pblntf_ty": "D",   # 지분공시
            "corp_cls": corp_cls,
            "page_count": 100,
            "page_no": page_no,
        }
        resp = session.get(LIST_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status")
        if status == "013":  # 조회된 데이터 없음
            break
        if status != "000":
            raise DartApiError(f"list.json {corp_cls} 오류: {status} / {data.get('message')}")

        for it in data.get("list", []):
            if "대량보유" in (it.get("report_nm") or ""):
                out.append(it)

        total_page = int(data.get("total_page", 1))
        if page_no >= total_page:
            break
        page_no += 1
        time.sleep(0.1)
    return out


def run(api_key: str, bgn_de: str, end_de: str):
    db = load_db()
    before = len(db)
    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0"

    # 기업명 캐시: 없거나 30일 이상 오래되면 갱신(개인/법인 판별용)
    stale = True
    if CORP_NAMES_PATH.exists():
        age = time.time() - CORP_NAMES_PATH.stat().st_mtime
        stale = age > 30 * 86400
    if stale:
        n = refresh_corp_names(session, api_key)
        print(f"  기업명 캐시 갱신: {n:,}개")

    for cls in SCAN_CLS:
        got = 0
        for cb, ce in date_chunks(bgn_de, end_de):
            items = fetch_range(session, api_key, cls, cb, ce)
            for it in items:
                no = it.get("rcept_no")
                if not no:
                    continue
                db[no] = {
                    "rcept_no": no,
                    "rcept_dt": it.get("rcept_dt", ""),
                    "corp_cls": CORP_CLS.get(it.get("corp_cls", ""), it.get("corp_cls", "")),
                    "corp_name": (it.get("corp_name") or "").strip(),
                    "stock_code": (it.get("stock_code") or "").strip(),
                    "report_nm": (it.get("report_nm") or "").strip(),
                    "flr_nm": (it.get("flr_nm") or "").strip(),
                }
            got += len(items)
        print(f"  {CORP_CLS[cls]}: {got:,}건 (대량보유)")

    save_db(db)
    print(f"완료: 신규 {len(db) - before:,}건, 전체 {len(db):,}건 → {DB_PATH.relative_to(ROOT)}")
    print(f"  범위 {bgn_de}~{end_de}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--api-key", default=os.environ.get("DART_API_KEY", ""))
    ap.add_argument("--from", dest="bgn", help="시작일 YYYYMMDD (백필)")
    ap.add_argument("--days", type=int, help="최근 N일")
    ap.add_argument("--to", dest="end", help="종료일 YYYYMMDD (기본 오늘)")
    args = ap.parse_args()

    if not args.api_key:
        sys.exit("DART_API_KEY 미설정: 환경변수 또는 --api-key 로 주입하세요.")

    today = dt.date.today()
    end_de = args.end or today.strftime("%Y%m%d")
    if args.bgn:
        bgn_de = args.bgn
    elif args.days:
        bgn_de = (today - dt.timedelta(days=args.days)).strftime("%Y%m%d")
    else:
        # 증분: DB 최신 공시일부터(그날 늦게 접수분 재확인, dedup 처리). 없으면 최근 180일.
        db = load_db()
        if db:
            last = max(r["rcept_dt"] for r in db.values())  # YYYYMMDD
            bgn_de = last.replace("-", "").replace(".", "")[:8] or (today - dt.timedelta(days=180)).strftime("%Y%m%d")
        else:
            bgn_de = (today - dt.timedelta(days=180)).strftime("%Y%m%d")

    run(args.api_key, bgn_de, end_de)
