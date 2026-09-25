# -*- coding: utf-8 -*-
"""asiasis(일간조선해양) 신조 오더북 증분 갱신 — CI용. data/shipbuilding/asiasis_orders.json에 새 글만 덧붙인다.

로컬 파이프라인(../asiasis-orderbook)은 원본 캐시(_cache.json) → 정규화 xlsx → 이 JSON의 3단이다.
**원본 캐시는 공개 리포에 올리지 않는다**는 결정이 있어, CI는 캐시 없이 돌아야 한다. 그래서
이미 받은 글은 **공개 JSON의 url(bbs_no)**로 판별하고, 새 글만 목록→상세를 읽어 정규화한 뒤 덧붙인다.

정규화 규칙(선종·조선소 국적·선가 환산·날짜)은 ../asiasis-orderbook/normalize.py와 같아야 한다.
**그쪽 규칙을 고치면 여기도 같이 고칠 것** — 로컬 전체 재생성(aggregate_asiasis_orders.py)과
CI 증분이 서로 다른 분류를 내면 칩 필터가 어긋난다.

    python scripts/update_asiasis.py
"""
import json
import re
import time
from collections import Counter
from datetime import date
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "shipbuilding" / "asiasis_orders.json"

BASE = "http://asiasis.com/wi_bbs"  # https는 인증서가 깨져 있다 — http로만 붙는다
LIST_URL = BASE + "/wi_kr_list.php?bbs_arr=1&pagenum={pg}"
VIEW_URL = BASE + "/wi_kr_view.php?bbs_arr=1&bbs_no={no}"
HDRS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Referer": "http://asiasis.com/"}
FIELDS = ["Reported Date", "Vessel Type", "Size", "Delivery", "Builder", "Buyer", "No", "Price ($m)", "Remarks"]
MAX_PAGES = 30  # 증분은 보통 1~5페이지에서 끝난다. 오래 방치됐을 때의 상한

# ── 수집 (crawl_asiasis.py와 동일) ─────────────────────────────────


def get(url, tries=3):
    last = ""
    for i in range(tries):
        try:
            r = requests.get(url, headers=HDRS, timeout=25, allow_redirects=True)
            r.encoding = "utf-8"
            if r.status_code == 200 and len(r.text) > 500:
                return r.text
            last = f"HTTP {r.status_code}, {len(r.text)}B"
        except requests.RequestException as e:
            last = f"{type(e).__name__}: {str(e)[:120]}"
        time.sleep(1.5 * (i + 1))
    # 해외(CI) 서버에서 막히는지, 느린지 구분하려고 마지막 실패 사유를 남긴다
    print(f"    요청 실패 ({last}) ← {url}")
    return ""


def parse_list(pg):
    html = get(LIST_URL.format(pg=pg))
    items = []
    for bbs_no, body in re.findall(
            r"<ul class='shell_data_4'[^>]*onclick=\"openPage\('(\d+)'\);[^>]*>(.*?)</ul>", html, re.S):
        cells = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", c)).strip()
                 for c in re.findall(r"<div>(.*?)</div>", body, re.S)]
        cells = [c for c in cells if c]
        items.append({
            "bbs_no": bbs_no,
            "title": cells[1] if len(cells) > 1 else "",
            "builder": cells[2] if len(cells) > 2 else "",
            "date": next((c for c in cells if re.match(r"20\d{2}-\d{2}-\d{2}$", c)), ""),
        })
    return items


def parse_detail(bbs_no):
    html = get(VIEW_URL.format(no=bbs_no))
    title = re.search(r"<div class='bbs_div_title'>(.*?)</div>", html, re.S)
    out = {"제목": re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", title.group(1))).strip() if title else ""}
    for label, val in re.findall(r"<tr class='tbl_s30'>\s*<td>(.*?)</td>\s*<td>(.*?)</td>\s*</tr>", html, re.S):
        label = re.sub(r"<[^>]+>", "", label).strip()
        if label in FIELDS:
            out[label] = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", val)).strip()
    return out


# ── 정규화 (normalize.py와 동일 규칙) ──────────────────────────────
MONTHS = {m: i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}

VESSEL_RULES = [
    (("VLCC", "초대형 원유", "초대형원유"), "VLCC(초대형원유운반선)"),
    (("crude oil", "원유운반선", "원유 운반선"), "원유운반선"),
    (("chemical", "케미컬", "석유제품", "product tanker", "제품운반선", "PC선", "P/C"), "석유제품/케미컬선"),
    (("shuttle", "셔틀"), "셔틀탱커"),
    (("tanker", "탱커", "유조선"), "탱커(기타)"),
    (("LNG",), "LNG운반선"),
    (("VLGC", "VLAC", "VLEC", "LPG", "ammonia", "암모니아", "ethane", "에탄", "가스"), "가스선(LPG/암모니아/에탄)"),
    (("container", "컨테이너", "box ship"), "컨테이너선"),
    (("bulk", "bulker", "BC", "벌커", "벌크", "capesize", "케이프", "handy", "panamax", "supramax"), "벌커"),
    (("car carrier", "PCTC", "PCC", "자동차운반선", "vehicle", "ro-ro", "로로", "ro/ro"), "자동차운반선(PCTC)"),
    (("cruise", "크루즈", "passenger", "여객"), "크루즈/여객선"),
    (("FPSO", "FSRU", "FSU", "FPU", "FLNG", "생산설비", "플랜트", "platform", "플랫폼", "drillship", "드릴십"), "해양설비"),
    (("풍력", "wind", "설치선", "WTIV"), "해상풍력설치선"),
    (("잠수함", "구축함", "호위함", "함정", "군수", "수상함", "frigate", "corvette", "navy", "submarine"), "군함/방산"),
]
NAT_KEYWORDS = {
    "한국": ["현대", "삼성", "대우", "한화", "한진", "HJ", "대선", "대한조선", "성동", "케이조선", "K조선", "SPP",
           "hyundai", "samsung", "daewoo", "dsme", "hanwha", "hanjin", "korea", "sungdong", "daehan",
           "daesun", "hd현대", "hmd", "hshi", "stx", "k shipbuilding"],
    "중국": ["후동", "상하이", "와이가오차오", "양쯔장", "뉴타임즈", "다롄", "장난", "코스코", "강소", "저장", "광저우",
           "난퉁", "칭다오", "양저우", "저우산", "우한", "우창", "청시", "hudong", "shanghai", "waigaoqiao", "sws",
           "yangzijiang", "yzj", "new times", "dalian", "jiangnan", "jiangsu", "zhejiang", "guangzhou", "nantong",
           "china", "cssc", "cmhi", "chengxi", "wuchang", "qingdao", "yangzhou", "zhoushan", "hantong", "xiangyu",
           "dajin", "guangji", "hubei", "cosco", "penglai", "new century", "shandong", "fujian", "weihai", "taizhou",
           "dayang", "wenchong", "huangpu", "jinling", "진링", "다양", "ouhua", "jinhai", "beihai", "sino",
           "avic", "cmi", "hengli", "yancheng", "wuhu", "jiangyin", "nacks", "dsic", "cosco shipping"],
    "일본": ["이마바리", "재팬마린", "JMU", "오시마", "나무라", "츠네이시", "미쓰비시", "가와사키", "스미토모", "미쓰이",
           "사노야스", "imabari", "japan marine", "oshima", "namura", "tsuneishi", "mitsubishi", "kawasaki",
           "sumitomo", "mitsui", "sanoyas", "japan", "kurushima", "onomichi", "mihara", "koyo", "shin kurushima"],
    "필리핀": ["subic", "수빅", "philly", "필리핀", "philippine", "cebu"],
    "베트남": ["vietnam", "베트남", "halong", "ha long"],
    "유럽": ["meyer", "fincantieri", "chantiers", "damen", "germany", "italy", "france", "romania", "norway",
           "poland", "croatia", "마이어", "핀칸티에리", "유럽"],
    "튀르키예": ["turkey", "turkiye", "터키", "튀르키예"],
    "인도": ["india", "인도", "cochin", "mazagon"],
    "미국": ["philly shipyard", "nassco", "미국", "usa", "u.s."],
    "대만": ["csbc", "taiwan", "대만"],
}
BUILDER_CANON = [
    (["hyundai heavy", "hd현대중공업", "현대중공업", "hd hyundai heavy", "hhi"], "HD현대중공업"),
    (["hyundai mipo", "현대미포", "hmd"], "HD현대미포"),
    (["hyundai samho", "현대삼호"], "HD현대삼호"),
    (["daewoo", "dsme", "대우조선", "한화오션", "hanwha ocean"], "한화오션(구 대우)"),
    (["samsung heavy", "삼성중공업", "samsung"], "삼성중공업"),
    (["hanjin", "한진중공업", "hj중공업", "hj heavy"], "HJ중공업"),
    (["k shipbuilding", "케이조선", "k조선"], "케이조선"),
    (["대선조선", "daesun"], "대선조선"),
    (["대한조선", "daehan"], "대한조선"),
    (["hudong", "후동중화", "후동"], "후동중화(中)"),
    (["waigaoqiao", "sws", "와이가오차오"], "상하이와이가오차오(中)"),
    (["yangzijiang", "yzj", "양쯔장"], "양쯔장(中)"),
    (["new times", "뉴타임즈"], "뉴타임즈(中)"),
    (["imabari", "이마바리"], "이마바리(日)"),
    (["japan marine", "jmu"], "재팬마린유나이티드(日)"),
]
# aggregate_asiasis_orders.py와 같은 칩 분류 — 여기 없는 선종은 '기타'로 묶는다
CANON_CATEGORIES = {k for _, k in VESSEL_RULES}


def norm_date(s, fallback=""):
    s = (s or "").strip() or (fallback or "").strip()
    m = re.match(r"(20\d{2})[.\-\s]+(\d{1,2})[.\-\s]+(\d{1,2})", s)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = re.match(r"([A-Z][a-z]{2})\s+(\d{1,2}),?\s+(20\d{2})", s)
    if m and m.group(1) in MONTHS:
        return f"{m.group(3)}-{MONTHS[m.group(1)]:02d}-{int(m.group(2)):02d}"
    m = re.match(r"(\d{1,2})-(\d{1,2})-(20\d{2})", s)
    if m:
        return f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    return s


def norm_vessel(s):
    s = (s or "").strip()
    if not s or s == "-":
        return ""
    for keys, canon in VESSEL_RULES:
        if any(k.lower() in s.lower() for k in keys):
            return canon
    return s


def classify(builder):
    b = (builder or "").strip()
    if not b or b == "-":
        return "", ""
    canon = next((name for keys, name in BUILDER_CANON if any(k.lower() in b.lower() for k in keys)), b)
    nat = next((c for c, kws in NAT_KEYWORDS.items() if any(k.lower() in b.lower() for k in kws)), "기타")
    return canon, nat


def parse_price(s):
    s = (s or "").strip()
    if not s or s == "-":
        return None, ""
    if not re.search(r"불|\$|dollar|usd", s, re.I) or "원" in s:
        return None, ("척당" if "척당" in s else ("총액" if "총" in s else ""))
    basis = "척당" if "척당" in s else ("총액" if ("총" in s or "합계" in s) else "")
    won = s.replace(",", "")
    eok = re.search(r"([\d.]+)\s*억", won)
    man = re.search(r"([\d.]+)\s*만", won)
    usd = (float(eok.group(1)) * 1e8 if eok else 0) + (float(man.group(1)) * 1e4 if man else 0)
    if not eok and not man:
        n = re.search(r"([\d.]+)", won)
        if n:
            usd = float(n.group(1)) * 1e6
    return (round(usd / 1e6, 1), basis) if usd else (None, basis)


def clean(v):
    v = (v or "").strip()
    return "" if v in ("-", "nan", "None") else v


def to_order(no, it, d):
    """목록 항목 + 상세 → 공개 JSON의 order 한 건(aggregate_asiasis_orders.py 출력과 같은 모양)."""
    builder_raw = d.get("Builder") or it.get("builder", "")
    canon, nat = classify(builder_raw)
    price_m, basis = parse_price(d.get("Price ($m)", ""))
    vtype = norm_vessel(d.get("Vessel Type", ""))
    report = norm_date(d.get("Reported Date", ""), it.get("date", ""))
    # 원문 연도 오타 방어: 범위 밖이면 목록의 게시일을 쓴다(로컬은 이웃 bbs_no로 보정 — 새 글엔 게시일이 가장 가깝다)
    y = int(report[:4]) if re.match(r"\d{4}-\d{2}-\d{2}$", report) else 0
    if not (2013 <= y <= date.today().year + 1) and re.match(r"\d{4}-\d{2}-\d{2}$", it.get("date", "")):
        report = it["date"]
    count = re.search(r"(\d+)", d.get("No", "") or "")
    return {
        "report_date": report,
        "title": clean(d.get("제목") or it.get("title", "")),
        "vessel_type": vtype,
        "category": vtype if vtype in CANON_CATEGORIES else "기타",
        "vessel_type_raw": clean(d.get("Vessel Type", "")),
        "size": clean(d.get("Size", "")),
        "delivery": clean(d.get("Delivery", "")),
        "delivery_year": (re.search(r"(20\d{2})", d.get("Delivery", "") or "") or [None, ""])[1],
        "builder": clean(canon),
        "nationality": nat or "미상",
        "buyer": clean(d.get("Buyer", "")),
        "count": int(count.group(1)) if count else None,
        "price_m": price_m,
        "price_basis": basis,
        "price_raw": clean(d.get("Price ($m)", "")),
        "url": VIEW_URL.format(no=no),
    }


def run():
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    orders = doc["orders"]
    seen = {m.group(1) for o in orders for m in [re.search(r"bbs_no=(\d+)", o.get("url", ""))] if m}
    print(f"  기존 {len(orders):,}건 (bbs_no {len(seen):,}개)")

    new = []
    for pg in range(1, MAX_PAGES + 1):
        items = parse_list(pg)
        if not items:
            # 사이트 불통이면 첫 페이지부터 빈다 — 아무것도 쓰지 않고 끝낸다(기존 데이터 보존)
            print(f"  pagenum={pg}: 목록을 못 읽음 — 중단")
            break
        fresh = [it for it in items if it["bbs_no"] not in seen]
        for it in fresh:
            d = parse_detail(it["bbs_no"])
            if not d.get("제목") and not d.get("Vessel Type"):
                print(f"    상세 실패 bbs_no={it['bbs_no']} — 다음 실행에서 재시도")
                continue
            new.append(to_order(it["bbs_no"], it, d))
            seen.add(it["bbs_no"])
            time.sleep(0.35)  # 서버 배려(로컬 크롤러와 같은 간격)
        print(f"  pagenum={pg}: 신규 {len(fresh)}건")
        if not fresh:
            break  # 이 페이지가 전부 기존 글이면 더 과거는 볼 필요 없다
        time.sleep(0.3)

    if not new:
        print("  새 글 없음 — 파일 유지")
        return
    orders = sorted(orders + [o for o in new if re.match(r"\d{4}-\d{2}-\d{2}$", o["report_date"])],
                    key=lambda o: o["report_date"], reverse=True)
    nat_freq = Counter(o["nationality"] for o in orders)
    cat_freq = Counter(o["category"] for o in orders if o["category"])
    doc["orders"] = orders
    doc["nationalities"] = [n for n, _ in nat_freq.most_common()]
    doc["categories"] = [c for c, _ in cat_freq.most_common() if c != "기타"] + (
        ["기타"] if "기타" in cat_freq else [])
    doc["updated"] = orders[0]["report_date"]
    doc["fetched"] = date.today().isoformat()
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  +{len(new)}건 → 총 {len(orders):,}건 (~{doc['updated']})")


if __name__ == "__main__":
    run()
