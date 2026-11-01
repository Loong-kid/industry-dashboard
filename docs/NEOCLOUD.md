# 네오클라우드

데이터센터 → 미국 → 네오클라우드(`#/datacenter/us/neocloud`)에 CoreWeave(CRWV), Nebius(NBIS), IREN(IREN)을 표시한다. 기존 미국 지표 31개는 하이퍼스케일러(`#/datacenter/us/hyperscalers`)에 그대로 남긴다. 기존 `#/datacenter/us` 북마크도 하이퍼스케일러로 열린다. 한국의 테이블과 지표는 바꾸지 않는다.

미국은 상장 시장을 기준으로 묶은 분류다. CoreWeave는 미국, Nebius는 네덜란드, IREN은 호주 본사이며 모든 값은 글로벌 연결·공시 사업 기준이다. 미국 내 데이터센터만의 투자나 매출을 뜻하지 않는다. Lambda·Crusoe·Nscale 같은 비상장 기업의 추정 매출이나 미공개 분기를 임의로 채우지 않고, 공개 재무 이력을 계속 수집할 수 있는 세 기업을 우선 등록했다.

상단은 AI 클라우드 매출, 전사 GAAP 영업이익, 전사 GAAP 영업이익률, 전사 현금 CAPEX, ASC 606 RPO의 5개 기업 비교 차트다. 이름을 클릭해 여러 기업을 동시에 선택한다. CAPEX 비교는 막대다. 회사별로 매출·영업이익 통합 선택 차트, 클라우드 매출 비중, 전사 영업이익률, CAPEX, RPO를 나열해 총 20개 카드다. 모두 기존 기본 카드 너비와 220px 그래프 높이를 사용한다. 호버는 기간·수치만, 자세한 메모와 출처는 숫자 클릭·표·집계 기준 펼침에서 확인한다.

CoreWeave는 단일 보고 부문인 AI 클라우드 플랫폼의 연결 매출·GAAP 영업이익을 사용한다. 통합 차트의 전사·클라우드 두 항목은 동일한 범위로 선이 겹친다. 회사 정의 **Revenue backlog는 ASC 606 RPO보다 넓다**. 2026년 6월 말 RPO 103,700백만 달러를 사용하며 약 104십억 달러의 Revenue backlog를 RPO에 대입하지 않는다. PP&E 현금 취득도 리스·외상 취득을 포함한 경영진 CAPEX와 구분한다.

Nebius의 전사 값은 계속영업 연결이며 AI cloud 외 Avride·TripleTen 등을 포함한다. 매각된 러시아 Yandex·중단영업 Toloka를 현재 AI cloud에 연결하지 않는다. 전사 표와 AI 부문 값을 구분하고 최신 재작성 비교치를 우선한다. 2023~2025년 연간과 공개 분기를 표시하지만 과거 분기 합계는 후속 재분류된 연간과 다를 수 있다. 분기 자료는 비정형 6-K 실적·재무제표에서도 실제 날짜·기간·단위를 읽는다. 2025년 AI cloud 1분기 41.4, 2분기 93.7백만 달러는 후속 6-K 부문 공시를 포함해 확보했으며 성장률이나 ARR로 역산하지 않는다. 현금흐름표의 유형·무형자산 취득액을 CAPEX로 사용해 타사 PP&E 전용 지표와 범위 차이를 표시한다.

IREN의 전사는 채굴 사업을 포함한다. AI Cloud Services 매출만 별도로 분리하며 매출총이익·Adjusted EBITDA를 클라우드 영업이익으로 쓰지 않는다. US GAAP 기준 공개 이력으로 시작하고 과거 IFRS 이력을 접합하지 않는다. 6월 결산 FY를 실제 날짜와 함께 표시하며 Q4 누적 차분에는 같은 회계연도·공개된 GAAP 근거를 보존한다. RPO는 ASC 606만 사용하고 ASC 842 리스 계약을 더한 계약 총액으로 대체하지 않는다. 계약 체결일인 2025-11-02의 9.7십억 달러를 분기 말 RPO로 올리지 않는다.

Nebius와 IREN은 AI cloud 단독 GAAP 영업이익이 미공개라 통합 차트에서 해당 항목을 비활성화한다. 비교 차트의 영업이익·이익률은 **전사**라고 명시하며 별도 클라우드 이익률을 만들어내지 않는다. 연간 이익률·매출 비중은 연간 분자/분모로 계산하고, 분기 비율을 평균하지 않는다. RPO 연간은 실제 결산일 잔액이고 합산·차분·이월하지 않는다. 비교 축은 달력 분기와 FY 종료 연도로 정렬하되 표에는 각 회사의 실제 회계기간을 유지한다.

`scripts/fetch_neocloud.py`가 SEC Company Facts, 표준 XBRL 부문 사실과 Nebius의 6-K 표·RPO 주석을 수집한다. `manual/us-datacenter/neoclouds.json`에 기업·범위를, `data/datacenter/us_neocloud_state.json`에 검증된 정규화 값과 근거를, `us_nc_*.json`에 표시 자료를 저장한다. 새 공시 조회가 실패하면 이전 이력을 보존하고 실패 상태를 노출한다. API에 없는 과거 기간은 빈값이며 0이나 추정치로 채우지 않는다.

`update-neocloud.yml`이 매일 **KST 10:10**에 사전 검증 → 수집 → 사후 검증 → 네오클라우드 JSON만 커밋한다. 독립 concurrency, 재시도 push, `publish-data.yml` 후속 배포를 사용한다. 하이퍼스케일러의 KST 09:50 수집과 별도로 동작한다. 화면 갱신 버튼도 세부탭에 맞는 워크플로와 상태 파일을 선택한다.

검증: `python -m unittest discover -s scripts -p test_neocloud.py -v`, `node scripts/test_us_datacenter.cjs`, 전체 `python scripts/run_ci_tests.py`. `scripts/fixtures/neocloud`에는 IREN 2026 10-K의 관련 XBRL 사실·문맥과 Nebius Q1 2026 6-K의 재무 표·RPO 주석 발췌 및 원문 위치를 보관한다.

공식 출처: [CoreWeave IR](https://investors.coreweave.com/), [Nebius IR](https://nebius.com/investor-hub), [IREN IR](https://www.iren.com/investors). 개별 수치는 차트·표의 SEC 원문 링크에서 확인할 수 있다.
