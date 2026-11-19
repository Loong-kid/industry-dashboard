# 소부장 전체 요약

`#/semicon/materials`의 기본 화면은 `#/semicon/materials/overview`에 해당하는 전체 요약이다. 기존 `#/semicon/materials/equipment` 및 개별 분야·옛 세부탭 주소는 계속 같은 자료를 가리킨다.

기업 목록은 `data/catalog.json`의 소부장 세부탭에서 참조하는 `valuation_company`·`valuation_companies` 및 하위 기업 목록을 모아, 기존 `data/semicon/valuation/valuation_index.json`과 결합한다. 회사 ID별 한 행이며 여러 분야의 소속과 이동 링크를 모두 보존한다. 장비 전체 요약·OSAT 전체 비교 같은 중복 목적지는 같은 기업의 세부 분야로 정리한다. 별도 수기 기업 목록이나 추가 수집 워크플로가 없어, 기업 등록·제거 및 주가 갱신을 그대로 따른다.

2026-11-19 기준 98개 등록 항목이다. 국내 상장 58개·해외 상장 37개·그 외 3개이며, ‘국내/해외’는 회사의 본사 국가가 아니라 상장 종목을 기준으로 구분한다. NuFlare의 상장폐지, CETC의 비상장, TOPEC 후보의 법인 확인 상태를 유지한다. Lumentum·Coherent는 MOCVD 수요처·참고 기업으로 표시한다. 정전척처럼 무역 지표만 있는 분야에는 기업을 임의로 만들어 넣지 않는다.

기업명·종목·분야 검색, 분야·세부 분야·상장 시장·등재 상태 필터 및 PER/PBR 정렬을 제공한다. 미확인 배수·적자 PER은 N/M이며, 비상장 등에는 가격을 채우지 않는다. 회사 전체 주가 배수와 사업부·추정 실적의 범위 차이를 안내한다. 다른 통화·사업 범위를 단순 합산한 매출이나 이익은 만들지 않는다.

기업·분야 링크는 기존 세부탭으로 이동한 다음 연결된 실적 제목 또는 기업 주가 패널로 스크롤한다. 페이지 로딩 완료를 기다리고, 다른 화면으로 이동하면 대기 중인 관찰자를 해제한다. Ctrl/Command 클릭 등 새 탭 동작은 일반 링크처럼 유지한다.

```text
node scripts/test_materials_overview.cjs
python scripts/verify_materials_overview_ui.py --url http://127.0.0.1:8807/
python scripts/run_ci_tests.py
```
