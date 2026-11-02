# -*- coding: utf-8 -*-
"""SEC EDGAR에서 분기 실적 보도자료(8-K Item 2.02 첨부 EX-99)를 찾는다.

회사 IR 사이트가 스크립트 요청을 403으로 막을 때 쓰는 공식 대체 경로다.
"""
import re

import requests

HEADERS = {"User-Agent": "industry-dashboard personal research wkorotk@gmail.com"}
EXHIBIT = re.compile(r"ex[-_]?99|exhibit[-_]?99|earning|press", re.I)  # Fluence: flncq3fy26earningspressrel.htm


def sec_get(url, timeout=45):
    response = requests.get(url, headers=HEADERS, timeout=timeout)
    response.raise_for_status()
    return response


def earnings_exhibits(cik, since, get=sec_get):
    """filed >= since인 실적 8-K의 첨부 보도자료 [{filed, url}], 오래된 순."""
    recent = get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json").json()["filings"]["recent"]
    found = []
    for form, filed, accession, items in zip(recent["form"], recent["filingDate"], recent["accessionNumber"], recent["items"]):
        if form != "8-K" or "2.02" not in items or filed < since:
            continue
        folder = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession.replace('-', '')}/"
        names = [item["name"] for item in get(folder + "index.json").json()["directory"]["item"]]
        exhibits = sorted(name for name in names if EXHIBIT.search(name) and name.lower().endswith((".htm", ".html")))
        if exhibits:
            found.append({"filed": filed, "url": folder + exhibits[0]})
    return sorted(found, key=lambda row: row["filed"])
