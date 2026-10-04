# 세계 주식시장 월별 시총 소스 조사 (2026-10-04)

한국 월말 시총은 ECOS로 구현했다. 세계 월별 시총도 WFE Focus 공개 월보로 구현했으며 매크로 → 시장규모에서 확인할 수 있다.

## WFE — 사용할 수 있는 월별 시총

- [공식 통계 안내](https://www.world-exchanges.org/our-work/statistics): 월간·연간 수집, 지표·거래소별 시계열과 다운로드. [지표 명세](https://wfe-live.lon1.digitaloceanspaces.com/org_focus/storage/media/statistics/monthly%20and%20annual%20indicators%20updated%2015%20Nov%202024.pdf)는 Market Capitalisation을 monthly & annually로 명시한다.
- [Focus 공개 월간 통계](https://focus.world-exchanges.org/issue/october-2026/market-statistics): 로그인 없이 HTTP 200 HTML 표 확인. 2026년 1~8월 Domestic market capitalisation(USD millions), Americas/APAC/EMEA 합계와 거래소별 자료가 있다. [2026년 9월판](https://focus.world-exchanges.org/issue/september-2026/market-statistics)은 2026년 1~7월이며 과거 호 목록은 2018년까지 공개돼 있다. 잡지 발행월과 관측월을 구분해야 한다.
- [공개 Dashboard](https://focus.world-exchanges.org/issue/september-2026/dashboard)는 세계 합계 스냅샷과 같은 기준월의 지역 자료를 표시한다. 세계 합계는 WFE가 공표한 지역 합계를 기준으로 집계하며 개별 거래소를 임의로 다시 더하지 않는다. Euronext·Nasdaq Nordic 등 여러 국가를 아우르는 거래소를 한 국가로 간주해서도 안 된다.
- [Statistics Portal](https://statistics.world-exchanges.org/)은 로그인 화면으로 연결된다. 등록 사용자용 일괄 시계열 추출이 있으므로 계정이 있으면 정규 다운로드 경로를 우선한다. 등록·이용 조건 및 외부 공개 재사용 범위는 실제 적용 경로별로 확인해야 한다. 이번 조사에서 회원가입이나 통계팀 연락은 하지 않았다.

## 구현과 검증

- `scripts/fetch_wfe_market_cap.py`가 공개 월보 링크를 탐색하고 시총 표의 단위·관측월·지역 합계·개정 빈티지를 검증한다. 최초 로딩에는 공개 과거 월보를 수집했고, 매일 최신 3개 월보와 매월 1일 연말 관련 과거 원문을 재확인한다. `fetch_market_size.py`의 기존 매일 예약 단계에 연결했으므로 별도 API 키나 계정이 필요하지 않다.
- 7개 카드: 세계, 3개 지역, 미국 NYSE+Nasdaq(각 거래소도 선택 가능), 중국 상하이+선전(각 거래소도 선택 가능), 일본 JPX, 홍콩 HKEX, 유럽 6개 주요거래소. 미국·중국·일본·유럽 카드를 국가 전체 또는 지수 시총으로 부르지 않는다. 홍콩은 중국 본토 합계에 포함하지 않는다. 유럽은 Euronext·Deutsche Börse·SIX·BME·Nasdaq Nordic/발트·LSE의 비교이며 EU 전체 합계를 만들지 않는다.
- 최초 확보 범위는 2018-01~2026-08, 대표 계열 각각 102개월이다. 2020-11·12는 공개 월보 통계표를 확보하지 못해 빈 월로 남긴다. LSE는 2018-01~2023-09의 67개월만 확보됐으며 이후를 채우지 않는다. 월간 차트 축을 매월 유지하고 `span_gaps: false`로 선을 끊는다. 기본 3년, 상단 전체 버튼으로 전체 이력과 표를 볼 수 있다.
- WFE의 Domestic market capitalisation, 원자료 USD millions ÷ 1,000,000 = 조 달러. 달력상 월말 날짜이며 원문 발행월과 관측월은 다르다. 명목 달러이므로 환율 영향이 포함된다. 국가별 보고 분류·거래소 통합·보고 범위 변화로 비교에 한계가 있고 비상장 기업 자산이나 ETF 순자산, 매출·거래대금이 아니다. World Bank 연간 이력과 이어 붙이지 않는다.
- 세계 합계는 같은 월보 빈티지의 Americas+APAC+EMEA 공표 지역 합계다. 개별 거래소를 모두 다시 더하지 않는다. 미국·중국의 주요거래소 합계 역시 같은 월보·공통 월의 성분만 합산한다. 누락된 지역으로 부분 세계 합계를 만들지 않는다.
- 2026년 10월판의 두 `Mar'26` 열은 모두 제외하고, 명확한 2026년 9월판의 3월·5월 값을 유지했다. 10월판의 올바른 머리글이 붙은 나머지 월은 새 개정치로 반영했다. 월을 열 순서로 추정하거나 잘못된 3월을 5월로 바꾸지 않는다. 과거 이중 머리글의 rowspan/colspan도 실제 연도·월 라벨로 읽는다.
- 원문은 특정 거래소의 두 달 이하 연속 누락에 대해 WFE가 보간했다고 명시한다. 대시보드가 직접 보간하지 않더라도 원자료에 추정이 포함될 수 있음을 설명해야 한다.
- Focus의 공식 차트가 참조하는 공개 Google workbook도 실제 다운로드 확인했다. 다만 `DMC` 시트의 값은 2013~2018년에 머무르고 `DMC table`도 2018년 표여서 최신 자동 수집 소스로 부적합하다. 다른 시트가 최신이라는 이유만으로 오래된 시총 시트를 최신으로 판단하지 않는다.

- 각 JSON의 `series_sources`는 계열별 관측월 출처와 월보 발행월을 보존한다. `period_sources`는 대표 계열이며 표에 해당 원문 링크를 표시한다. `data/_market_size/wfe_monthly.json`은 단위가 USD millions인 정규화 이력/빈티지 캐시다. 최신 월보 파싱 실패, 단위 변화, 기존 이력 삭제·최신 월 후퇴는 7개 카드를 교체하기 전에 거부한다.
- `test_wfe_market_cap.py`, `test_wfe_cards.cjs`에서 단위·퍼센트/기업수 제외, 잘못된 머리글, 연도 전환, 동일 빈티지 합계, 실패 시 보존, 실제 월 누락·출처·토글을 검증한다. WFE 원자료의 보간은 대시보드에서 구별 가능한 개별 표식을 제공하지 않으므로 별도 주의 문구를 표시한다.
