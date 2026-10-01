# -*- coding: utf-8 -*-
"""ASML 지역별 매출(고객 설비 소재지 기준) → 반도체 소부장 > 에스앤에스텍 서브탭 카드.

원본: ASML이 SEC에 내는 6-K(CIK 937966)의 반기보고서(statutory interim report, 7월)와
연간보고서(2~3월)에 들어 있는 'Total net sales by geographic region' 글자 표. 키 없이 SEC EDGAR에서 받는다
(SEC 정책상 User-Agent에 연락처를 적어야 한다).

자동 갱신: 이미 파싱한 제출은 data/_asml/region_tables.json에 남겨 두고, 새 제출만 받아 붙인다.
반기·연간 값만 공개되므로 하반기 = 연간 − 상반기로 만든다.

**표 형식이 연도마다 다르다**(검증: 지역 합 == 표의 Total, 28개 표 모두 일치):
  - 단위: 2017년 상반기까지 천€, 이후 백만€
  - 반기표 열 순서: (전기, 당기)가 기본, 2014-07 제출만 (당기, 전기), 2013-07은 (매출, 비유동자산)
  - 연간표: (매출, 비유동자산) 쌍. 2024·2025 연간보고서는 3개년이 연도 표기 없이 오름차순 → 당해 = 5번째 숫자
  - 지역명: Korea→South Korea, Netherlands·Rest of Europe·Europe→EMEA. 2015년 상반기 이전엔 China가
    'Rest of Asia'에 묶여 있다.

    python scripts/fetch_asml_regions.py
"""
import datetime as dt
import html
import json
import re
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "_asml" / "region_tables.json"
OUT = ROOT / "data" / "semicon"
UA = {"User-Agent": "industry-dashboard (personal research) wkorotk@gmail.com"}
CIK = "937966"
SEC_URL = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000937966&type=6-K"

NAMES = ["United States", "South Korea", "Korea", "Singapore", "Taiwan", "China", "Rest of Asia",
         "Netherlands", "Rest of Europe", "EMEA", "Europe", "Japan", "Total"]
CANON = {"Korea": "South Korea", "Netherlands": "EMEA", "Rest of Europe": "EMEA", "Europe": "EMEA"}
KO = {"South Korea": "한국", "Taiwan": "대만", "China": "중국", "United States": "미국", "Japan": "일본",
      "Singapore": "싱가포르", "EMEA": "유럽·중동(EMEA)", "Rest of Asia": "기타 아시아"}
NUM = r"\(?-?[\d][\d,]*\.?\d*\s*\)?"


def get(url):
    for _ in range(3):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90).read().decode("utf-8", "replace")
        except Exception:  # noqa
            time.sleep(2)
    return ""


def text_of(raw):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw)))


def tonum(s):
    s = s.replace(" ", "")
    neg = s.startswith("(") and s.endswith(")")
    v = float(s.strip("()").replace(",", ""))
    return -v if neg else v


def parse(date, t):
    """지역 표 한 개 → (기간, {지역: €백만}, Total). 형식 분기는 모듈 설명 참고."""
    unit = 1 / 1000 if "(in thousands)" in t else 1.0
    interim = "six-month" in t
    pat = r"(" + "|".join(re.escape(n) for n in NAMES) + r")\s+((?:" + NUM + r"\s+){1,6})"
    blk = []
    for m in re.finditer(pat, t):
        nums = re.findall(NUM, m.group(2))
        if len(nums) > 1 and re.fullmatch(r"[1-9]", nums[0].strip()):  # 'EMEA 1 (18.4)' 같은 각주 번호
            nums = nums[1:]
        blk.append((m.group(1), [tonum(n) for n in nums]))
        if m.group(1) == "Total":
            break
    y = int(date[:4])
    if interim:
        period = f"{y}H1"
        col = 0 if date in ("2013-07-17", "2014-07-16") else 1
    else:
        period = f"{y - 1}FY"
        col = 4 if date >= "2025" else 0
    vals = {}
    for n, nums in blk:
        if len(nums) > col:
            k = CANON.get(n, n)
            vals[k] = vals.get(k, 0) + nums[col] * unit
    total = vals.pop("Total", None)
    if total is None or abs(sum(vals.values()) - total) > max(1.0, total * 0.002):
        raise ValueError(f"{date} 지역 합 {sum(vals.values()):.1f} ≠ Total {total}")
    return period, {k: round(v, 1) for k, v in vals.items()}, round(total, 1)


def find_table(t):
    for m in re.finditer(r"(?i)(?:totals?|net sales)[^.]{0,60}by geographic region", t):
        seg = t[m.start():m.start() + 3000]
        if re.search(r"Taiwan\s+[\d,\.]+", seg[:900]):
            return seg
    return None


def update_cache():
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    sub = json.loads(get(f"https://data.sec.gov/submissions/CIK{int(CIK):010d}.json") or "{}")
    r = sub.get("filings", {}).get("recent", {})
    new = 0
    for i, form in enumerate(r.get("form", [])):
        d, acc = r["filingDate"][i], r["accessionNumber"][i]
        if form != "6-K" or d < "2013" or d in cache:
            continue
        if d[5:7] not in ("01", "02", "03", "07"):  # 연간보고서(1~3월)·반기보고서(7월)만
            continue
        a = acc.replace("-", "")
        try:
            items = json.loads(get(f"https://www.sec.gov/Archives/edgar/data/{CIK}/{a}/index.json"))["directory"]["item"]
        except Exception:  # noqa
            continue
        docs = [it["name"] for it in items if it["name"].endswith(".htm")
                and re.search(r"annual|integrated|statutory|interim|ex99", it["name"], re.I)
                and int(it.get("size") or 0) > 20000]
        for h in docs:
            seg = find_table(text_of(get(f"https://www.sec.gov/Archives/edgar/data/{CIK}/{a}/{h}")))
            time.sleep(0.15)
            if seg:
                period, vals, total = parse(d, seg)
                cache[d] = {"period": period, "doc": h, "regions": vals, "total": total}
                new += 1
                print(f"  + {d} {period} 합계 {total:,.0f}")
                break
        else:
            # 표가 없는 제출(1월 4분기 실적 등)도 '확인함'으로 남겨 매일 다시 받지 않게 한다
            cache[d] = {"period": None}
        time.sleep(0.15)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(dict(sorted(cache.items())), ensure_ascii=False, indent=1), encoding="utf-8")
    return cache, new


def build(cache):
    per = {v["period"]: v["regions"] for v in cache.values() if v.get("period")}
    halves = {}
    for p, v in per.items():
        if p.endswith("H1"):
            halves[(int(p[:4]), 1)] = v
    for p, v in per.items():
        if p.endswith("FY"):
            y = int(p[:4])
            h1 = per.get(f"{y}H1")
            if h1:  # 하반기 = 연간 − 상반기 (반기 단위로만 공개되므로)
                halves[(y, 2)] = {k: round(v.get(k, 0) - h1.get(k, 0), 1) for k in set(v) | set(h1)}
    keys = sorted(halves)
    regions = ["South Korea", "Taiwan", "China", "United States", "Japan", "EMEA", "Singapore", "Rest of Asia"]

    def date(k):
        return f"{k[0]}-06-30" if k[1] == 1 else f"{k[0]}-12-31"
    sales = {KO[r]: [[date(k), round(halves[k].get(r, 0) / 1000, 2)] for k in keys if r in halves[k] or r != "China"]
             for r in regions}
    sales = {k: v for k, v in sales.items() if v}
    share = {}
    for r in regions:
        pts = []
        for k in keys:
            tot = sum(halves[k].values())
            if r in halves[k] and tot:
                pts.append([date(k), round(halves[k][r] / tot * 100, 1)])
        if pts:
            share[KO[r]] = pts
    last = keys[-1]
    lastv = halves[last]
    tot = sum(lastv.values())
    top = sorted(lastv.items(), key=lambda kv: -kv[1])[:4]
    label = f"{last[0]}년 {'상' if last[1] == 1 else '하'}반기"
    common = {"unit": "", "frequency": "semiannual", "full_range": True, "source": "ASML 반기·연간보고서(SEC 6-K)",
              "source_url": SEC_URL, "updated": date(last), "fetched": dt.date.today().isoformat(),
              "stale_days": 200,  # 반기 공시라 매일 갱신 기준으로 보면 늘 '지연'이다
              "default_series": ["한국", "대만", "중국", "미국"]}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "asml_region_sales.json").write_text(json.dumps({
        **common, "id": "asml_region_sales", "name": "ASML 지역별 매출 (반기, 고객 설비 소재지)", "unit": "€bn",
        "description": (
            "ASML 매출을 고객 공장이 있는 나라별로 나눈 것 — 누가 노광기를 사 가는지의 근사치다. 한국은 삼성전자·"
            "SK하이닉스, 대만은 TSMC, 미국은 인텔·마이크론·TSMC 애리조나, 중국은 SMIC·CXMT 등이 주 고객이다. "
            "블랭크마스크는 장비가 깔린 곳에서 쓰이므로, 에스앤에스텍의 내수(한국)와 수출처 수요를 함께 가늠할 수 있다."
        ),
        "note": (f"{label} " + " · ".join(f"{KO[k]} {v / 1000:.1f}" for k, v in top) + f" (€bn, 합계 {tot / 1000:.1f}). "
                 "장비+서비스를 합친 총매출 기준이며 대수가 아니라 금액이다(지역별 대수는 공개되지 않는다). "
                 "하반기는 연간 − 상반기로 계산. 2015년 상반기 이전엔 중국이 '기타 아시아'에 들어 있다. "
                 "SEC에서 자동으로 받아 새 반기·연간보고서가 나오면 갱신된다."),
        "series": sales,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "asml_region_share.json").write_text(json.dumps({
        **common, "id": "asml_region_share", "name": "ASML 지역별 매출 비중 (반기)", "unit": "%",
        "description": (
            "위 지역별 매출을 반기 합계 대비 비중으로 바꾼 것. 금액 규모가 커지는 효과를 걷어내고 어느 지역이 "
            "몫을 늘리고 줄이는지만 본다 — 2023~2024년 중국 비중 급등(수출규제를 앞둔 선구매로 풀이된다)과 이후 되돌림, "
            "한국 비중의 오르내림이 특히 눈에 띈다."
        ),
        "note": "총매출(장비+서비스) 기준 비중. 하반기는 연간 − 상반기.",
        "series": share,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  ASML 지역: 반기 {len(keys)}개({keys[0][0]}H{keys[0][1]}~{last[0]}H{last[1]})")


if __name__ == "__main__":
    cache, new = update_cache()
    print(f"  새 지역 표 {new}개 · 누적 {sum(1 for v in cache.values() if v.get('period'))}개")
    build(cache)
