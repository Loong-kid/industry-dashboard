# -*- coding: utf-8 -*-
"""해운 탭의 가스선 운임에서 LNG 항목만 떼어 천연가스 탭에도 둔다.

`data/shipping/gas_earnings.json`(신영 위클리 PDF → 클락슨 선형별 운임)에는 VLGC(LPG)와 LNG가
함께 들어 있다. 해운 탭에서는 가스선을 한 카드로 보는 게 맞지만, 천연가스 탭에서는 LNG 운임이
가격·차익·프로젝트와 함께 읽혀야 한다 — 그래서 **해운 쪽은 그대로 두고 LNG 계열만 복제**한다.

수집이 아니라 이미 받아 둔 JSON을 변환만 하므로 네트워크를 쓰지 않는다. 원본이 주간 수동
(PDF 추출)이라 이 스크립트도 그 뒤에 돌면 되고, CI에서 매일 돌아도 값은 그대로다.

    python scripts/derive_lng_freight.py
"""
import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "shipping" / "gas_earnings.json"
OUT = ROOT / "data" / "natgas" / "lng_freight.json"


def run():
    if not SRC.exists():
        print(f"  원본 없음: {SRC.relative_to(ROOT)} (extract_shinyoung.py 먼저 실행)")
        return
    src = json.loads(SRC.read_text(encoding="utf-8"))
    series = {k: v for k, v in src.get("series", {}).items() if "LNG" in k}
    if not series:
        print("  LNG 계열 시리즈를 찾지 못했다 — 원본 시리즈명이 바뀌었는지 확인할 것")
        return

    # 기본 표시는 현행 기준선(174k). 구기준(160k)은 2024년에 끊겨 있어 칩으로만 둔다.
    default = [k for k in series if "174" in k] or [list(series)[0]]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "id": "lng_freight", "name": "LNG선 운임 (스팟 용선료)",
        "unit": src.get("unit", "USD/day"), "frequency": "weekly",
        "source": src.get("source", ""), "source_url": src.get("source_url", ""),
        "updated": src.get("updated"), "fetched": dt.date.today().isoformat(),
        "stale_days": src.get("stale_days", 10),  # 주간 수동 소스라 지연 기준을 원본과 맞춘다
        "default_series": default,
        "description": (
            "LNG 운반선 한 척을 하루 빌리는 값(스팟 용선료). 174k는 현행 주력 선형인 17.4만 입방미터급, "
            "160k는 옛 기준선이다. 앞의 'JKM − TTF'가 벌어져 화물이 아시아로 멀리 돌면 같은 척수로 "
            "나를 수 있는 양이 줄어 이 운임이 오른다. 해운 탭 '가스선 운임' 카드와 같은 데이터이며, "
            "여기서는 LNG 계열만 떼어 두었다(LPG용 VLGC는 해운 탭에 있다)."
        ),
        "note": "신영 위클리 PDF에서 주 1회 추출한다 — 사용자가 새 PDF를 저장한 뒤 갱신된다.",
        "series": series,
    }, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    last = max((v[-1][0] for v in series.values() if v), default="")
    print(f"  lng_freight: {len(series)}시리즈 (~{last}) ← {SRC.name}")


if __name__ == "__main__":
    run()
