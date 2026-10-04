# -*- coding: utf-8 -*-
"""모든 페처 실행. 개별 소스 실패는 건너뛰고 나머지는 계속 진행."""
import sys
import traceback
from functools import partial
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import import_manual
from fetchers import harpex, kcla, kobc, stockq, tankers_international
from common import record_fetch_failure

JOBS = [
    ("KOBC KCCI", kobc.fetch_kcci, ["kcci"]),
    ("KOBC KDCI", kobc.fetch_kdci, ["kdci"]),
    ("Harper Petersen HARPEX", harpex.run, ["harpex"]),
    *[(f"KCLA {key.upper()}", partial(kcla.fetch_one, key, *args), [key]) for key, args in kcla.PAGES.items()],
    *[(f"StockQ {key.upper()}", partial(stockq.fetch_one, key, *args), [key]) for key, args in stockq.INDICES.items()],
    ("Tankers International (VLCC 성약 TCE)", tankers_international.run,
     ["ti_vlcc_tce", "ti_vlcc_routes", "ti_vlcc_count", "ti_vlcc_fixtures"]),
    ("수기입력 CSV 변환", import_manual.run, []),
]


def main():
    failures = []
    for name, fn, ids in JOBS:
        print(f"[{name}]")
        try:
            fn()
        except Exception as error:
            traceback.print_exc()
            failures.append(name)
            print(f"::warning title=운임지표 수집 실패::{name}: {type(error).__name__}")
            for ind_id in ids:
                record_fetch_failure("shipping", ind_id, error)
    if failures:
        print(f"\n실패한 소스: {', '.join(failures)} (나머지는 정상 갱신됨)")
        # 일부 실패해도 성공한 데이터는 커밋되도록 exit 0
    print("done")


if __name__ == "__main__":
    main()
