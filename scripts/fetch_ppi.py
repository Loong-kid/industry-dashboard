"""Export the industry PPI monitor as lazy-loaded, key-free FRED snapshots.

Catalog metadata is retained from PPI-Monitoring. Full histories are stored per
series; scanners load only the most recent 49 months of their selected sector.
All requests must succeed before replacing any published snapshot.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "ppi"
URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
# FRED graph CSV silently truncates requests beyond 12 series.
BATCH_SIZE = 12


def parse_csv(text: str, ids: list[str]) -> dict[str, list[list]]:
    reader = csv.DictReader(io.StringIO(text))
    fields = reader.fieldnames or []
    if not fields or fields[0] not in ("observation_date", "DATE") or not set(ids).issubset(fields):
        raise ValueError("FRED CSV response did not contain the requested series")
    result = {sid: {} for sid in ids}
    for row in reader:
        month = row[fields[0]][:7]
        if len(month) != 7 or month[4] != "-":
            raise ValueError("Invalid observation date")
        for sid in ids:
            try:
                value = float(row[sid])
            except (ValueError, TypeError):
                continue
            if math.isfinite(value):
                result[sid][month] = value
    return {sid: [[month, value] for month, value in sorted(points.items())]
            for sid, points in result.items()}


def fetch_batch(ids: list[str]) -> dict:
    for attempt in range(4):
        try:
            response = requests.get(URL, params={"id": ",".join(ids)}, timeout=30)
            response.raise_for_status()
            return parse_csv(response.text, ids)
        except (requests.RequestException, ValueError):
            if attempt == 3:
                raise RuntimeError(f"FRED batch failed ({ids[0]}); existing snapshot preserved") from None
            time.sleep(2 ** (attempt + 1))
    raise AssertionError("unreachable")


def recent_points(points: list[list], latest: str, months: int = 49) -> list[list]:
    year, month = map(int, latest.split("-"))
    lower = year * 12 + month - months + 1
    return [p for p in points if int(p[0][:4]) * 12 + int(p[0][5:7]) >= lower]


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False), encoding="utf-8")
    temp.replace(path)


def export(catalog: dict, observations: dict, output: Path = OUT) -> dict:
    # Validate before writes: an accidental empty upstream payload cannot erase data.
    if not observations or not any(observations.values()):
        raise ValueError("No observations; existing snapshot preserved")
    missing = {s["id"] for s in catalog["series"]} - observations.keys()
    if missing:
        raise ValueError(f"Missing {len(missing)} requested series")
    fetched = datetime.now(timezone.utc).isoformat(timespec="seconds")
    sectors = sorted((c for c in catalog["categories"] if c["parent_id"] == catalog["root_category_id"]),
                     key=lambda c: c["name"])
    latest = max(points[-1][0] for points in observations.values() if points)
    for sid, points in observations.items():
        write_json(output / "series" / f"{sid}.json", {"id": sid, "fetched": fetched, "points": points})
    for sector in sectors:
        ids = [s["id"] for s in catalog["series"] if sector["id"] in s["category_ids"]]
        sector_latest = max((observations[sid][-1][0] for sid in ids if observations[sid]), default=latest)
        series = {sid: recent_points(observations[sid], sector_latest) for sid in ids}
        write_json(output / "sectors" / f"{sector['id']}.json",
                   {"id": sector["id"], "fetched": fetched, "data_through": sector_latest, "series": series})
        sector["count"] = len(ids)
    manifest = {"updated": fetched, "data_through": latest, "catalog_built": catalog["built_at"],
                "source": URL, "sectors": sectors, "series": catalog["series"],
                "available": sum(bool(p) for p in observations.values())}
    write_json(output / "catalog.json", manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, help="Original PPI-Monitoring catalog for first import")
    args = parser.parse_args()
    if args.catalog:
        catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    else:
        previous = json.loads((OUT / "catalog.json").read_text(encoding="utf-8"))
        catalog = {"built_at": previous["catalog_built"], "root_category_id": 33584,
                   "categories": previous["sectors"], "series": previous["series"]}
    ids = [s["id"] for s in catalog["series"]]
    batches = [ids[i:i + BATCH_SIZE] for i in range(0, len(ids), BATCH_SIZE)]
    observations = {}
    pool = ThreadPoolExecutor(max_workers=3)
    try:
        for index, batch in enumerate(pool.map(fetch_batch, batches), 1):
            observations.update(batch)
            if index % 10 == 0 or index == len(batches):
                print(f"FRED batches {index}/{len(batches)}", flush=True)
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    manifest = export(catalog, observations)
    print(f"Exported {manifest['available']}/{len(ids)} series; data through {manifest['data_through']}")


if __name__ == "__main__":
    main()
