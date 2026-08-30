# -*- coding: utf-8 -*-
"""EIA-930 (Hourly Electric Grid Monitor) 수집기 — 전력구역별 수요.

EIA-860M이 '설비(공급)'라면 이건 '수요'다. 같은 BA 코드를 쓰므로 그대로 조인된다.
860M만으로는 "PJM 파이프라인이 얇다"까지밖에 못 말하는데, 여기가 붙으면
"수요는 X% 느는데 공급은 12%"라는 문장이 완성된다.

원본: https://www.eia.gov/electricity/gridmonitor/
  6개월 단위 CSV: .../sixMonthFiles/EIA930_BALANCE_{YYYY}_{Jan_Jun|Jul_Dec}.csv
  **API 키가 필요 없다.** (api.eia.gov v2는 키를 요구하지만 이 벌크 CSV는 공개)
  2015년 하반기부터 제공. 파일당 30~48MB, 시간 단위 60개 BA.

산출: data/_eia930/monthly.csv.gz — (BA, 월) 단위로 집계
  demand_mwh(전력량), peak_mw(최대수요), netgen_mwh, gen_*(발전원별 전력량)

사용법:
  python scripts/fetch_eia930.py --backfill   # 최초 1회(로컬). 2015H2부터 약 900MB.
  python scripts/fetch_eia930.py              # CI 기본. 현재 반기 파일만 다시 받아 갱신.

함정:
  1) **EIA 헤더에 오타가 있다.** `Pumped Storage  (Adjusted)`는 공백이 두 칸이고,
     `Solar witho Integrated Battery Storage (Adjusted)`는 with가 witho로 깨져 있다.
     컬럼명을 하드코딩하면 조용히 누락된다 → 공백 정규화 + 정규식으로 뽑는다.
  2) 같은 지표가 원본/Imputed/Adjusted 3벌로 들어있다. **Adjusted가 EIA가 보정을
     끝낸 값**이라 이걸 쓴다(원본만 쓰면 결측 구간이 생긴다).
  3) 현재 반기 파일은 매일 자란다. 과거 반기는 고정이므로 CI는 현재 파일만 다시 받는다.
  4) 날짜가 MM/DD/YYYY다.
"""
import argparse
import gzip
import re
import shutil
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
D930 = ROOT / "data" / "_eia930"
RAW = D930 / "raw"  # gitignore

BASE = "https://www.eia.gov/electricity/gridmonitor/sixMonthFiles"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
BACKFILL_START = (2015, 2)  # 2015년 하반기부터 제공
MIN_BYTES = 1_000_000

BA_COL = "Balancing Authority"
DATE_COL = "Data Date"
DEMAND_COL = "Demand (MW) (Adjusted)"
NETGEN_COL = "Net Generation (MW) (Adjusted)"
FUEL_RE = re.compile(r"^Net Generation \(MW\) from (.+) \(Adjusted\)$")

# 930의 연료 구분 → 대시보드 표기. 860M의 기술 분류와 결이 맞게 묶는다.
# (930은 가스 복합/단순을 구분하지 않고, 풍력도 육상/해상을 나누지 않는다 — 발전량이지 설비가 아니라서)
# 2024년 하반기에 EIA가 분류를 바꿨다. 구명칭을 같이 매핑하지 않으면
# 2018H2~2024H1 구간의 태양광·풍력·수력이 통째로 0이 된다.
#   Solar        → Solar with/without Integrated Battery Storage
#   Wind         → Wind  with/without Integrated Battery Storage
#   Hydropower and Pumped Storage → Hydropower Excluding Pumped Storage + Pumped Storage
# 또 연료별 발전량 자체가 **2018년 하반기부터**다(그 이전은 Unknown Fuel Sources뿐).
FUEL_GROUP = {
    "Coal": "석탄",
    "Solar": "태양광",                          # 구명칭
    "Wind": "풍력",                             # 구명칭
    "Hydropower and Pumped Storage": "수력",    # 구명칭(양수 포함. 양수 순발전은 ~1TWh라 영향 미미)
    "Natural Gas": "가스",
    "Nuclear": "원자력",
    "All Petroleum Products": "석유",
    "Hydropower Excluding Pumped Storage": "수력",
    "Pumped Storage": "양수",
    "Solar without Integrated Battery Storage": "태양광",
    "Solar with Integrated Battery Storage": "태양광",
    "Wind without Integrated Battery Storage": "풍력",
    "Wind with Integrated Battery Storage": "풍력",
    "Battery Storage": "배터리 ESS",
    "Other Energy Storage": "기타 저장",
    "Unknown Energy Storage": "기타 저장",
    "Geothermal": "지열",
    "Other Fuel Sources": "기타",
    "Unknown Fuel Sources": "기타",
}


def _norm(c: str) -> str:
    """헤더 정규화. 함정 1: EIA 오타(공백 2칸, 'witho') 흡수."""
    c = re.sub(r"\s+", " ", str(c).strip().strip('"'))
    return c.replace("Solar witho Integrated", "Solar with Integrated")


def half_iter(start, end):
    y, h = start
    while (y, h) <= end:
        yield y, h
        h += 1
        if h > 2:
            y, h = y + 1, 1


def _url(y: int, h: int) -> str:
    return f"{BASE}/EIA930_BALANCE_{y}_{'Jan_Jun' if h == 1 else 'Jul_Dec'}.csv"


def fetch_half(y: int, h: int, force: bool = False) -> Path | None:
    dest = RAW / f"{y}H{h}.csv"
    if dest.exists() and dest.stat().st_size > MIN_BYTES and not force:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        req = urllib.request.Request(_url(y, h), headers=UA)
        with urllib.request.urlopen(req, timeout=300) as r, open(dest, "wb") as f:
            shutil.copyfileobj(r, f)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        print(f"  !! {y}H{h} 실패: {e}", file=sys.stderr)
        return None
    if dest.stat().st_size < MIN_BYTES:
        dest.unlink(missing_ok=True)
        return None
    return dest


def aggregate_file(path: Path) -> pd.DataFrame:
    """시간 단위 CSV → (BA, 월) 집계. 메모리 아끼려 필요한 컬럼만 읽는다."""
    header = pd.read_csv(path, nrows=0)
    cols = {_norm(c): c for c in header.columns}
    fuels = {}
    for norm, orig in cols.items():
        m = FUEL_RE.match(norm)
        if m and m.group(1) in FUEL_GROUP:
            fuels[orig] = FUEL_GROUP[m.group(1)]
    use = [cols[BA_COL], cols[DATE_COL], cols[DEMAND_COL], cols[NETGEN_COL]] + list(fuels)

    df = pd.read_csv(path, usecols=use, low_memory=False)
    df.columns = [_norm(c) for c in df.columns]
    fuels = {_norm(k): v for k, v in fuels.items()}

    df["month"] = pd.to_datetime(df[DATE_COL], format="%m/%d/%Y", errors="coerce") \
                    .dt.strftime("%Y-%m")
    df = df[df["month"].notna()]
    for c in [DEMAND_COL, NETGEN_COL] + list(fuels):
        df[c] = pd.to_numeric(df[c], errors="coerce")

    # 최대수요는 **단일 시간 오류에 그대로 오염된다**. PJM 2020-07에는 224,345 / 192,229 /
    # 176,085MW가 세 시간 찍혀 있는데 4번째로 큰 값은 145,428MW다(실제 피크가 그 수준).
    # 비율 임계값으로는 이런 연속 오류를 못 거른다(오류가 분위수 자체를 밀어올린다)
    # → 월별 **99.5분위(약 4번째로 높은 시간)** 를 최대수요로 쓴다.
    # 정상 월에서는 진짜 최댓값보다 1% 안쪽으로 낮을 뿐이고, 오류에는 흔들리지 않는다.
    # 원 최댓값은 peak_raw_mw로 같이 남긴다.
    key = [BA_COL, "month"]
    g = df.groupby(key)
    out = pd.DataFrame({
        "demand_mwh": g[DEMAND_COL].sum(),
        "peak_mw": g[DEMAND_COL].quantile(0.995),
        "peak_raw_mw": g[DEMAND_COL].max(),
        "hours": g[DEMAND_COL].count(),
        "netgen_mwh": g[NETGEN_COL].sum(),
    })
    # 같은 그룹으로 묶이는 연료(태양광 2컬럼 등)는 합산
    for bucket in sorted(set(fuels.values())):
        srcs = [c for c, b in fuels.items() if b == bucket]
        # min_count=1: 전부 결측인 그룹은 0이 아니라 NaN이어야 한다
        # (2018년 하반기 이전엔 연료 컬럼 자체가 없어 0으로 나오면 "발전량 0"으로 오독된다)
        out[f"gen::{bucket}"] = g[srcs].sum(min_count=1).sum(axis=1, min_count=1)
    out = out.reset_index().rename(columns={BA_COL: "ba"})
    return out


def _save(df: pd.DataFrame) -> None:
    D930.mkdir(parents=True, exist_ok=True)
    p = D930 / "monthly.csv.gz"
    with gzip.open(p, "wt", encoding="utf-8", newline="", compresslevel=9) as f:
        df.to_csv(f, index=False)
    print(f"  saved {p.relative_to(ROOT)}  ({len(df):,} rows, {p.stat().st_size/1e3:.0f} KB)")


def _load() -> pd.DataFrame | None:
    p = D930 / "monthly.csv.gz"
    return pd.read_csv(p, dtype={"ba": str, "month": str}) if p.exists() else None


def current_half() -> tuple[int, int]:
    t = date.today()
    return t.year, 1 if t.month <= 6 else 2


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backfill", action="store_true", help="2015H2부터 전부(로컬 1회, 약 900MB)")
    ap.add_argument("--keep-raw", action="store_true", help="원본 CSV 유지(기본: 파싱 후 삭제)")
    args = ap.parse_args()

    cur = current_half()
    old = _load()
    if args.backfill:
        halves = list(half_iter(BACKFILL_START, cur))
    else:
        if old is None:
            print("!! 월별 저장소가 없다. --backfill 로 최초 구축 필요.", file=sys.stderr)
            return 1
        halves = [cur]  # 함정 3: 과거 반기는 고정, 현재 반기만 다시 받는다
    print(f"대상 {len(halves)}개 반기: {halves[0]} ~ {halves[-1]}")

    frames = []
    for y, h in halves:
        p = fetch_half(y, h, force=(not args.backfill))
        if p is None:
            continue
        try:
            frames.append(aggregate_file(p))
            print(f"  {y}H{h} 집계 완료 ({p.stat().st_size/1e6:.0f}MB)", flush=True)
        except Exception as e:
            print(f"  !! {y}H{h} 파싱 실패: {e}", file=sys.stderr)
        if not args.keep_raw:
            p.unlink(missing_ok=True)

    if not frames:
        print("!! 집계된 파일 없음", file=sys.stderr)
        return 1

    new = pd.concat(frames, ignore_index=True)
    if old is not None and not args.backfill:
        new = pd.concat([old, new], ignore_index=True)
    new = new.drop_duplicates(subset=["ba", "month"], keep="last")
    new = new.sort_values(["ba", "month"]).reset_index(drop=True)
    _save(new)

    if not args.keep_raw and RAW.exists():
        shutil.rmtree(RAW, ignore_errors=True)
    print(f"완료. {new['ba'].nunique()}개 구역 / {new['month'].min()}~{new['month'].max()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
