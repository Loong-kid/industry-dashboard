# ESS 기업 지표

ESS 탭에서 기존 미국 EIA 카드 5개와 테슬라·선그로우·플루언스의 기업 지표를 함께 표시한다. 전력 탭의 지표는 유지한다. 통화 환산·기업 순위·추정 설치량은 생성하지 않는다.

## 공개 범위와 표시

| 회사 | 매출 | 영업손익 | 물량 | 수주 지표 |
|---|---|---|---|---|
| Tesla | 에너지 발전·저장 부문, 태양광 포함. 분기·연간 | 부문 영업이익 미공개 | 공표 분기 배치량. 누계는 **2019 Q1 이후 공개 분기 합계**이며 전체 누적 설치량·가동 용량이 아니다 | 에너지 부문 장기 RPO. 최초 계약기간 1년 초과 계약 등 제한된 범위 |
| Sungrow | ESS 부문 반기·연간. H2는 연간−H1 | 부문 영업이익 미공개. 영문 Operating income(营业收入)은 이 표에서 매출이다 | 연간 **출하량**만 별도 표시. 분기 배치·기준일이 명확한 누적 배치 시계열은 미확인 | 전사 ESS의 비교 가능한 backlog/intake/pipeline 정기 총계 미확인 |
| Fluence | ESS 솔루션 / 연결, 분기·연간 선택 | **연결 계산 소계**. 매출총이익−R&D−판매마케팅−일반관리−영업 D&A. 이자·기타손익·세금 제외. 회사 공표 영업이익 소계·ESS 솔루션만의 이익·조정 EBITDA가 아니다 | 공표 누적 Deployed(GWh), 인접 분기 누적 차이로 계산한 **순증**. 폐기·정정이 반영될 수 있어 총 신규 설치량과 다르다 | 금액 backlog/intake(연결), ESS 계약 잔고 GW, ESS 미계약 pipeline GWh/GW, ESS 신규 계약 GWh/GW |

Fluence는 9월 결산이다. **FY2026 Q1=2025년 10~12월, Q2=2026년 1~3월, Q3=2026년 4~6월**이다. 실제 날짜를 저장하고 화면·차트·표에는 회계 분기를 표시한다. 매출 인식 기준 GWh, 서비스·디지털 AUM, 공장 생산능력은 배치량으로 사용하지 않는다. GW와 GWh는 지속시간이 없으면 환산하지 않는다.

## 수집과 검증

- `scripts/ess_company_sources.json`: 공식 과거 보고서 URL과 이미지표 대조 전사값. 제3자 추정값 없음.
- `scripts/fetch_ess_companies.py`: 보고서 파싱, 기간·단위 검증, 정규화 이력, 기업별 검증 후 발행. `data/_ess_companies/observations.json`에 URL·기간·원문 SHA-256·출처별 관측값을 보존한다. PDF/HTML 원문 바이너리는 저장소에 포함하지 않는다.
- Tesla 신규 분기 IR deck은 해당 기간의 10-Q/10-K 제출이 확인된 뒤 공식 asset 경로에서 확인한다. 분기 종료만으로 미발표 재무자료를 발행하지 않는다. 에너지 RPO도 SEC 제출 목록에서 10-Q/10-K를 발견해 공식 Tesla PDF를 읽는다. 재무자료보다 먼저 발표되는 배치량은 확인한 공식 발표를 출처 등록한다.
- Fluence 신규 실적 발표는 공식 RSS에서 발견한다. 과거 정정은 이후 비교 공시를 우선한다. FY Q4 직접 수치가 없으면 같은 회계연도 연간−9개월로 계산한다.
- Sungrow 신규 반기·연차보고서는 공식 CNINFO 공시 목록에서 발견한다. 영문·중문 모두 제품별 매출 표에서 ESS를 식별한다. 반기/연간 물량을 분기로 임의 분배하지 않는다.
- Fluence FY2026 Q3 보충자료 p.2~3는 이미지표이다. 자동 OCR 수치로 발행하지 않고 원문을 렌더링해 대조한 전사값을 사용한다. 매출의 ESS 솔루션 보기와 신규수주 용량 보기 등은 이 자료의 반올림 값이다. 출처·확인일을 명시한다. 연결 매출의 새 분기보다 부문 매출 확인이 늦으면 부문 보기에서 추가 확인 필요를 표시한다. 새 보충자료의 과거 정정도 별도 원문 검증이 필요하다.
- 새 공시 발견 실패는 화면에 경고한다. 파싱 실패 시 해당 기업의 기존 카드와 정규화 이력을 보존하고 다른 기업은 계속 수집한다. 기존 관측값 삭제·null 대체·관측일 후퇴는 발행을 거절한다. 미공개 항목은 명시적 미공개 카드이며 0·추정값으로 채우지 않는다.
- 매일 KST 07:30 기존 `update-data` 워크플로에서 테스트 후 수집한다. `--offline --reuse-raw --raw-dir ...`는 로컬 개발용이며 스케줄에서 사용하지 않는다.

## 공식 자료

- [Tesla IR](https://ir.tesla.com/) · [2026 Q2 10-Q 에너지 RPO](https://ir.tesla.com/_flysystem/s3/sec/000162828026049270/tsla-20260630-gen.pdf#page=12)
- [Sungrow 2025 Annual Report](https://disc.static.szse.cn/disc/disk03/finalpage/2026-06-08/aef7994f-21d4-49d4-8738-984e86a61c33.PDF) · [2026 반기보고서](https://disc.static.szse.cn/disc/disk03/finalpage/2026-08-29/e9a7008a-d6d2-456d-84ae-da985a0212d9.PDF)
- [Fluence FY2026 Q3 실적](https://ir.fluenceenergy.com/news-releases/news-release-details/fluence-energy-inc-reports-third-fiscal-quarter-2026-results) · [FY2026 Q3 보충자료](https://ir.fluenceenergy.com/static-files/88b278a4-9215-4c0a-9c33-ca0339ecb458)

2026-06-30 Fluence: 연결 매출 649.848백만 USD, ESS 솔루션 매출 627.3백만 USD, 연결 계산 영업손익 -57.520백만 USD. 누적 19.3GWh, 분기 순증 0.1GWh. 금액 수주잔고 약6,400백만 USD, 분기 신규수주 약1,441백만 USD. ESS 신규수주 8.3GWh/2.6GW, 계약 잔고 12.6GW, 미계약 파이프라인 163.7GWh/45.6GW. 공급계약의 master agreement·계약 전 award를 실제 설치·확정 신규수주로 합산하지 않는다.

선그로우의 개별·지역별 계약 발표는 존재한다. [2025-08-29 중남미 ESS 누적 계약 10GWh](https://www.sungrowpower.com/de/en/newsdetail/6658)는 지역 누적 계약이지 미이행 글로벌 수주잔고가 아니다. 전사 합계로 합산하지 않는다.
