# -*- coding: utf-8 -*-
"""모든 페처 실행. 개별 소스 실패는 건너뛰고 나머지는 계속 진행."""
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import import_manual
from fetchers import kcla, kobc, stockq

JOBS = [
    ("KOBC (KCCI/KDCI)", kobc.run),
    ("KCLA (SCFI/CCFI/KCFI)", kcla.run),
    ("StockQ (BDI/BDTI/BCTI)", stockq.run),
    ("수기입력 CSV 변환", import_manual.run),
]


def main():
    failures = []
    for name, fn in JOBS:
        print(f"[{name}]")
        try:
            fn()
        except Exception:
            traceback.print_exc()
            failures.append(name)
    if failures:
        print(f"\n실패한 소스: {', '.join(failures)} (나머지는 정상 갱신됨)")
        # 일부 실패해도 성공한 데이터는 커밋되도록 exit 0
    print("done")


if __name__ == "__main__":
    main()
