# 구리 수급

기존 Yahoo HG=F 가격·월물 커브·스프레드에 SHFE 주간 재고를 추가했다.
SMM·LME·COMEX 재고는 이번 수집 범위에 포함하지 않는다.

## SHFE

- 원문: https://www.shfe.cn/eng/reports/StatisticalData/WeeklyData/
- 공개 웹 데이터 경로는 공식 `/eng/images/api.js`의 `api_future_weeklystock`에서 확인했다.
- `o_cursor`에서 구리(`铜`)의 `总计` 행만 사용한다. 지역 소계·보세/완세 소계를 다시 합산하지 않는다.
- `SPOTWGHTS`가 주간 재고(톤), `SPOTCHANGE`가 전주 대비다. `WHSTOCKS`는 창고 용량이며 재고가 아니다. `WRTWGHTS` 창고증권을 재고에 더하지 않는다.
- 요청일과 `report_date`, `o_tradingday` 일치, 단위, 유한한 비음수 재고, 전주 재고+증감=현재 재고를 검증한다.
- 일일 워크플로는 최근 21일 평일을 재확인한다. 404는 미발표로 건너뛰며 유효 보고서가 없으면 실패를 반환하고 기존 파일·수집일을 유지한다.
- 초기 이력: `python scripts/fetch_copper_inventory.py --backfill-weeks 156`. 과거 금요일 중심 이력이므로 휴일 단축 주차가 누락될 수 있다. 결측은 보간하지 않는다.
- 4주 변화는 정확히 28일 전 관측치가 있을 때만 계산한다. 주간 증감은 원문 값을 사용한다.
- 데이터 기준일이 14일 이상 지났으면 과거 자료 경고를 표시한다. 수집일이 최근이어도 경고를 숨기지 않는다.

최초 확인 시 2023-10-13~2025-11-14의 101개 보고서를 확보했다. 최근 요청 날짜는 404였으므로 현재 수급 판단용 최신 자료로 표시하지 않는다. 최신 경로의 지속 가용성은 미확인이다.

검증: `python -m unittest discover -s scripts -p test_copper_inventory.py`
