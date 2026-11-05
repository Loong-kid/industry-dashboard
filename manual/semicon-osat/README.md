# 패키징·테스트 서비스

화면: 반도체 → 소부장 → 패키징·테스트 → 전체 비교 / 국내 / 글로벌.

국내 6사(두산테스나·하나마이크론·SFA반도체·LB세미콘·네패스·네패스아크)와 Amkor·ASE를 사업 역할 기준으로 선정했다. 장비 판매사·기판·소켓 제조사를 같은 서비스 비교군에 넣지 않는다. 시총 순위나 투자 추천이 아니다. 회사별 공식 사업·공시 URL과 연결 범위는 `companies.json`에 있다.

`python scripts/fetch_semicon_osat.py --refresh`는 최근 2개년 DART·SEC 원문을 재확인하고 기존 성공 이력을 보존한다. `--full-history`는 DART API 제공 2015년 이후 원문과 비교열의 2014년 수치를 포함해 전 이력을 확인한다. `--from-state`는 저장된 상태로 그래프를 재생성한다. GitHub Actions의 `DART_API_KEY` Secret을 사용하며 공개 파일·로그·원문 URL에 API 키를 저장하지 않는다.

국내 재무는 연결 우선이며 공시되지 않으면 별도로 표시한다. 실제 분기와 완결 연도를 구분한다. 매출·영업이익의 실제 3개월 값을 우선하며 4분기 및 누적 현금흐름은 동일 회계연도·연결 범위의 누적−직전 누적으로 계산한다. 공란·역전·불일치 기간은 0이나 임의 추정값으로 채우지 않는다. CAPEX는 유형자산 취득 현금지출이며 무형자산·M&A·비현금 리스는 포함하지 않는다.

Amkor는 SEC US-GAAP companyfacts의 원통화 USD를 사용한다. ASE는 SEC IFRS companyfacts에서 연간 TWD 매출·영업이익·유형자산 총취득 지출을 읽고, 공식 6-K 실적 발표 표에서 분기 매출·영업이익 및 **Net payments for property, plant and equipment**를 읽는다. ASE 연간 총취득과 분기 순지출은 **별도 카드**로 제공하고 같은 CAPEX 시계열로 연결하지 않는다. Equipment CAPEX의 USD 발표값을 TWD로 임의 환산하지 않는다. ASE 전사에는 ATM뿐 아니라 EMS가 포함된다. 이후 발표의 수정 비교 분기는 반영하되 미래 공시를 사용하지 않는다.

ASE는 2018년 통합 이후 분기, 네패스아크는 2019-04-01 분할 설립 이후 확보 기간부터 표시한다. 다른 법인 실적을 붙여 2014년까지 늘리지 않는다. 2018년 ASE 연간은 통합 전후가 포함된 전환기다. 하나마이크론과 하나머티리얼즈, 네패스와 네패스아크 등 연결 실적의 단순 합산은 중복을 만들 수 있다.

상태는 `data/semicon/osat_state.json`, 공개 비교표는 `osat_universe.json`, 그래프 25개는 `company_osat_*.json`이다. 기업별 과거 원문·계산 구성요소·통화·기간을 저장하고 각 포인트에 원문 링크를 제공한다. 조회 실패 시 마지막 성공 자료와 실패 표시를 유지한다. `update-semicon-osat.yml`이 매일 09:15 KST 실행되며 GitHub 대기에 따라 실제 실행 시각은 늦어질 수 있다.

검증: `python -m unittest discover -s scripts -p test_semicon_osat.py -v` 및 `python scripts/run_ci_tests.py`.
