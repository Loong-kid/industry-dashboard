# 세계 주식시장 월별 시총 소스 조사 (2026-10-04)

한국 월말 시총은 ECOS로 구현했다. 세계 월별 시총은 이번 요청에서 조사만 수행했고 공개 대시보드에 추가하지 않았다.

## WFE — 사용할 수 있는 월별 시총

- [공식 통계 안내](https://www.world-exchanges.org/our-work/statistics): 월간·연간 수집, 지표·거래소별 시계열과 다운로드. [지표 명세](https://wfe-live.lon1.digitaloceanspaces.com/org_focus/storage/media/statistics/monthly%20and%20annual%20indicators%20updated%2015%20Nov%202024.pdf)는 Market Capitalisation을 monthly & annually로 명시한다.
- [Focus 공개 월간 통계](https://focus.world-exchanges.org/issue/october-2026/market-statistics): 로그인 없이 HTTP 200 HTML 표 확인. 2026년 1~8월 Domestic market capitalisation(USD millions), Americas/APAC/EMEA 합계와 거래소별 자료가 있다. [2026년 9월판](https://focus.world-exchanges.org/issue/september-2026/market-statistics)은 2026년 1~7월이며 과거 호 목록은 2018년까지 공개돼 있다. 잡지 발행월과 관측월을 구분해야 한다.
- [공개 Dashboard](https://focus.world-exchanges.org/issue/september-2026/dashboard)는 세계 합계 스냅샷과 같은 기준월의 지역 자료를 표시한다. 세계 합계는 WFE가 공표한 지역 합계를 기준으로 집계하며 개별 거래소를 임의로 다시 더하지 않는다. Euronext·Nasdaq Nordic 등 여러 국가를 아우르는 거래소를 한 국가로 간주해서도 안 된다.
- [Statistics Portal](https://statistics.world-exchanges.org/)은 로그인 화면으로 연결된다. 등록 사용자용 일괄 시계열 추출이 있으므로 계정이 있으면 정규 다운로드 경로를 우선한다. 등록·이용 조건 및 외부 공개 재사용 범위는 실제 적용 경로별로 확인해야 한다. 이번 조사에서 회원가입이나 통계팀 연락은 하지 않았다.

## 자동 수집 전 해결할 점

- 공개 HTML 통계표가 현재 접근 가능하므로 연도별 월간 값을 모으는 구현은 가능하다. 관측월/단위/지역 합계/개정 빈티지를 검증하고 최신 보고서의 정정치를 우선해야 한다. World Bank 연간값과 이어 붙이지 않는다.
- 2026년 10월판 국내 시총 표 머리글의 다섯 번째 월이 `Mar'26`으로 잘못 표기돼 있다. 같은 값이 9월판에서는 `May'26`으로 표기된다. 숫자 순서만 보고 월을 추측하는 수집기를 만들면 안 된다. 해당 월은 명확한 다른 원문에서 확보하거나 오류로 남기고, 확인된 개정만 반영해야 한다.
- 원문은 특정 거래소의 두 달 이하 연속 누락에 대해 WFE가 보간했다고 명시한다. 대시보드가 직접 보간하지 않더라도 원자료에 추정이 포함될 수 있음을 설명해야 한다.
- Focus의 공식 차트가 참조하는 공개 Google workbook도 실제 다운로드 확인했다. 다만 `DMC` 시트의 값은 2013~2018년에 머무르고 `DMC table`도 2018년 표여서 최신 자동 수집 소스로 부적합하다. 다른 시트가 최신이라는 이유만으로 오래된 시총 시트를 최신으로 판단하지 않는다.

추천 경로는 WFE 공개 월간 통계 원문 또는 등록 후 정규 통계 포털이다. 한국은 ECOS 월별, 일본·중국·미국 등은 거래소별 월보로도 보완할 수 있지만 국가 합계·거래소 합계·지수 시총의 범위가 다르므로 각각 구분해야 한다.
