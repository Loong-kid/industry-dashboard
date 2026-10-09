# ESS 셀 업체 공장별 생산능력

검토일: 2026-10-10. 원장 `manual/ess_cell_factories.json` →
`scripts/aggregate_ess_factories.py` → `data/ess/ess_cell_factories.json`.
같은 게시 스크립트가 기존 시스템 공장 원장도 계속 검증한다.
ESS 셀·모듈 물량 추이 다음, 개별 기업 재무지표 앞에 표시한다.

## 기준

- CATL 4개, LG에너지솔루션 7개, 삼성SDI 2개, SK온 2개: 총 15개 시설·라인·프로젝트 기록. 전체 공장을 망라하지 않는다.
- ESS 전용 설치능력과 ESS 계획에는 회사·발행사 자료의 연간 GWh만 넣는다. 출하량, 계약 물량, 지역 합계, EV 합산은 대체 자료가 아니다.
- EV 포함 전체 공장 수치, 과거 계획, 증권사 추정은 참고 CAPA 열에 별도 표시한다. 설치능력과 더하거나 지분으로 환산하지 않는다.
- 나트륨이온은 LFP와 구분한다. CATL 푸딩 40GWh는 회사가 가동 중이라고 발표한 나트륨이온 증설 능력이며 푸딩 전체 LFP 능력이 아니다. ESS 발표에 포함돼도 ESS 전용 배분을 명시하지 않은 푸딩 40·지닝 160은 참고 CAPA에 둔다.
- 계획 기한이 지났어도 양산 완료를 확인하지 못하면 계획으로 유지한다. 기존 EV 공장의 가동과 ESS 라인의 양산을 구분한다.
- 출처별 확인 시점과 PDF 실제 페이지를 표기한다. 미확인은 0이 아니다. 연면적과 부지도 혼용하지 않는다.

## 사용자 수치 확인

| 수치 | 판단 | 근거 |
|---|---|---|
| CATL 현재 ESS 100GWh | 공식 글로벌 ESS 전용 수치 미확인 | [CATL 지닝 1기 발표](https://www.catl.com/en/news/6472.html)의 60GWh는 2025년 EV·ESS 합산. 공장별 자료로 글로벌 ESS 100을 확정할 수 없음 |
| CATL 2028년 ESS 720GWh | 해당 회사 발표·원출처 미확인 | [13개 생산기지 소개](https://www.catl.com/news/8368.html), [2026 나트륨이온 발표](https://www.catl.com/en/news/6861.html), 연차 자료 및 한·영·중 검색에서 해당 조합을 확인하지 못함. 틀렸다고 단정하거나 목표값을 생성하지 않음 |
| 삼성SDI 울산 10GWh | 증권사 ESS 추정에는 있음. 회사 직접 공시 미확인 | [IBK 2026-02-03, PDF 1쪽](https://file.alphasquare.co.kr/media/pdfs/company-report/20260203071133833_ko.pdf#page=1)은 ESS 10GWh로 추정. [2023-10-26 딜사이트](https://dealsite.co.kr/articles/111891)의 10은 EV·ESS 합산 |
| 삼성SDI 미국 23GWh | 역사적 EV 셀·모듈 최초 계획 | [2022 회사 발표](https://www.samsungsdi.com/sdi-now/sdi-news/2765.html), 이후 [2024 ESG, PDF 10쪽](https://www.samsungsdi.com/upload/download/sustainable-management/2024_Samsung_SDI_Sustainability_Report_Korean.pdf#page=10)에서 EV 1공장 33GWh. [2025 3Q 발표](https://samsungsdi.com/sdi-now/sdi-news/4562.html?idx=4562)의 미국 ESS 약 30GWh는 2026년 말 지역 목표 |

## 핵심 공장별 원문

- LGES 발행사 [2026-03-25 투자설명서 PDF 11쪽](https://links.sgx.com/FileOpen/LGES%20-%20Final%20Offering%20Circular%20%28March%2025_2026%29.ashx?App=Prospectus&FileID=69099#page=11), [82쪽](https://links.sgx.com/FileOpen/LGES%20-%20Final%20Offering%20Circular%20%28March%2025_2026%29.ashx?App=Prospectus&FileID=69099#page=82): 미시간 ESS LFP 16.5GWh·2025년 5월 양산, 캐나다 2025년 11월·폴란드 12월 ESS LFP 셀 생산, 오창 ESS LFP 2027년 1GWh 계획.
- [LGES 2026-08-19 랜싱 발표](https://www.lgcorp.com/media/release/30470): 랜싱 EV·ESS 병행 생산 개시, 본격 가동 시 전체 >35GWh 목표. 북미 5개 거점 ESS LFP 합계 >50GWh는 지역 목표로 분리. 회사 발표상 NextStar는 단독 소유.
- [SK온 2026-02-12 서산](https://askinno.com/archives/157723): 2공장 전체 6GWh 중 2개 라인 ESS LFP 3GWh 전환 계획. 6과 3 합산 금지.
- [SK온 2026-08-31 미국 계약](https://askinno.com/archives/170702): 조지아 셀 공급, 2027–2031년 총 9GWh 계약. 미국 기존 전체 약 100GWh나 계약량을 개별 ESS 공장 CAPA로 배분하지 않음. NeoVolta의 Pendergrass 팩 조립 공장과 구분.

## PDF 검증 기록

원문 PDF를 내려받아 관련 페이지를 렌더링하고 확인했다. 원문은 공개 사이트에 중복 배포하지 않는다.

| 문서 | SHA-256 | 검토 PDF 페이지 |
|---|---|---|
| LGES 2026 Offering Circular | ee1952302b14b94d8ef5f01df74b7adb33ef23b613973c5acab08c26b6dc9001 | 11, 82, 86 |
| IBK 삼성SDI 2026-02-03 | 735bab6c2b2038df3f55c345a033e015a5505d216c543ba22284d4881af3eb9f | 1 |

2022년 키움 자료의 PDF 25쪽에는 2030년 EV 생산능력 전망 막대그래프가 있었다.
이 오래된 EV 전망을 2028년 ESS 720GWh 회사 목표의 근거로 사용하지 않았다.
