"""Build lifecycle metadata from saved full histories, without fetching FRED."""
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "data" / "ppi"


def navigation(observations: dict, updated: str) -> dict:
    return {"updated": updated, "latest_dates": {sid: points[-1][0] if points else None for sid, points in observations.items()}}


def main() -> None:
    manifest = json.loads((ROOT / "catalog.json").read_text(encoding="utf-8"))
    def read(s):
        doc = json.loads((ROOT / "series" / f"{s['id']}.json").read_text(encoding="utf-8"))
        if doc["fetched"] != manifest["updated"]:
            raise ValueError(f"Mixed snapshot: {s['id']}")
        return s["id"], doc["points"]
    with ThreadPoolExecutor(max_workers=8) as pool:
        observations = dict(pool.map(read, manifest["series"]))
    out = ROOT / "navigation.json"
    temp = out.with_suffix(".tmp")
    temp.write_text(json.dumps(navigation(observations, manifest["updated"]), separators=(",", ":")), encoding="utf-8")
    temp.replace(out)
    print(f"Navigation metadata: {len(observations)} series")


if __name__ == "__main__":
    main()
