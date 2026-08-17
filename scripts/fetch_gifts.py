# -*- coding: utf-8 -*-
"""DART 임원·주요주주 소유보고 중 '증여/수증' 이벤트 수집 → data/_dart/증여DB.csv.

증여는 별도 공시가 아니라 임원·주요주주 특정증권등 소유상황보고서의 변동사유='증여(-)'/
'수증(+)' 로 잡힌다. 사유는 API에 없어 원문(document.xml) 파싱 필수(수주 방식).
대주주 필터는 수집 후 UI에서(다 뽑고 탈락).

방침: 시장 전체 임원 소유보고를 훑어 원문에서 증여/수증 행이 있는 것만 저장.
  원문 커스텀태그: AUNIT/ACODE. 헤더=CRP_*/IFR_NM/STF_PSM/MAIN_SH/FLT_SUM,
  변동행=RPT_RSN(사유)/MDF_STK_CNT(증감)/AFR_STK_CNT(변동후)/RMK(증여자·수증자명).

    python scripts/fetch_gifts.py            # 증분
    python scripts/fetch_gifts.py --from 20250101   # 백필
    python scripts/fetch_gifts.py --days 30
"""
import argparse
import csv
import datetime as dt
import io
import os
import re
import sys
import time
import zipfile
from pathlib import Path

import requests

LIST_URL = "https://opendart.fss.or.kr/api/list.json"
DOC_URL = "https://opendart.fss.or.kr/api/document.xml"
ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "_dart" / "증여DB.csv"

CLS = {"Y": "코스피", "K": "코스닥"}
FIELDS = ["rcept_no", "rcept_dt", "corp_name", "stock_code", "market", "reporter", "position",
          "main_sh", "direction", "gift_shares", "after_shares", "float_total", "gift_rate",
          "counterparty", "report_nm"]


def load_db():
    rows = {}
    if DB_PATH.exists():
        with DB_PATH.open(encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                rows[r["rcept_no"]] = r
    return rows


def save_db(rows):
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(rows.values(), key=lambda r: (r["rcept_dt"], r["rcept_no"]), reverse=True)
    with DB_PATH.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(ordered)


def date_chunks(bgn, end, days=89):
    b = dt.datetime.strptime(bgn, "%Y%m%d").date()
    e = dt.datetime.strptime(end, "%Y%m%d").date()
    cur = b
    while cur <= e:
        ce = min(cur + dt.timedelta(days=days - 1), e)
        yield cur.strftime("%Y%m%d"), ce.strftime("%Y%m%d")
        cur = ce + dt.timedelta(days=1)


def scan_reports(session, api_key, bgn, end):
    """임원·주요주주 소유보고 rcept_no 목록(시장 전체)."""
    out = []
    for cls in ["Y", "K"]:
        for cb, ce in date_chunks(bgn, end):
            page = 1
            while True:
                r = session.get(LIST_URL, params={"crtfc_key": api_key, "bgn_de": cb, "end_de": ce,
                                                   "pblntf_ty": "D", "corp_cls": cls,
                                                   "page_count": 100, "page_no": page}, timeout=30)
                d = r.json()
                if d.get("status") == "013":
                    break
                if d.get("status") != "000":
                    raise RuntimeError(f"list {cls} {d.get('status')} {d.get('message')}")
                for it in d.get("list", []):
                    if "임원" in (it.get("report_nm") or ""):
                        out.append(it)
                if page >= int(d.get("total_page", 1)):
                    break
                page += 1
                time.sleep(0.08)
    return out


def _field(html, code):
    m = re.search(r'(?:ACODE|AUNIT)="%s"[^>]*>([^<]*)<' % code, html)
    return m.group(1).strip() if m else ""


def _num(s):
    s = re.sub(r"[^\d\-]", "", s or "")
    try:
        return int(s)
    except ValueError:
        return None


def parse_gift(html):
    """원문 HTML → 증여/수증 이벤트(없으면 None). 여러 증여행은 합산."""
    if "증여" not in html and "수증" not in html:
        return None
    gift_rows = []
    for tr in re.split(r"<TR\b", html):
        rsn = re.search(r'AUNIT="RPT_RSN"[^>]*>([^<]*)<', tr)
        if not rsn:
            continue
        reason = rsn.group(1).strip()
        if "증여" not in reason and "수증" not in reason:
            continue
        mdf = re.search(r'ACODE="MDF_STK_CNT"[^>]*>([^<]*)<', tr)
        aft = re.search(r'ACODE="AFR_STK_CNT"[^>]*>([^<]*)<', tr)
        rmk = re.search(r'ACODE="RMK"[^>]*>([^<]*)<', tr)
        gift_rows.append({
            "reason": reason,
            "shares": _num(mdf.group(1)) if mdf else None,
            "after": _num(aft.group(1)) if aft else None,
            "rmk": (rmk.group(1).strip() if rmk else ""),
        })
    if not gift_rows:
        return None
    total = sum(abs(g["shares"]) for g in gift_rows if g["shares"] is not None)
    first = gift_rows[0]
    direction = "수증(받음)" if "수증" in first["reason"] else "증여(줌)"
    after = next((g["after"] for g in reversed(gift_rows) if g["after"] is not None), None)
    cp = ""
    for g in gift_rows:
        m = re.search(r"(?:증여자|수증자)\s*[:：]\s*([^\s,()]+)", g["rmk"])
        if m:
            cp = m.group(1)
            break
    return {"direction": direction, "gift_shares": total, "after_shares": after, "counterparty": cp}


def fetch_doc(session, api_key, rcept_no):
    r = session.get(DOC_URL, params={"crtfc_key": api_key, "rcept_no": rcept_no}, timeout=30)
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        raw = zf.read(zf.namelist()[0])
    return raw.decode("utf-8", "replace")


def run(api_key, bgn, end):
    db = load_db()
    before = len(db)
    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0"

    reports = scan_reports(session, api_key, bgn, end)
    todo = [it for it in reports if it["rcept_no"] not in db]
    print(f"임원 소유보고 {len(reports):,}건 / 신규 원문파싱 대상 {len(todo):,}건 ({bgn}~{end})")

    gifts = 0
    for i, it in enumerate(todo, 1):
        try:
            html = fetch_doc(session, api_key, it["rcept_no"])
            g = parse_gift(html)
        except Exception:  # noqa
            time.sleep(0.3)
            continue
        if g:
            market = "코스닥" if "코스닥" in _field(html, "CRP_DST") else ("코스피" if "유가" in _field(html, "CRP_DST") else CLS.get(it.get("corp_cls"), ""))
            ft = _num(_field(html, "FLT_SUM"))
            rate = round(100 * g["gift_shares"] / ft, 4) if ft and g["gift_shares"] else None
            db[it["rcept_no"]] = {
                "rcept_no": it["rcept_no"],
                "rcept_dt": it.get("rcept_dt", ""),
                "corp_name": (it.get("corp_name") or _field(html, "CRP_NM")).strip(),
                "stock_code": (it.get("stock_code") or _field(html, "CRP_CD")).strip(),
                "market": market,
                "reporter": _field(html, "IFR_NM"),
                "position": _field(html, "STF_PSM"),
                "main_sh": _field(html, "MAIN_SH"),
                "direction": g["direction"],
                "gift_shares": g["gift_shares"],
                "after_shares": g["after_shares"],
                "float_total": ft,
                "gift_rate": rate,
                "counterparty": g["counterparty"],
                "report_nm": (it.get("report_nm") or "").strip(),
            }
            gifts += 1
        if i % 300 == 0:
            print(f"  ...{i}/{len(todo)} (증여 {gifts})")
            save_db(db)
        time.sleep(0.06)

    save_db(db)
    print(f"완료: 신규 증여 {len(db) - before:,}건, 전체 {len(db):,}건 → {DB_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--api-key", default=os.environ.get("DART_API_KEY", ""))
    ap.add_argument("--from", dest="bgn")
    ap.add_argument("--days", type=int)
    ap.add_argument("--to", dest="end")
    args = ap.parse_args()
    if not args.api_key:
        sys.exit("DART_API_KEY 필요")
    today = dt.date.today()
    end = args.end or today.strftime("%Y%m%d")
    if args.bgn:
        bgn = args.bgn
    elif args.days:
        bgn = (today - dt.timedelta(days=args.days)).strftime("%Y%m%d")
    else:
        db = load_db()
        bgn = max((r["rcept_dt"].replace("-", "") for r in db.values()), default="") or (today - dt.timedelta(days=90)).strftime("%Y%m%d")
    run(args.api_key, bgn, end)
