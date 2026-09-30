# 구리 수급

기존 Yahoo HG=F 가격·월물 커브·스프레드에 SHFE 주간 재고를 추가했다.
SMM·LME·COMEX 재고는 이번 수집 범위에 포함하지 않는다.

## SHFE

- 원문: https://www.shfe.cn/eng/reports/StatisticalData/WeeklyData/
- 현재 경로: `/data/tradedata/future/stockdata/weeklystock_YYYYMMDD/ZH/all.html`. 공식 `/images/api.js`의 `api_weeklystock_iframe`와 `/images/generateData_weeklystock.js`에서 HTML 우선·JSON 대체 순서를 확인했다.
- 과거 JSON 경로: `/data/tradedata/future/weeklydata/YYYYMMDDweeklystock.dat`. 2025-11-14까지의 보고서가 이 경로로 제공되며 이후 보고서는 새 HTML 경로에서 확인했다. JSON 404만으로 원자료 미발표를 판단하면 안 된다.
- `o_cursor`에서 구리(`铜`)의 `总计` 행만 사용한다. 지역 소계·보세/완세 소계를 다시 합산하지 않는다.
- `SPOTWGHTS`가 주간 재고(톤), `SPOTCHANGE`가 전주 대비다. `WHSTOCKS`는 가용 창고 용량이며 재고가 아니다. `WRTWGHTS` 창고증권을 재고에 더하지 않는다.
- HTML은 구리·톤·열 제목을 검증한 뒤 `总计`의 본주 재고 `小计`와 재고 증감 `小计`를 읽는다. 다른 금속·완세/보세 소계·창고증권·가용 창고 용량을 합산하지 않는다.
- 요청일과 HTML 보고서 날짜(구형 JSON은 `report_date`, `o_tradingday`) 일치, 단위, 유한한 비음수 재고, 전주 재고+증감=현재 재고를 검증한다.
- 일일 워크플로는 최근 21일 평일을 재확인한다. 404는 미발표로 건너뛰며 유효 보고서가 없으면 실패를 반환하고 기존 파일·수집일을 유지한다.
- 이력 수집: `python scripts/fetch_copper_inventory.py --backfill-weeks 156`. 기존 관측치는 보존하고 미수집 평일을 확인한다. 2025년 11월 이후 공백은 48주 평일 재수집으로 복원했다. 기존 2025년 10월 이전 이력은 금요일 중심이므로 휴일 단축 주차가 누락될 수 있다. 결측은 보간하지 않는다.
- 4주 변화는 정확히 28일 전 관측치가 있을 때만 계산한다. 주간 증감은 원문 값을 사용한다.
- 데이터 기준일이 14일 이상 지났으면 과거 자료 경고를 표시한다. 수집일이 최근이어도 경고를 숨기지 않는다.

최초 버전은 구형 JSON만 사용해 2025-11-14에서 멈췄다. 원자료 제공 중단이 아니라 수집 경로 선택 오류였다. 수정 후 2026-09-30 공식 보고서에서 재고 38,744톤, 전주 47,147톤, 증감 -8,403톤을 확인했다. 9월 24일과 9월 30일처럼 금요일이 아닌 발표일도 수집한다.

공식 원문: https://www.shfe.cn/data/tradedata/future/stockdata/weeklystock_20260930/ZH/all.html

검증: `python -m unittest discover -s scripts -p test_copper_inventory.py`
