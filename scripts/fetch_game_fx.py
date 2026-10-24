"""Free ECB daily reference rates, averaged over each exact reporting interval.

Original accounts are never rewritten. fx.json is a separate, reproducible lookup:
daily local/EUR divided by USD/EUR -> local/USD, then arithmetic mean of all
published days in [start, end]. Original currency millions / mean -> USD millions.
Annual means use all daily observations, not an unweighted mean of quarter means.
"""
import argparse
import csv
from datetime import date, datetime, timedelta, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import statistics
import zipfile

import requests

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip"
SOURCE_PAGE = "https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html"
METHOD = "mean daily local per USD; original millions divided by mean"


def parse_rates(raw):
    """Read ECB's actual published dates only; never carry holidays forward."""
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        text = archive.read("eurofxref-hist.csv").decode("utf-8-sig")
    result = {}
    for row in csv.DictReader(io.StringIO(text)):
        day = date.fromisoformat(row["Date"])
        if day in result:
            raise ValueError("duplicate ECB observation date")
        try:
            usd = float(row["USD"])
        except (ValueError, KeyError):
            continue
        if not math.isfinite(usd) or usd <= 0:
            continue
        quotes = {}
        for currency, value in row.items():
            if not currency or len(currency) != 3:
                continue
            try:
                local = float(value)
            except (ValueError, TypeError):
                continue
            if math.isfinite(local) and local > 0:
                quotes[currency] = local / usd
        result[day.isoformat()] = quotes
    return result


def period_average(rates, currency, start, end):
    begin, finish = date.fromisoformat(start), date.fromisoformat(end)
    if begin > finish:
        raise ValueError("reversed reporting interval")
    points = sorted((d, r[currency]) for d, r in rates.items()
                    if start <= d <= end and currency in r)
    if not points:
        return None
    days = [begin + timedelta(days=i) for i in range((finish-begin).days+1)]
    weekdays = sum(d.weekday() < 5 for d in days)
    # Reject truncated feeds, missing months or large holes. Never use a partial
    # average as though it covers a complete fiscal period.
    gaps = [(date.fromisoformat(b[0])-date.fromisoformat(a[0])).days
            for a, b in zip(points, points[1:])]
    if (len(points) < weekdays * .85
            or (date.fromisoformat(points[0][0])-begin).days > 7
            or (finish-date.fromisoformat(points[-1][0])).days > 7
            or max(gaps, default=0) > 7):
        return None
    return dict(currency=currency, start=start, end=end,
                local_per_usd=statistics.fmean(p[1] for p in points),
                observations=len(points), first=points[0][0], last=points[-1][0])


def monetary_metric(row):
    return row.get("unit", "").startswith("백만 ") and row.get("kind") in {"revenue", "spend", "creator_income"}


def required_intervals(companies, platforms, revenue):
    periods = {(c["currency"], r["start"], r["date"])
               for c in companies["companies"] for r in c["rows"] if c["currency"] != "USD"}
    for profile in platforms["profiles"]:
        for row in profile["metrics"]:
            if monetary_metric(row):
                currency = row["unit"].split()[-1]
                if currency != "USD":
                    periods.add((currency, row["start"], row["date"]))
    for row in revenue.get("official_games", []):
        if row["currency"] != "USD":
            periods.add((row["currency"], row["start"], row["date"]))
    return sorted(periods)


def build_snapshot(previous, intervals, rates, fetched, digest=None, error=None):
    periods = {}
    missing = []
    for currency, start, end in intervals:
        key = f"{currency}|{start}|{end}"
        quote = period_average(rates, currency, start, end) if rates is not None else None
        if quote is not None:
            quote.update(fetched=fetched, source=SOURCE, sha256=digest, method=METHOD)
        else:
            # Exact interval only: an old completed quote is usable and retains
            # its real collection date. Never borrow an adjacent quarter/rate.
            old = previous.get("periods", {}).get(key)
            if (old and old.get("currency") == currency and old.get("start") == start
                    and old.get("end") == end and old.get("method") == METHOD
                    and isinstance(old.get("local_per_usd"), (int, float))
                    and math.isfinite(old["local_per_usd"]) and old["local_per_usd"] > 0):
                quote = old
        if quote:
            periods[key] = quote
        else:
            missing.append(key)
    return dict(base="USD", rate_unit="original currency per 1 USD", method=METHOD,
                source=SOURCE, source_page=SOURCE_PAGE,
                fetched=fetched if rates is not None else previous.get("fetched"),
                status="ok" if rates is not None and not missing else "partial" if rates is not None else "fetch failed; retained completed intervals",
                error=error, missing=missing, periods=periods)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ecb-cache", type=Path, help="Previously downloaded, unmodified ECB ZIP")
    args = parser.parse_args()
    target = ROOT / "data/games/fx.json"
    read = lambda p: json.loads(p.read_text(encoding="utf-8"))
    previous = read(target) if target.exists() else {}
    intervals = required_intervals(read(ROOT / "data/games/companies.json"),
                                   read(ROOT / "data/games/platforms.json"),
                                   read(ROOT / "data/games/revenue.json"))
    fetched = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    raw, rates, error = None, None, None
    try:
        if args.ecb_cache:
            raw = args.ecb_cache.read_bytes()
        else:
            response = requests.get(SOURCE, timeout=60)
            response.raise_for_status()
            raw = response.content
        rates = parse_rates(raw)
        if not rates:
            raise ValueError("empty ECB feed")
    except (requests.RequestException, ValueError, KeyError, zipfile.BadZipFile, OSError) as exc:
        error = f"{type(exc).__name__}: ECB feed unavailable"
        rates = None
    snapshot = build_snapshot(previous, intervals, rates, fetched,
                              hashlib.sha256(raw).hexdigest() if raw else None, error)
    target.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(f"FX {snapshot['status']}: {len(snapshot['periods'])}/{len(intervals)} complete reporting intervals; {len(snapshot['missing'])} missing")


if __name__ == "__main__":
    main()
