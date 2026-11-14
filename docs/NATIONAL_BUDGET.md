# 국가예산

`#/national_budget/kr` / `#/national_budget/us`. 기존 DARPA의 카드 크기를 유지하되 국가 전체의 공식 분야 분류를 사용한다. 2014년부터 총액·분야별 막대·연간 행렬, 선택 분야의 부처·사업 검색/페이지 이동, 중장기 전망을 제공한다. 세부사업은 선택 분야의 JSON만 요청한다. 최초 진입 자료는 국가당 약 17–22 KB이며 전체 계정 이력을 첫 화면에 받지 않는다.

## 한국

- [열린재정 세부사업 예산편성현황(총지출)](https://www.openfiscaldata.go.kr/op/ko/sd/UOPKOSDA01?odtId=5Y5A50K2L4CW2IRKI2J0F2C8T): 공식 웹 Sheet가 사용하는 익명 공개 JSON 다운로드. 일반 예산과 기금을 함께 선택하고 **총지출** 기준을 사용한다. 본예산과 정부 제출안을 별도 보관한다. 원 단위는 천원 → 조원. 추경·내부거래·보전지출을 본예산에 더하지 않는다.
- [16대 분야별 재원배분](https://www.openfiscaldata.go.kr/op/ko/sd/UOPKOSDA01?odtId=5JVB22KUDE71A1SMR67O50R63): 결산만 분리하여 분야 합계를 제공한다. 12대 정책 분야 및 R&D는 중복이 있어 16대 분류와 합산하지 않는다. `외교·통일`/`통일·외교`는 같은 분야로 연결한다. 결산의 사업 상세를 예산 상세로 대신 표시하지 않는다.
- [재정수지](https://www.openfiscaldata.go.kr/op/ko/sd/UOPKOSDA01?odtId=45DHAZ24H7WWJ0VG03Q666V46): 월 누계 중 **12월만 연간 실적**으로 사용한다. 최신 미완료 연도는 별도 누계 문장으로 표시한다. 공급원별 마감 시점이 달라 지출 결산과 수입·수지의 마지막 연도가 다를 수 있으며 차트에 실적 범위를 각각 표시한다.
- [2026–2030 국가재정운용계획, 2026-09-01 발표](https://mpb.go.kr/web/main/bbs/b_0001/2629): `manual/national-budget/kr_plan_2026-09.json`, 공식 PDF 9–11쪽을 검토해 입력했다. **2026년은 본예산 기준값**, 이후는 계획이며 확정 예산·결산이 아니다. 총수입·총지출·재정수지·의무/재량지출·국가채무를 보관한다. 새 계획 발표 시 원문을 검토하고 새 `kr_plan_YYYY-MM.json`을 추가한다. 이 PDF 표는 자동 추출하지 않는다.

2026-11-15 등록 기준 본예산 2014–2026, 정부안 2014–2027, 분야 결산 2014–2025. 미확정 미래 본예산 열 전체가 원문에서 0으로 내려오면 해당 연도를 게시하지 않는다. 실제 개별 사업의 0은 유지한다. 이름·기관 개편으로 끊긴 사업 이력을 신규 사업으로 단정하지 않는다.

## 미국

- [OMB Public Budget Database](https://www.whitehouse.gov/omb/information-resources/budget/supplemental-materials/): `budauth_fy*.xlsx`, `outlays_fy*.xlsx`를 별도 집계한다. 원 단위 USD 천 → USD 십억. **Budget Authority는 지출 의무를 부담할 권한, Outlays는 지급 지출**이며 서로 대체하지 않는다. FY2027 판의 FY2025까지는 실적, FY2026–2031은 해당 정부 발표 당시 추계다. 과거 기관·계정은 최신 OMB 분류로 재작성된 이력이다.
- [Treasury MTS Table 9](https://fiscaldata.treasury.gov/datasets/monthly-treasury-statement/): 완료 회계연도 9월 자료에서 Net Outlays/Receipts 합계와 공식 기능 분야를 사용한다. 원 단위 USD → USD 십억. FY2026 총괄·분야 지출은 Treasury 결산으로 갱신하지만 계정 상세는 OMB 추계로 남아 있으므로 화면에 구분한다. 상계수입 등 음수도 포함해야 순지출 총액이 맞는다.
- [CBO Budget/Economic Data](https://www.cbo.gov/data/budget-economic-data) / [공식 데이터 저장소](https://github.com/US-CBO/cbo-data): `catalog.json`의 `ten_year_budget` 배포본을 발표 빈티지별로 보존한다. 독립기관의 **현행법 기준선**이며 대통령 예산 요청과 별개다. `historical_budget`에서 과거 총수입·지출·수지를 읽는다. 최신 2026-02 기준선은 2036년까지 제공한다. 전망 선택을 바꾸면 당시 발표본으로 비교할 수 있다.

미국 FY는 전년 10월–해당 연도 9월. 한국 달력연도와 기간이 같지 않다. 주·지방 자체 지출은 제외하며 연방의 이전지출은 연방 지출에 포함된다.

## 갱신·검증

`python scripts/fetch_national_budget.py` / `--offline` 캐시 재현 / `--refresh` 과거 원문까지 다시 확인. 일일 `update-national-budget` 워크플로는 KST 09:10 실행하며 API 키가 필요 없다. 공개 웹 JSON은 정식 API SLA가 없으므로 응답 형태가 바뀌면 수집기를 수정해야 한다. 닫힌 연도 캐시는 재사용하고 최근 한국 예산·최신 메타데이터·OMB 링크·Treasury 결산·CBO 배포 목록을 재확인한다.

원문은 `.cache/national-budget/`에 보관하고 공개 JSON에는 인증정보를 쓰지 않는다. 수집 실패 시 해당 국가의 마지막 성공 자료와 성공일을 유지하고 실패 상태를 표시한다. 오프라인 재현은 성공 확인일을 새로 찍지 않는다. 분야 합계·계정 합계·16/20 분류·연간 실적 범위를 검증한 뒤 국가 파일을 교체한다. `scripts/test_national_budget.py`와 `scripts/test_national_budget.cjs`는 네트워크 없이 실행된다. 국가 자료는 별도 경로이므로 기존 DARPA 자료와 집계를 바꾸지 않는다.
