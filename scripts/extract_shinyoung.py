# -*- coding: utf-8 -*-
"""신영증권 「조선/운송 위클리」 PDF에서 주간 데이터 추출 → data/ JSON 머지.

로컬 전용 스크립트 (PDF가 레포지토리 밖에 있으므로 CI에서는 실행 안 됨).
새 위클리 PDF를 폴더에 넣은 뒤 실행하고 커밋하면 대시보드에 반영된다.

    python scripts/extract_shinyoung.py

각 레포트에는 표마다 (전주, 금주) 2개 주간 컬럼이 있어, 전체 레포트를 겹치며
머지하면 끊김 없는 주간 시계열이 된다.

추출 대상 (표 앵커 텍스트 기준):
- 신조선가 동향        → shipbuilding/newbuild_prices.json + clarksons_nb_index.json
- 신조선 발주량        → shipbuilding/newbuild_orders.json (연초누적 척수)
- 중고선가 동향        → shipbuilding/secondhand_prices.json + secondhand_index.json
- 선종별 해상운임 추이 → shipping/tanker_earnings, bulker_earnings, gas_earnings, clarksea
- 1페이지 요약 텍스트  → 종합 중고선가지수 (secondhand_index.json)
"""
import re
import sys
from datetime import datetime
from pathlib import Path

import fitz  # PyMuPDF

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import load_indicator, merge_points, save_indicator, to_float

PDF_DIR = Path(r"C:\Users\공도일\Desktop\증권사레포트\조선")

UNITS = {"dwt", "cbm", "teu", "ceu", "pt", "$/day"}
TREND = {"FIRM", "FIRM!!", "FIRMER", "FIRMER!!", "WEAK", "WEAK!!", "STEADY", "STEADY!!"}
SIZE_RE = re.compile(r"^\d{1,3}(,\d{3})*~?$|^\d{3,6}~?$")
NUM_RE = re.compile(r"^-?\d{1,3}(,\d{3})*(\.\d*)?$")  # '176.' 같은 끝점 잘림 허용
PCT_RE = re.compile(r"^-?\d+(\.\d+)?%$")
DATE_RE = re.compile(r"\b(\d{1,2})-([A-Za-z]{3})\s*-?\s*(\d{2,4})\b")

MONTHS = {m: i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}


def parse_header_dates(tokens_joined: str):
    """헤더 행에서 날짜 컬럼들을 찾아 ISO 문자열 리스트로 반환.

    '3-Jul-2026' / '3-Jul-26' / '3-Jul -26'(공백 변형) 모두 처리.
    공백을 전부 제거하면 옆 컬럼 날짜와 붙어 연도가 오염되므로(예: '-26 10-Jul' → '2610')
    공백을 유지한 채 토큰 경계로 매칭한다.
    """
    out = []
    for d, mon, y in DATE_RE.findall(tokens_joined):
        if mon not in MONTHS:
            continue
        year = int(y)
        year += 2000 if year < 100 else 0
        if not (2020 <= year <= 2035) or not (1 <= int(d) <= 31):
            continue
        out.append(f"{year:04d}-{MONTHS[mon]:02d}-{int(d):02d}")
    return out


TREND_RE = re.compile(r"^[A-Z]{3,}!{0,2}$")  # FIRMER!!, WEAK!!, STEADY ...


def parse_data_row(tokens):
    """행 토큰 → (라벨, 사이즈, 값 리스트). 뒤에서부터 %/추세어 제거 후 말미 숫자 런 추출.

    표가 페이지 왼쪽 단에 있으면 오른쪽 본문 텍스트가 행 끝에 붙는다. 값들 뒤에
    오는 추세어/% 토큰(발주량 표의 마지막 컬럼)에서 행을 절단해 본문을 떼어낸다.
    (라벨의 'TOTAL' 같은 대문자 토큰과 혼동하지 않도록 숫자 2개 이상 지난 뒤부터만)
    """
    toks = [t for t in tokens if t.strip()]
    numeric_seen = 0
    for i, t in enumerate(toks):
        if NUM_RE.match(t):
            numeric_seen += 1
        elif numeric_seen >= 2 and (PCT_RE.match(t) or TREND_RE.match(t)):
            toks = toks[:i]
            break
    while toks and (PCT_RE.match(toks[-1]) or toks[-1] in TREND):
        toks.pop()
    vals = []
    while toks and NUM_RE.match(toks[-1]):
        vals.insert(0, to_float(toks.pop()))
    size = None
    while toks and (toks[-1] in UNITS or SIZE_RE.match(toks[-1])):
        t = toks.pop()
        if t not in UNITS:
            size = t
    label = " ".join(toks).strip()
    return label, size, vals


def find_table(doc, anchor):
    """anchor(표 제목)가 있는 페이지에서 제목 아래 ~ '자료:' 위 구간의 행들을 반환.

    페이지가 2단 구성(왼쪽 본문 + 오른쪽 표)이라 y좌표만으로 행을 묶으면 본문
    텍스트가 라벨에 섞인다. 제목 rect의 x0를 표의 왼쪽 경계로 삼아 그보다 왼쪽
    단어를 버린다.
    """
    for page in doc:
        rects = page.search_for(anchor)
        if not rects:
            continue
        r = rects[0]
        words = [w for w in page.get_text("words")
                 if w[1] > r.y1 - 1 and w[0] > r.x0 - 20]
        # y좌표 클러스터링으로 행 재구성
        words.sort(key=lambda w: (w[1], w[0]))
        rows, cur, cur_y = [], [], None
        for w in words:
            if cur_y is None or abs(w[1] - cur_y) <= 3:
                cur.append(w)
                cur_y = w[1] if cur_y is None else cur_y
            else:
                rows.append(cur)
                cur, cur_y = [w], w[1]
        if cur:
            rows.append(cur)
        out = []
        for row in rows:
            toks = [x[4] for x in sorted(row, key=lambda t: t[0])]
            if "".join(toks).startswith("자료"):
                break
            out.append((row[0][1], toks))
        return out
    return None


def extract_table(doc, anchor):
    """표 → (dates[-2:], [(라벨, 사이즈, [전주값, 금주값] 또는 None), ...] 순서 유지).

    값 없는 행(섹션 헤더 'Tanker'/'Bulker' 등)도 vals=None으로 포함시켜
    소비 측에서 섹션 추적에 쓸 수 있게 한다.
    """
    rows = find_table(doc, anchor)
    if not rows:
        return None, []
    dates = []
    data = []
    for _, toks in rows:
        if not dates:
            dates = parse_header_dates(" ".join(toks))
            if dates:
                continue
        label, size, vals = parse_data_row(toks)
        if not label:
            continue
        data.append((label, size, vals[-2:] if len(vals) >= 2 else None))
    return dates[-2:] if len(dates) >= 2 else None, data


def norm_sh(label: str) -> str:
    """중고선가 라벨 정규화: 'VLCC 5Yr 중고'/'Capesize 5 Yr 중고' → 'VLCC 5Y' 등."""
    s = label.replace("D/H", "").replace("중고", "")
    s = re.sub(r"5\s*Yr", "5Y", s)
    s = re.sub(r"\b[\d,~/.]+\b", "", s)  # 라벨에 섞여든 사이즈 토큰('60~61,000' 등) 제거
    return re.sub(r"\s+", " ", s).strip()


# ── 지표별 시리즈 매핑 ──────────────────────────────────────────────
NB_MAP = {
    "VLCC": "VLCC", "Suezmax": "수에즈막스", "Aframax": "아프라막스", "'MR' Tanker": "MR탱커",
    "Capesize": "케이프사이즈", "Panamax": "파나막스", "Handymax": "핸디막스", "Handysize": "핸디사이즈",
    "LPG": "LPG선(91k)", "LNG": "LNG선(174k)", "Pure Car Carriers": "PCC(자동차운반선)",
}
# 발주량 표는 라벨 표기가 리포트마다 조금씩 달라 접두어로 매칭
ORDER_PREFIX = [
    ("TOTAL", "합계"), ("Oil Tanker", "유조선"), ("Chemical", "케미컬/특수선"),
    ("LPG", "LPG선"), ("LNG", "LNG선"), ("Bulk", "벌커"),
    ("Container", "컨테이너선"), ("Offshore", "해양선박"),
]
FREIGHT_TANKER = {"VLCC": "VLCC", "Suezmax": "수에즈막스", "Aframax": "아프라막스",
                  "'MR' PC": "MR탱커", "Handy PC": "핸디 클린탱커"}
FREIGHT_BULKER = {"Capesize": "케이프사이즈", "Panamax": "파나막스", "Supramax": "수프라막스"}
FREIGHT_GAS = {"VLGC(미주-동아시아)": "VLGC 미주-동아시아", "VLGC(중동-동아시아)": "VLGC 중동-동아시아",
               "174k cbm LNG": "LNG 174k",
               # 과거 리포트의 구기준 벤치마크 (연속성이 없어 별도 시리즈로 유지)
               "84k cbm LPG": "VLGC(84k, 구기준)", "160k cbm LNG": "LNG 160k(구기준)"}


def container_key(size):
    n = int(re.sub(r"\D", "", size or "0"))
    if n >= 20000:
        return "컨테이너선 23k TEU"
    if n >= 10000:
        return "컨테이너선 13k TEU"
    return "컨테이너선 2.8k TEU"


def apply(doc_json, dates, pairs):
    """{시리즈명: [v1, v2]} + [d1, d2] → 머지."""
    for name, vals in pairs.items():
        merge_points(doc_json, name, list(zip(dates, vals)))


def extract_pdf(path, out):
    """out: dict of indicator-id → doc-json (미리 로드됨)"""
    doc = fitz.open(path)
    hit = []

    # 1) 신조선가
    dates, data = extract_table(doc, "신조선가 동향(단위")
    if dates and data:
        hit.append("신조선가")
        pairs = {}
        for label, size, vals in data:
            if vals is None:
                continue
            if label == "Container":
                pairs[container_key(size)] = vals
            elif label in NB_MAP:
                pairs[NB_MAP[label]] = vals
            elif "Newbuilding Price" in label:
                apply(out["clarksons_nb_index"], dates, {"신조선가지수": vals})
        apply(out["newbuild_prices"], dates, pairs)

    # 2) 발주량 (연초누적 척수)
    d2, data = extract_table(doc, "신조선 발주량(단위")
    if d2 and data:
        hit.append("발주량")
        pairs = {}
        for label, size, vals in data:
            if vals is None:
                continue
            for prefix, name in ORDER_PREFIX:
                if label.startswith(prefix):
                    pairs[name] = vals
                    break
        apply(out["newbuild_orders"], d2, pairs)

    # 3) 중고선가 (섹션 추적: Tanker/Bulker 양쪽에 Panamax가 있어 구분 필요.
    #    Container 섹션은 포맷 변동이 잦아 제외)
    d3, data = extract_table(doc, "중고선가 동향(단위")
    if d3 and data:
        hit.append("중고선가")
        pairs, idx = {}, {}
        section = ""
        for label, size, vals in data:
            n = norm_sh(label)
            if vals is None:
                for sec in ("Tanker", "Bulker", "Container"):
                    if n.startswith(sec):
                        section = sec
                continue
            if not n:
                continue
            if "Secondhand Index" in n:
                who = "탱커 중고선가지수" if "Tanker" in n else "벌커 중고선가지수"
                idx[who] = vals
            elif n.startswith("Secondhand Price"):
                idx["중고선가지수(종합)"] = vals
            elif section == "Container":
                continue
            elif section == "Tanker" and n.startswith("Panamax"):
                pairs[n.replace("Panamax", "Panamax(탱커)")] = vals
            else:
                pairs[n] = vals
        apply(out["secondhand_prices"], d3, pairs)
        apply(out["secondhand_index"], d3, idx)

    # 4) 해상운임
    d4, data = extract_table(doc, "선종별 해상운임 추이(단위")
    if d4 and data:
        hit.append("해상운임")
        tk, bk, gs = {}, {}, {}
        for label, size, vals in data:
            if vals is None:
                continue
            if label in FREIGHT_TANKER:
                tk[FREIGHT_TANKER[label]] = vals
            elif label in FREIGHT_BULKER:
                bk[FREIGHT_BULKER[label]] = vals
            elif label in FREIGHT_GAS:
                gs[FREIGHT_GAS[label]] = vals
            elif "ClarkSea" in label:
                apply(out["clarksea"], d4, {"ClarkSea Index": vals})
        apply(out["tanker_earnings"], d4, tk)
        apply(out["bulker_earnings"], d4, bk)
        apply(out["gas_earnings"], d4, gs)

    doc.close()
    return hit


META = {
    # industry, id: (name, unit, default_series)
    ("shipbuilding", "clarksons_nb_index"): ("클락슨 신조선가 지수", "pt", ["신조선가지수"]),
    ("shipbuilding", "newbuild_prices"): ("선종별 신조선가", "M$", ["LNG선(174k)", "VLCC", "컨테이너선 23k TEU", "케이프사이즈"]),
    ("shipbuilding", "newbuild_orders"): ("신조선 발주량 (연초누적)", "척", ["합계"]),
    ("shipbuilding", "secondhand_prices"): ("선종별 중고선가", "M$", ["VLCC 5Y", "Capesize 5Y"]),
    ("shipbuilding", "secondhand_index"): ("클락슨 중고선가 지수", "pt", ["중고선가지수(종합)"]),
    ("shipping", "tanker_earnings"): ("탱커 운임 (Average Earnings)", "USD/day", ["VLCC"]),
    ("shipping", "bulker_earnings"): ("벌커 운임 (Average Earnings)", "USD/day", ["케이프사이즈"]),
    ("shipping", "gas_earnings"): ("가스선 운임 (VLGC·LNG)", "USD/day", ["LNG 174k"]),
    ("shipping", "clarksea"): ("ClarkSea Index (종합 해운운임)", "USD/day", ["ClarkSea Index"]),
}


def run():
    pdfs = sorted(PDF_DIR.glob("*.pdf"))
    if not pdfs:
        print(f"PDF 없음: {PDF_DIR}")
        return

    out = {}
    for (industry, ind_id), (name, unit, default) in META.items():
        d = load_indicator(industry, ind_id)
        d.update({
            "name": name, "unit": unit, "frequency": "weekly",
            "source": "신영증권 조선/운송 위클리 (원자료: 클락슨)",
            "source_url": "", "default_series": default,
        })
        d.pop("manual", None)
        out[ind_id] = d

    ok, bad = 0, []
    for p in pdfs:
        try:
            hit = extract_pdf(p, out)
            if len(hit) >= 3:
                ok += 1
            else:
                bad.append((p.name, hit))
        except Exception as e:
            bad.append((p.name, f"ERROR {e}"))

    for (industry, ind_id), _ in META.items():
        save_indicator(industry, out[ind_id])

    print(f"\n{ok}/{len(pdfs)}개 레포트에서 3개 표 이상 추출 성공")
    if bad:
        print("표가 일부만 추출된 파일:")
        for name, hit in bad:
            print(f"  {name}: {hit}")


if __name__ == "__main__":
    run()
