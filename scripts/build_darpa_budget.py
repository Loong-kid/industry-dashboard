"""🛰️ DARPA 예산(RDT&E Volume 1 Justification Book, PB FY2016~) → data/darpa/budget.json.

예산서 PDF는 국방부 회계감사관(comptroller.defense.gov)이 해마다 2~4월 한 번 내므로 매일 수집에 넣지 않는다.
새 예산서가 나오면 PDF를 한 폴더에 받아 두고 다시 만든다:
    python scripts/build_darpa_budget.py --pdf-dir "%USERPROFILE%/Downloads"

읽는 것
- 'COST ($ in Millions)' 표: 프로그램 요소(PE)·프로젝트별 금액(전전년 실적, 전년, 요청 연도).
- 'B. Accomplishments/Planned Programs'의 'Title:' 행: 프로그램별 금액. 숫자는 글자 위치로 연도 열에 맞춘다.
  (본문 텍스트 순서로 읽으면 숫자가 설명 뒤로 밀려 엉뚱한 프로그램에 붙는다)
- 프로젝트 합계와 프로그램 합계의 차이: 기밀(SAP) 프로젝트·지원비 프로젝트·의회 증액분(Congressional Adds)을 별도 행으로 둔다.
  그래서 연도별 분야 합계 = DARPA 총액이 된다(test_darpa_budget.py가 확인).

분야는 공식 분류가 아니다. PB2026에 DARPA가 PE·프로젝트 체계를 통째로 바꿔 공식 코드로는 FY2025↔2026이 이어지지 않으므로,
프로그램 제목·설명 키워드 + 소속 프로젝트로 산업 분야를 붙이고(SECTOR_RULES), 틀린 것은 SECTOR_FIX로 바로잡았다.
"""
import argparse
import json
import os
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "darpa" / "budget.json"

SECTORS = [
    ("ai", "인공지능"), ("compute", "컴퓨팅·수학·데이터"), ("cyber", "사이버보안"), ("micro", "반도체·전자"),
    ("quantum", "양자"), ("bio", "바이오·의료"), ("materials", "소재·제조·에너지"), ("space", "우주"),
    ("aero", "항공·극초음속"), ("maritime", "해양·수중"), ("ground", "지상·로봇·자율"), ("sensors", "센서·전자전·항법"),
    ("comms", "통신·네트워크·지휘통제"), ("weapons", "타격·방어 무기"), ("human", "인간·사회·인재"), ("explore", "범분야 탐색 연구"),
    ("classified", "기밀 프로그램"), ("support", "운영·지원"),
]
BUDGET_ACTIVITY = {"0601": "기초연구", "0602": "응용연구", "0603": "첨단기술개발", "0605": "관리·지원"}

# 소속 프로젝트(구 코드·PB2026 신 코드)의 기본 분야. 제목·설명 키워드 점수에 가산점으로만 쓴다.
PROJECT_SECTOR = {
    **dict.fromkeys(["CCS-02", "EMR-01", "IT-02", "TT-13", "CCC-02"], "compute"),
    **dict.fromkeys(["CYS-01", "IT-03", "IT-05", "CCC-05", "MSL-04", "AET-03", "CCC-04"], "cyber"),
    **dict.fromkeys(["ES-01", "ES-02", "ELT-01", "ELT-02", "MT-12", "MT-15", "MT-16", "MSL-02", "MSL-03", "AET-02", "EMR-02"], "micro"),
    **dict.fromkeys(["MS-01", "EMR-03", "MBT-01", "MSL-01"], "materials"),
    **dict.fromkeys(["MED-01", "EMR-04", "BT-01", "WP-02", "BW-01", "MBT-02", "WP-01", "BLS-01"], "bio"),
    **dict.fromkeys(["IT-04", "MSL-05", "COG-02", "COG-03"], "ai"),
    **dict.fromkeys(["TT-03", "NET-02"], "maritime"),
    **dict.fromkeys(["TT-04", "ACS-01"], "ground"),
    **dict.fromkeys(["TT-06", "TT-07", "AIR-01", "ACX-01"], "aero"),
    **dict.fromkeys(["SPC-01"], "space"),
    **dict.fromkeys(["SEN-01", "SEN-02", "SEN-03", "DAT-02"], "sensors"),
    **dict.fromkeys(["CCC-06", "NET-01", "NET-06", "SEN-06", "AET-01", "DAT-01", "MSL-06", "MSL-07"], "comms"),
    **dict.fromkeys(["MQB-01"], "quantum"), **dict.fromkeys(["EFF-01"], "weapons"), **dict.fromkeys(["TRS-01"], "human"),
    **dict.fromkeys(["MST-01", "MH-01", "SB-01"], "support"),
}
# 위에서부터 우선. 제목에서 걸리면 5점, 설명(앞 700자)에서 걸리면 1점씩(최대 6).
SECTOR_RULES = [
    ("quantum", r"quantum|qubit"),
    ("ai", r"artificial intelligence|\bai\b|machine learning|deep learning|neural net|explainab|\bcognitiv|common sense|reasoning|human-machine|machine (?:teaming|reading)|autonomous (?:agents|learning)|lifelong learning|trust(?:ed)? (?:ai|autonomy)"),
    ("cyber", r"cyber|malware|exploit|vulnerab|software (?:security|assurance)|binary|intrusion|secure (?:hardware|software|network)|attack"),
    ("micro", r"microelectron|semiconductor|\bchips?\b|integrated circuit|photonic|transistor|heterogeneous integration|beyond scaling|microsystem|\bmems\b|electronics|\brf\b|millimeter|wafer|3d (?:soc|integration)|packaging|analog|fpga|asic|optoelectron"),
    ("bio", r"\bbio|medic|health|disease|pathogen|vaccin|\bneuro|brain|genom|gene\b|genetic|injur|pandemic|\bcell|protein|synthetic biolog|mass terror|immun|infect|wound|trauma|prosthe|microb|biolog"),
    ("space", r"\bspace|satellite|orbit|cislunar|launch|lunar|\bgeo\b|spacecraft"),
    ("aero", r"aircraft|aerial|air vehicle|hypersonic|glide|engine|airbreathing|air-breathing|x-plane|vtol|take-off|flight|airframe|\bwing|aero|rotorcraft|\buav|\buas\b|drone|seaplane|lifter|air combat|helicopter"),
    ("maritime", r"maritime|undersea|naval|\bship|submarine|ocean|\bsea\b|vessel|underwater|anti-submarine|\buuv|\busv|marine|harbor|littoral|propulsor|manning"),
    ("ground", r"ground|robot|squad|\bland\b|urban|infantry|off-road|legged|tunnel|subterranean|soldier"),
    ("sensors", r"sensor|sensing|imag|radar|\bisr\b|surveillance|navigation|\bpnt\b|positioning|timing|clock|detect|optical|electronic warfare|countermeasure|lidar|infrared|camera|inertial|gps|targeting|tracking|reconnaissance"),
    ("comms", r"communicat|network|command and control|\bc2\b|\bc3|\bc4|spectrum|wireless|data link|mosaic|battle management|system of systems|interoperab|tactical edge|logistic|wargam|decision"),
    ("weapons", r"weapon|munition|\bfires\b|missile|intercept|strike|directed energy|counter-uas|counter-unmanned|explosive|precision guid|effects|kinetic|projectile|warhead|gun"),
    ("materials", r"material|manufactur|chemi|molecul|polymer|metal|additive|structur|fabricat|synthesis|coating|composite|energy|power|nuclear|batter|fuel|fusion|reactor"),
    ("compute", r"comput|software|\bmath|data|analytic|algorithm|programming|compiler|high performance|processor|graph|formal method|modeling|simulation"),
    ("human", r"social|behavior|language|narrative|influence|population|cultur|human|people|teaming|training|education|young faculty"),
]
# 규칙이 틀린 프로그램: 제목 앞부분(영숫자만 비교) → 분야. 2026-11-02 810개 제목을 훑어 고쳤다.
SECTOR_FIX = {
    "bio": ["Food and Feedstocks on Demand", "Restoring Cognitive Capability", "Warfighter Analytics using Smartphones", "Defend Against Crop", "In vivo Nanoplatforms",
            "Engineered Living Materials", "Reengineering Enabling Sleep", "Accelerated Agricultural", "Blast Exposure Accelerated",
            "Living Foundries", "Decoding Neural Activity", "Human Assisted Neural"],
    "human": ["Young Faculty Award", "Open Price Exploration", "National Security Economic Theory", "Computational Cultural Understanding",
              "Competition in the Information Environment", "Analytics and Adaptation of Human Resilience", "Improved Personnel Placement",
              "Objective Prediction of Team", "Competing in Undergoverned"],
    "compute": ["Anticipatory and Adaptive Anti-money", "Engineering Complex Systems"],
    "quantum": ["Quantum Inspired Classical", "Quantum Imaging of Vector", "Underexplored Systems for Utility-Scale Quantum"],
    "ai": ["RF Machine Learning Systems", "Human-Machine Symbiosis", "Control System Introspection", "Learning Autonomy in Synthetic", "Semantic Forensics", "Media Forensics", "Perceptually-Enabled Task", "Communicating With Computers", "Data-Driven Discovery",
           "Learning with Less", "Environment-driven Conceptual", "Understanding Machine Intelligence", "Probabilistic Programming",
           "In The Moment", "Modular Meta-cognition", "Strategic Chaos Engine", "Autonomy Standards and Ideals", "Low Resource Languages",
           "Stylized Language Processing", "Broad Operational Language"],
    "cyber": ["Brandeis", "Edge-Directed Cyber", "Securing Information for Encrypted", "SafeWare", "Intrinsic Cognitive Security", "Computers and Humans Exploring Software", "Vetting Commodity Computing", "Transparent Computing",
              "System Security Integrated Through", "Securing the Software Supply", "Analyzing Software to Protect", "Safe Documents",
              "Data Privacy", "Translating All C To Rust", "Enhanced SBOM", "Compartmentalization and Privilege", "Continuous-correctness",
              "Guaranteed Architectures for Physical", "Leveraging the Analog Domain", "Critical Infrastructure Defense",
              "Faithful Integration Reverse", "Active Social Engineering", "Hardening Development Toolchains", "Provably Weird",
              "Anomaly Detection at Multiple"],
    "comms": ["Adapting Cross-domain Kill", "Dynamic Airspace Control", "Mobile Hotspots", "Open, Programmable, Secure 5G",
              "Air Space Total Awareness", "Scalable Optical Nodes", "Portable Optical Integrated Network"],
    "micro": ["Programmable Logic for Applications", "Hierarchical Identify Verify Exploit", "FLASH - Scaling Fiber", "Power Efficiency Revolution", "Electronic Globalization", "Unconventional Processing of Signals", "Removing Barriers to Hardware",
              "Cortical Processor", "Structured Array Hardware", "Ferroelectric Computing", "Lasers for Universal Microscale",
              "NanoWatt Platforms", "Supply Chain & Logistics in Electronic"],
    "materials": ["Making, Maintaining, Supply Chains and Logistics Studies", "Instant Foundry", "Microsystem Induced", "Fundamentals of Nanoscale", "Process Intensified Energetics",
                  "Rubble to Rockets", "21st Century Propellants", "Atmospheric Water Extraction", "Wireless Autonomous Vehicle Power"],
    "maritime": ["Mobile Offboard Command", "Disaggregated Strike Group"],
    "aero": ["Collaborative Operations in Denied", "Advanced Aeronautics and Space", "Tactically Exploited Reconnaissance Node", "Hybrid Multi Material Rotor"],
    "sensors": ["Precise Robust Inertial Guidance", "Intelligent Spectroscopic", "LUSTER", "Laser Ultraviolet Sources"],
    "weapons": ["Counter High Energy Lasers", "High Energy Liquid Laser", "CounterSwarmAI", "Counter Unmanned Air Systems", "Kinetic Delivery",
                "Long Range Anti-Ship Missile", "Mobile Force Protection", "Assault Breaker"],
    "ground": ["Systems of Systems-Enhanced Small Units"],
    "support": ["Embedded Entrepreneurship"],
    # PB2026 개편 뒤 생긴 범용 탐색 예산(특정 분야 없이 새 사업 씨앗으로 쓰는 Studies and Concepts)
    "explore": ["Advanced Systems Studies and Concepts", "Advanced Complex Systems Studies and Concepts"],
}
SECTOR_FIX_EXACT = {"meta": "materials"}  # 'META'는 앞부분 비교로 다른 제목을 잡지 않게 정확히 비교

NUM = re.compile(r"^-?\d[\d,]*\.\d{3}$|^-$")
PAGE_FURNITURE = re.compile(r"^(UNCLASSIFIED|PE \d{7}|Defense Advanced Research|Page \d|Volume \d|R-1 Line|Exhibit R-)")


def norm(text):
    return re.sub(r"[^a-z0-9]", "", text.lower())


def find_books(pdf_dir):
    import pymupdf
    books = {}
    for path in sorted(Path(pdf_dir).glob("*.pdf")):
        if "DARPA" not in path.name.upper():
            continue
        doc = pymupdf.open(path)
        head = "".join(doc[i].get_text() for i in range(min(3, len(doc))))
        m = re.search(r"Fiscal Year \(FY\) (20\d\d)", head) or re.search(r"(?:FY|Fiscal Year) ?(20\d\d) Budget Estimates", head)
        if m and "Defense Advanced Research Projects Agency" in head:
            books[int(m.group(1))] = path
    return books


# ── 'COST ($ in Millions)' 표 ──
def _is_val(s):
    s = s.strip().rstrip("#*^ ").strip()
    return bool(re.match(r"^-?\d[\d,]*\.\d+$|^-$|^Continuing$", s))


def _val(s):
    s = s.strip().rstrip("#*^ ").strip()
    if s in ("-", "", "Continuing"):
        return 0.0
    return float(s.replace(",", ""))


def parse_cost_tables(text):
    """→ {('PE', pe) | (pe, project): {'name', 'cols': {col: value}}}; col = '2024', '2026t'(요청 연도 합계) …"""
    lines = [l.strip() for l in text.split("\n")]
    out, pe, pename = {}, None, ""
    for i, line in enumerate(lines):
        m = re.match(r"^PE (\d{7}E) ?/ ?(.*)", line)
        if m:
            pe, pename = m.group(1), m.group(2)
        if line != "COST ($ in Millions)":
            continue
        j, hdr = i + 1, []
        while j < len(lines) and not (":" in lines[j] or lines[j].startswith("Total Program Element")):
            hdr.append(lines[j]); j += 1
        cols, k = [], 0
        while k < len(hdr):
            h = hdr[k]
            nxt = hdr[k + 1] if k + 1 < len(hdr) else ""
            if h == "Prior":
                cols.append("prior"); k += 2
            elif h.startswith("FY ") and nxt in ("Base", "OCO", "OOC", "Total"):
                cols.append(h[3:] + {"Base": "b", "OCO": "o", "OOC": "o", "Total": "t"}[nxt]); k += 2
            elif h.startswith("FY "):
                cols.append(h[3:]); k += 1
            elif h in ("Cost To", "Total"):
                cols.append("ctc" if h == "Cost To" else "total"); k += 2
            else:
                k += 1
        while j < len(lines):
            label = []
            while j < len(lines) and not _is_val(lines[j]) and not lines[j].startswith(("A. Mission", "Note")):
                label.append(lines[j]); j += 1
            if j >= len(lines) or not _is_val(lines[j]):
                break
            vals = []
            while j < len(lines) and _is_val(lines[j]) and len(vals) < len(cols):
                vals.append(_val(lines[j])); j += 1
            lab = re.sub(r"\s*(Quantity of RDT&E Articles|Program MDAP/MAIS Code:.*)$", "", " ".join(label)).strip()
            row = dict(zip(cols, vals))
            m = re.match(r"^([A-Z]{1,4}-\d{2}[A-Z]?):\s*(.*)", lab)
            if lab.startswith("Total Program Element"):
                out.setdefault(("PE", pe), {"name": re.sub(r"\s+", " ", pename).strip(), "cols": row})
            elif m:
                out.setdefault((pe, m.group(1)), {"name": re.sub(r"\s+", " ", m.group(2)).strip(), "cols": row})
    return out


def col_value(cols, fy, request_year):
    if fy == request_year:
        for key in (f"{fy}t", f"{fy}", f"{fy}b"):
            if key in cols:
                return cols[key]
        return 0.0
    return cols.get(str(fy), 0.0)


# ── 'Title:' 프로그램 행 (글자 위치) ──
def _page_lines(page):
    out = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            text = "".join(s["text"] for s in line["spans"]).strip()
            if text:
                x0, y0, x1, y1 = line["bbox"]
                out.append((x0, y0, x1, text))
    out.sort(key=lambda r: (round(r[1]), r[0]))
    return out


def parse_programs(doc):
    progs, mission = [], {}
    pe = None
    for pno, page in enumerate(doc):
        text = page.get_text()
        m = re.search(r"PE (\d{7}E) ?/", text)
        if m:
            pe = m.group(1)
        m2 = re.search(r"Project \(Number/Name\)\n([A-Z]{1,4}-\d{2}[A-Z]?) ?/", text)
        proj = m2.group(1) if m2 else None
        mm = re.search(r"A\. Mission Description and Budget Item Justification\n(.{0,600})", text, re.S)
        if mm and (proj or pe):
            mission.setdefault((pe, proj), mm.group(1))
        lines = _page_lines(page)
        heads = [(x0, x1, y0, int(t[3:])) for x0, y0, x1, t in lines if re.fullmatch(r"FY 20\d\d", t) and x0 > 450]
        for i, (x0, y0, x1, t) in enumerate(lines):
            if not t.startswith("Title:"):
                continue
            above = [h for h in heads if h[2] < y0]
            if not above:
                continue
            top = max(h[2] for h in above)
            cols = [h for h in above if abs(h[2] - top) < 15]
            vals = {}
            for a0, b0, a1, tt in lines:
                if a0 > 450 and abs(b0 - y0) < 3 and NUM.match(tt):
                    cx = (a0 + a1) / 2
                    h = min(cols, key=lambda h: abs((h[0] + h[1]) / 2 - cx))
                    vals[h[3]] = 0.0 if tt == "-" else float(tt.replace(",", ""))
            # 제목이 여러 줄이면 이어 붙이고, 이어서 설명을 읽는다. 오른쪽 금액 열(x>450)은 건너뛴다.
            title, k = t[6:].strip(), i + 1
            while k < len(lines):
                if lines[k][0] >= 450:
                    k += 1; continue
                if lines[k][3].startswith("Description") or lines[k][1] - y0 >= 40 or PAGE_FURNITURE.match(lines[k][3]):
                    break
                title += " " + lines[k][3]; k += 1
            desc = []
            while k < len(lines):
                if lines[k][0] >= 450:
                    k += 1; continue
                s = lines[k][3]
                if re.match(r"^(FY 20\d\d (Plans|Accomplishments)|Title:|Accomplishments/Planned)", s) or PAGE_FURNITURE.match(s):
                    break
                desc.append(s); k += 1
            progs.append({"pe": pe, "proj": proj, "title": re.sub(r"\s+", " ", title).strip(" *"), "vals": vals,
                          "desc": re.sub(r"\s+", " ", re.sub(r"^Description:\s*", "", " ".join(desc))).strip()})
    return progs, mission


def classify(title, desc, projects):
    n = norm(title)
    if n in SECTOR_FIX_EXACT:
        return SECTOR_FIX_EXACT[n]
    for sector, prefixes in SECTOR_FIX.items():
        if any(n.startswith(norm(p)) for p in prefixes):
            return sector
    if re.fullmatch(r"classified darpa programs?", title.strip().lower()):
        return "classified"
    if re.match(r"^(mission support|management headquarters|small business|facilities and infrastructure|accounting and audit)", title, re.I):
        return "support"
    score = defaultdict(float)
    t, d = title.lower(), desc.lower()[:700]
    for i, (sector, rx) in enumerate(SECTOR_RULES):
        nt, nd = len(re.findall(rx, t)), len(re.findall(rx, d))
        if nt or nd:
            score[sector] += nt * 5 + min(nd, 6) + 0.1 * (len(SECTOR_RULES) - i) / len(SECTOR_RULES)
    for p in projects:
        if PROJECT_SECTOR.get(p):
            score[PROJECT_SECTOR[p]] += 2.5
    return max(score, key=score.get) if score else "compute"


def short_desc(text, limit=340):
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    end = cut.rfind(". ")
    return cut[: end + 1] if end > 120 else cut.rstrip() + "…"


def acronym(title):
    m = re.search(r"\(([A-Za-z0-9][A-Za-z0-9\-²&]{1,14})\)\s*$", title)
    return m.group(1) if m else None


def build(pdf_dir):
    import pymupdf
    books = find_books(pdf_dir)
    if not books:
        raise SystemExit(f"{pdf_dir}에 DARPA 예산서 PDF가 없다")
    entries = []          # 책별 프로그램 행 (+ 차액 행)
    pe_series = defaultdict(lambda: {"name": "", "request": {}})
    book_meta = []
    for fy in sorted(books):
        doc = pymupdf.open(books[fy])
        text = "\n".join(p.get_text() for p in doc)
        date = re.search(r"Date: ([A-Z][a-z]+ 20\d\d)", text)
        book_meta.append({"fy": fy, "file": books[fy].name, "pages": len(doc), "date": date.group(1) if date else None,
                          "url": f"https://comptroller.defense.gov/Budget-Materials/Budget{fy}/"})
        costs = parse_cost_tables(text)
        progs, mission = parse_programs(doc)
        projects_of_pe = defaultdict(list)
        for (pe, code), row in costs.items():
            if pe == "PE":
                pe_series[code]["name"] = row["name"]
                pe_series[code]["request"][fy] = round(col_value(row["cols"], fy, fy), 3)
            else:
                projects_of_pe[pe].append(code)
        for p in progs:   # 프로젝트가 하나뿐인 PE의 R-2 쪽은 프로젝트 칸이 없다
            if not p["proj"] and len(projects_of_pe.get(p["pe"], [])) == 1:
                p["proj"] = projects_of_pe[p["pe"]][0]
            p["book"] = fy
            entries.append(p)
        # 프로젝트 합계 - 프로그램 합계 = 기밀·지원비·의회 증액분
        sums = defaultdict(float)
        for p in progs:
            for y, v in p["vals"].items():
                sums[(p["proj"], y)] += v
        for (pe, code), row in costs.items():
            if pe == "PE":
                continue
            for y in (fy - 2, fy - 1, fy):
                gap = round(col_value(row["cols"], y, fy) - sums.get((code, y), 0.0), 3)
                if abs(gap) < 0.05:
                    continue
                text_m = mission.get((pe, code)) or mission.get((pe, None)) or ""
                name = row["name"].title()
                if "classified DARPA programs" in text_m or code in ("DAT-06",):
                    title, kind = "Classified DARPA Program", "classified"
                elif code in ("MST-01", "MH-01", "SB-01") or name.lower().endswith("support"):
                    title, kind = f"{name} (지원비)", "support"
                elif y < fy:
                    title, kind = f"의회 증액분 — {name}", "adds"
                else:
                    title, kind = f"{name} (세부 미기재)", "other"
                entries.append({"pe": pe, "proj": code, "title": title, "vals": {y: gap}, "desc": "", "book": fy, "synthetic": kind})

    # ── 책을 넘어 같은 프로그램 묶기: 괄호 뺀 제목이 같거나, 약어가 같고 프로젝트가 겹치면 같은 것 ──
    parent = list(range(len(entries)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]; i = parent[i]
        return i

    by_key = {}
    for i, e in enumerate(entries):
        keys = ["t:" + norm(re.sub(r"\([^)]*\)", "", e["title"]))]
        ac = acronym(e["title"])
        if not ac and re.fullmatch(r"[A-Za-z][A-Za-z0-9\-]{2,11}", e["title"]):
            ac = e["title"]   # 'MoHAWC'처럼 약어만 제목인 해 ↔ 'More Opportunities with HAWC (MoHAWC)'
        if ac and not e.get("synthetic"):
            keys.append(f"a:{ac.upper()}:{PROJECT_SECTOR.get(e['proj']) or e['proj']}")
        if e.get("synthetic") == "classified":
            keys = ["classified"]
        for k in keys:
            if k in by_key:
                parent[find(i)] = find(by_key[k])
            else:
                by_key[k] = i
    groups = defaultdict(list)
    for i, e in enumerate(entries):
        groups[find(i)].append(e)

    years = list(range(min(books) - 2, max(books) + 1))
    programs = []
    for members in groups.values():
        members.sort(key=lambda e: e["book"])
        latest = members[-1]
        request, actual = defaultdict(float), defaultdict(float)
        for e in members:
            if e["book"] in e["vals"]:
                request[e["book"]] += e["vals"][e["book"]]
            if e["book"] - 2 in e["vals"]:
                actual[e["book"] - 2] += e["vals"][e["book"] - 2]
        funded = sorted(y for e in members for y, v in e["vals"].items() if v > 0)
        first_amount = None
        if funded:   # 첫해 금액은 그 해를 가장 늦게 다룬 예산서(실적 > 당해 추정 > 요청) 값
            seen = [e for e in members if funded[0] in e["vals"]]
            last_book = max(e["book"] for e in seen)
            first_amount = round(sum(e["vals"][funded[0]] for e in seen if e["book"] == last_book), 3)
        if not funded and not any(request.values()):
            continue
        projects = sorted({e["proj"] or e["pe"] for e in members})
        synthetic = latest.get("synthetic")
        if synthetic == "classified":
            sector = "classified"
        elif synthetic == "support":
            sector = "support"
        elif synthetic:
            sector = PROJECT_SECTOR.get(latest["proj"], "support")
        else:
            sector = classify(latest["title"], next((e["desc"] for e in reversed(members) if e["desc"]), ""), projects)
        programs.append({
            "title": "기밀 프로그램 (Classified DARPA Program)" if sector == "classified" else latest["title"],
            "acronym": acronym(latest["title"]),
            "sector": sector,
            "kind": synthetic or "program",
            "projects": projects,
            "books": sorted({e["book"] for e in members}),
            "first_fy": funded[0] if funded else None,
            "first_amount": first_amount,
            "last_fy": funded[-1] if funded else None,
            "request": {y: round(v, 3) for y, v in sorted(request.items()) if v},
            "actual": {y: round(v, 3) for y, v in sorted(actual.items()) if v},
            "desc": short_desc(next((e["desc"] for e in reversed(members) if e["desc"]), "")),
        })
    programs.sort(key=lambda p: (-sum(p["request"].values()), p["title"]))
    for i, p in enumerate(programs):
        p["id"] = i

    first_book = min(books)
    req_years = sorted(books)
    act_years = [y for y in years if y + 2 in books]
    sectors = []
    for sid, name in SECTORS:
        mine = [p for p in programs if p["sector"] == sid]
        sectors.append({
            "id": sid, "name": name,
            "request": {y: round(sum(p["request"].get(y, 0) for p in mine), 3) for y in req_years},
            "actual": {y: round(sum(p["actual"].get(y, 0) for p in mine), 3) for y in act_years},
            "count": {y: sum(1 for p in mine if p["request"].get(y, 0) > 0) for y in req_years},
        })
    for p in programs:   # 신규 = 처음 돈이 붙은 해가 첫 예산서 해 이후(그 전 해 실적이 보이므로 그 전부터 있던 것은 기존 사업)
        p["new_fy"] = p["first_fy"] if p["kind"] == "program" and p["sector"] != "support" and p["first_fy"] and p["first_fy"] >= first_book else None
    ba = defaultdict(lambda: defaultdict(float))
    for pe, s in pe_series.items():
        for y, v in s["request"].items():
            ba[BUDGET_ACTIVITY.get(pe[:4], "기타")][y] += v
    return {
        "source": "DoD RDT&E Budget Justification Volume 1, Defense Advanced Research Projects Agency (PB FY%d~FY%d)" % (min(books), max(books)),
        "books": book_meta,
        "unit": "백만 달러(USD M)",
        "years": {"request": req_years, "actual": act_years},
        "totals": {
            "request": {y: round(sum(s["request"][y] for s in sectors), 3) for y in req_years},
            "actual": {y: round(sum(s["actual"][y] for s in sectors), 3) for y in act_years},
        },
        "budget_activity": [{"name": k, "request": {y: round(v[y], 3) for y in req_years}} for k, v in ba.items()],
        "pes": [{"pe": pe, "name": s["name"], "request": s["request"]} for pe, s in sorted(pe_series.items())],
        "sectors": sectors,
        "programs": programs,
        "notes": [
            "요청액 = 그 해 예산서(PB)의 요청 연도 금액. 실적 = 2년 뒤 예산서의 전전년 열(의회 증액분 포함).",
            "분야는 DARPA 공식 분류가 아니라 프로그램 제목·설명·소속 프로젝트로 붙인 산업 분야다.",
            "PB2026부터 DARPA가 PE·프로젝트 체계를 개편했다. 같은 이름의 프로그램은 이어 붙였고, 이때 지원비가 별도 프로젝트로 빠져 '운영·지원'이 늘어 보인다.",
            "신규 = 금액이 처음 붙은 회계연도. 이름을 바꾼 사업이 신규로 잡히거나, 다른 사업에서 갈라져 나온 사업이 포함될 수 있다.",
        ],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf-dir", default=os.path.expanduser("~/Downloads"))
    args = ap.parse_args()
    doc = build(args.pdf_dir)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    tot = doc["totals"]["request"]
    print(f"{OUT.relative_to(ROOT)}: 예산서 {len(doc['books'])}권, 프로그램 {len(doc['programs'])}개, "
          f"요청액 FY{min(tot)} {tot[min(tot)]:,.0f} → FY{max(tot)} {tot[max(tot)]:,.0f} $M")


if __name__ == "__main__":
    main()
