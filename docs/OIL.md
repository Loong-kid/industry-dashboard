# 원유: 메이저 실적과 해양 시추

진입점은 `#/oil`이며, `원유 메이저`와 `해양 시추`로 나눕니다. 해양 시추의 시장·수급, 글로벌 리그, 계약 일정, 운영사 실적은 `#/oil/offshore/<view>`에서 제공합니다. 과거 `#/offshore/<view>` 링크는 새 주소로 연결합니다. 데이터 디렉터리 `data/offshore/`와 관심 리그 저장 키는 유지합니다.

## 수록 기업과 회계 기준

ExxonMobil, Chevron, Shell, BP, TotalEnergies, ConocoPhillips, Equinor의 연결 매출·영업손익·CAPEX를 기업별 3개 그래프로 표시합니다. 통화는 USD 백만이며 분기와 연간을 전환할 수 있습니다. 회사 전체 매출은 원유 단독 매출이 아닙니다. ConocoPhillips는 탐사·생산 중심이며 통합 정유사와 사업 범위가 다릅니다. 회사 간 매출을 합산하거나 시장 점유율로 환산하지 않습니다.

- ExxonMobil·Chevron·ConocoPhillips: 원문 손익계산서의 매출 − 총 비용 + 별도 표시 이자비용으로 **계산한 영업손익**입니다. 지분법 이익과 기타 매출 외 수익은 제외하고 비금융 기타 비용은 포함합니다. 별도 공시 GAAP Operating income이나 Adjusted earnings로 표시하지 않습니다. 옛 Chevron 손익계산서에서 이자비용을 별도 표시하지 않은 기간은 추가 가산하지 않습니다.
- Shell: 세전손익 + 이자비용 − Interest and other income으로 계산합니다. 관계사·JV 손익은 포함하며 이자와 기타수익을 제외합니다. 회사의 Adjusted earnings·EBITDA가 아닙니다.
- TotalEnergies: 소비세 제외 매출 − 매입 − 기타 영업비용 − 탐사비 − 감가·손상 + 기타수익 − 기타비용입니다. 금융손익·지분법손익·법인세는 제외합니다. Adjusted net operating income과 다릅니다.
- BP: 공시 Profit before interest and taxation입니다. Underlying replacement-cost profit과 구분합니다. 해당 연도 분기 공시를 기준으로 하며, 2015년 매출은 Q4 공시의 수정 주석에 따라 2016년 동기 비교 수치로 갱신합니다.
- Equinor: 공시 Net operating income입니다. 2014–2015년은 회사가 2016년 발표한 USD 환산 엑셀을 사용하고, 이후 USD 분기 보고서와 연결합니다. NOK 원문을 그대로 이어 붙이지 않습니다.

CAPEX는 회사별 현금흐름표 항목을 유지합니다. ExxonMobil은 유형자산 현금취득, Chevron은 Capital expenditures, Shell은 Capital expenditure, BP는 유형·무형·기타 자산 취득, TotalEnergies는 유형·무형자산 취득, COP·Equinor는 Capital expenditures and investments입니다. Shell Cash capital expenditure, BP Total cash capital expenditure, 인수대금, 비현금 자산 증가와 혼동하지 않습니다. 각 카드에 정의와 원문 링크를 제공합니다.

2014년부터의 완결 연간을 수록하며, 진행 중인 연도 누적을 연간으로 표시하거나 연간을 4등분하지 않습니다. 분기 공시와 후속 비교 공시의 재작성·반올림 차이는 존재할 수 있습니다. 검증 가능한 독립 분기는 직접 사용하고, 누적만 있는 현금흐름표는 같은 연도 누적 차이로 계산합니다. 결측은 0으로 만들지 않습니다.

2026-10-27 초기 수록은 7개 기업 각각 2014 Q1–2026 Q2의 50개 분기와 2014–2025의 12개 연간입니다. Shell의 과거 6-K 첨부파일도 회수했으며, 2014년 현금 CAPEX는 후속 비교 공시의 수정값 31,676을 사용합니다. 이 수치는 당시 연차보고서의 31,854와 구분됩니다. 회사 공시 수정값을 반영한 모든 완결 연도의 분기 합계·연간은 USD 백만 단위 반올림 허용 범위에서 일치하는지 검증합니다.

ExxonMobil은 2026년 7월 지주회사 전환 전후 CIK 34088 / 2115436을 하나의 그룹 이력으로 연결합니다. 승계 법인의 Q2와 종전 법인 이력을 중복 합산하지 않습니다. [승계 공시](https://www.sec.gov/Archives/edgar/data/2115436/000119312526291990/d71068d8k12b.htm).

## 출처와 갱신

- [SEC 공개 Company Facts](https://www.sec.gov/edgar/sec-api-documentation)와 제출 원문의 손익·현금흐름표. 같은 XBRL 매출 태그가 매출과 기타수익 포함 합계에 중복 사용되는 사례는 실제 표의 행으로 구분합니다.
- [Shell Databook](https://www.shell.com/investors/results-and-reporting/data-supplements.html) 및 SEC 분기 재무제표 첨부파일.
- [TotalEnergies 분기 Accounts](https://totalenergies.com/investors/results): 원문의 부호·분기·연간 열을 구분하고 PDF 페이지를 연결합니다.
- [Equinor 분기 보고서](https://www.equinor.com/investors/quarterly-results), [회사 제공 USD 과거 자료](https://www.equinor.com/investors/information-for-analysts). PDF 열 좌표로 Note 번호와 분기 수치를 구분합니다.

`manual/oil/source_files.json`에 공식 IR 파일 주소를 기록합니다. 원문은 `.cache/oil/`에만 보관하며 웹 배포 대상이 아닙니다. `data/oil/state.json`에는 파싱한 행과 출처·계산 근거를 보관합니다. 과거 원문 캐시가 없는 자동 갱신에서도 검증된 기존 이력을 보존합니다.

`update-oil.yml`은 매일 KST 08:35에 원문을 확인합니다. 기업별 수집 실패는 마지막 성공 자료를 보존하고 실패 상태를 표시합니다. 새 공시 여부를 확인한 날짜와 실적 종료일은 구분합니다. 해양 시추 갱신은 기존 `update-offshore.yml`로 연결합니다.

## 다음 정유 탭 후보

| 우선 | 기업 | 선정 이유와 분리할 항목 |
|---|---|---|
| 1 | Valero · VLO | 정유 실적 비교의 중심. Refining과 Renewable Diesel·Ethanol을 분리합니다. |
| 2 | Marathon Petroleum · MPC | 대형 미국 정유사. 전사 연결에 포함되는 MPLX 미드스트림과 Refining & Marketing을 나눠 봅니다. |
| 3 | Phillips 66 · PSX | 정유 외 Midstream·Chemicals·Marketing & Specialties·Renewable Fuels가 섞입니다. 정유 부문 손익과 전사 CAPEX를 구분합니다. |
| 국내 | S-Oil | 정유·석유화학·윤활 사업의 매출과 영업이익을 공개합니다. 통화는 KRW로 유지하고 미국 기업과 통화 혼합 합산하지 않습니다. |

정유 신규 화면은 이번 변경에 포함하지 않습니다. 다음에는 연결 실적 3종과 정유 부문 이익, 처리량·가동률·배럴당 마진을 함께 구성하는 것이 적절합니다.

근거: [Valero 부문별 실적](https://investorvalero.com/news/news-details/2026/Valero-Energy-Reports-2025-Fourth-Quarter-and-Full-Year-Results/default.aspx), [MPC 2025 Annual Report](https://www.marathonpetroleum.com/content/documents/Investors/Annual_Report/2025_MPC_Annual_Report_and_10K.pdf), [Phillips 66 Annual Report](https://www.sec.gov/Archives/edgar/data/1534701/000119312526139125/d64580dars.pdf), [S-Oil 사업별 매출·영업이익](https://www.s-oil.com/en/relation/ir/Revenue.aspx).

## 검증

`test_oil.py`는 2025년 원문 매출·현금투자 앵커, ExxonMobil 승계, Equinor PDF 열과 달러 전환, 위치 지정 XHTML의 매출 행 분리, 결측과 출처, 기존 시추 경로를 검증합니다. `verify_oil_ui.py`는 PC·모바일의 21개 카드, 분기·연간, 원문 링크, 고정 기간 버튼, 해양 시추의 새·기존 주소를 확인합니다. 기존 해양 시추·미드스트림 검증도 함께 실행합니다.
