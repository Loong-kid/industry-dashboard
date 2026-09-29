"""Build the institution directory from curated profiles, KOFIA snapshots and DART.

No network or extra dependencies. Preserve separate legal entities and historical
names; only legal-form markers and spelling separators are normalized.
"""
import csv
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANAGER = re.compile(r"자산운용|투자운용|신탁운용|리츠운용|투자자문|asset\s*management|investment\s*management|capital\s*management|fund\s*advisors|advisors", re.I)


def institution_key(name):
    name = re.sub(r"주식회사|\(주\)|㈜", "", name or "")
    return re.sub(r"[\s,.·]+", "", name).casefold()


def load_institutions(root=ROOT):
    entries = json.loads((root / "manual/institutions.json").read_text(encoding="utf-8"))
    aliases, by_id = {}, {}

    def bind(inst, names):
        by_id[inst["id"]] = inst
        for name in names:
            key = institution_key(name)
            if key in aliases and aliases[key] != inst["id"]:
                raise ValueError(f"기관 별칭 충돌: {name}")
            aliases[key] = inst["id"]
            if name not in inst["aliases"]:
                inst["aliases"].append(name)

    for inst in entries:
        inst.setdefault("watchlist", False)
        inst.setdefault("region", "국내" if inst["id"] in ("vip", "life", "must") else "해외")
        inst.setdefault("kind", "자산운용사")
        inst.setdefault("styles", [])
        inst["origins"] = ["관심기관 선정"]
        bind(inst, list(inst["aliases"]))

    def find_or_add(name, origin, domestic=False):
        key = institution_key(name)
        inst = by_id.get(aliases.get(key))
        if inst is None:
            kind = ("투자자문사" if "투자자문" in name else "자산운용사" if re.search(r"자산운용|투자운용|신탁운용|리츠운용", name)
                    else "증권사" if "증권" in name and "투자회사" not in name else "기타 운용기관·후보")
            inst = {"id": "inst_" + hashlib.sha256(key.encode()).hexdigest()[:16], "name": name, "aliases": [],
                    "watchlist": False, "region": "국내" if domestic else "미확인",
                    "kind": kind, "styles": [], "origins": []}
            entries.append(inst)
        bind(inst, [name])
        if origin not in inst["origins"]:
            inst["origins"].append(origin)
        return inst

    folder = root / "manual/institution_aum"
    manifest = json.loads((folder / "sources.json").read_text(encoding="utf-8"))
    for snapshot in manifest["snapshots"]:
        with (folder / snapshot["file"]).open(encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == snapshot["companies"], snapshot["file"]
        for row in rows:
            inst = find_or_add(row["name"], "금융투자협회 통계", domestic=True)
            inst.setdefault("aum_history", []).append({
                "date": snapshot["date"], "period": snapshot["period"],
                "value": int(row["total"]) * 100_000_000 if row["total"] else None,
                "currency": "KRW", "series": "kofia_principal", "scope": manifest["scope"],
                "basis": manifest["basis"], "source": manifest["source"], "checked": manifest["checked"],
                "funds": int(row["funds"]) * 100_000_000 if row["funds"] else None,
                "discretionary": int(row["discretionary"]) * 100_000_000 if row["discretionary"] else None})

    # Evaluated AUM is a separate series; never replace the preserved principal snapshots.
    nav_folder = root / "manual/institution_aum_nav"
    nav_manifest = json.loads((nav_folder / "sources.json").read_text(encoding="utf-8"))
    for snapshot in nav_manifest["snapshots"]:
        with (nav_folder / snapshot["file"]).open(encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == snapshot["companies"], snapshot["file"]
        for row in rows:
            inst = find_or_add(row["name"], "금융투자협회 통계", domestic=True)
            inst.setdefault("aum_history", []).append({
                "date": snapshot["date"], "period": snapshot["period"],
                "value": int(row["total"]) * 100_000_000 if row["total"] else None,
                "currency": "KRW", "series": "kofia_nav", "scope": nav_manifest["scope"],
                "basis": nav_manifest["basis"], "source": nav_manifest["source"],
                "checked": nav_manifest["checked"]})

    alias_path = root / "manual/institution_aliases.json"
    if alias_path.exists():
        for rule in json.loads(alias_path.read_text(encoding="utf-8")):
            inst = by_id[aliases[institution_key(rule["canonical"])]]
            bind(inst, rule["aliases"])
            inst.setdefault("alias_sources", []).append(rule)

    reports = {}
    for filename, field in (("대량보유DB.csv", "flr_nm"), ("대량보유상세DB.csv", "repror")):
        path = root / "data/_dart" / filename
        if not path.exists():
            continue
        with path.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                name = row.get(field, "")
                if institution_key(name) in aliases or MANAGER.search(name):
                    inst = find_or_add(name, "DART 공시")
                    reports.setdefault(inst["id"], set()).add(row["rcept_no"])
    for inst in entries:
        inst["dart_reports"] = len(reports.get(inst["id"], ()))
        inst["dart_status"] = "연결됨" if inst["dart_reports"] else "저장 공시 미확인"
        for point in inst.get("profile", {}).get("aum", []):
            inst.setdefault("aum_history", []).append({**point, "series": "official:" + point["currency"] + ":" + point["scope"],
                "basis": "운용사 공식 발표", "period": "year_end" if point["date"][5:] == "12-31" else "observation"})
        inst.setdefault("aum_history", []).sort(key=lambda p: (p["date"], p["series"]))
    entries.sort(key=lambda i: (not i["watchlist"], i["name"].casefold()))
    return entries, aliases
