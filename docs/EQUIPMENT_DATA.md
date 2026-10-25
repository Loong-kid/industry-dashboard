# 반도체 장비 실적

장비는 전체 요약 / 전공정 / 패키징·후공정 / 검사·계측 / 테스트로 구분한다.
기업의 대표 장비 분야에 따른 탐색 분류이며, 전사 연결 재무를 해당 공정 매출로 해석하지 않는다.
MOCVD의 기존 수요·공급 화면은 전공정 하위 보기에서 유지한다.

| 분야 | 기업 | 연결 손익 / 투자 통화 |
| --- | --- | --- |
| 전공정 | Lam, Applied Materials, ASML, Tokyo Electron, ASM International, SCREEN | USD / EUR / JPY |
| 패키징·후공정 | DISCO, Besi, 한미반도체 | JPY / EUR / KRW |
| 검사·계측 | KLA, Camtek | USD |
| 테스트 | Advantest, Teradyne | JPY / USD |

각 기업에 매출·보고 영업이익·CAPEX 카드를 나란히 제공한다. 회계연도와 원통화 백만 단위를 보존하며 조정 영업이익을 섞지 않는다. KLA만 영업이익 소계 미공시 기간을 동일 공시 문맥의 GAAP 영업항목으로 계산한다. Teradyne 과거 XBRL의 달력 말일 비교 태그는 해당 회계연도 10-Q/10-K의 실제 종료일로 검증해 중복 분기를 제거한다.

## 갱신 범위

`update-equipment.yml`은 매일 KST 08:30 및 화면의 장비 실적 확인 버튼으로 실행한다.

- Lam / AMAT / KLA / Teradyne: SEC Company Facts 분기·연간 자동 수집.
- ASML / Camtek: SEC Company Facts 연간 자동 수집. 공식 분기 IR의 이미지/본문 자료는 원문 대조 후 검토 스냅샷으로 반영.
- 한미반도체: 기존 DART 비밀키를 이용해 OpenDART 연결 공시 수집. 누적 현금흐름과 손익은 동일 회계연도 안에서 차분. 별도 재무제표로 대체하지 않음.
- TEL / ASM / SCREEN / DISCO / Besi / Advantest: 아래 공식 IR 자료의 검토 스냅샷. 새 분기는 원문 확인과 import 후 반영하며, 버튼을 누르는 것만으로 새 IR 분기가 추가되지는 않음.

검토 기준일은 2026-10-25. 원문 실패 시 마지막 성공 자료와 기준일을 유지한다. 카드의 집계 기준과 갱신 주기에 수집 방식을 명시한다.

## 원문과 재현

`manual/equipment_ir_sources.json`: 다운로드 원문 URL, 회계연도, 분기, 파일 종류.
`manual/equipment_reviewed.json`: 이미지/본문 표, 접근이 제한된 발행사 자료의 검토 수치 및 출처.
`manual/equipment_global.json`: 파싱 결과와 원문 SHA-256. 원본 파일은 무시되는 `.cache/equipment/`에만 저장한다.

원문 검토 후 매니페스트를 갱신하고 다음을 실행한다. 웹 구조·단위·표 열 순서가 바뀌면 파서를 확인한다.

```sh
pip install requests beautifulsoup4 openpyxl pymupdf
python scripts/import_equipment_ir.py --download
python scripts/fetch_equipment_companies.py --offline
python -m unittest discover -s scripts -p test_equipment_companies.py -v
```

ASML/Camtek 재현에 필요한 SEC Company Facts JSON도 매니페스트에 포함한다. 한미반도체 원본은 `manual/equipment_hanmi.json`이다.

## 자료 범위와 주요 정의

- [ASML 2026 Q3 US GAAP 재무표](https://www.sec.gov/Archives/edgar/data/937966/000162828026065813/financial_statementsxusx.htm): 5개 실제 분기 종료일, 장비 시스템·서비스/필드 옵션 매출. IFRS와 혼합하지 않음.
- [TEL 데이터북](https://www.tel.com/ir/library/db/index.html)과 [결산자료](https://www.tel.com/ir/library/report/index.html/): FY2016–2026 연간, FY2022 이후 분기. CAPEX는 연간 CF의 유형자산 현금취득이므로 연간 기본 표시.
- [ASM 결과 센터](https://www.asm.com/investors/results-center): 2022 Q1 이후 확보 분기. 2023 헤드라인의 Normalized profit 대신 부속 표 Operating result 사용. 예전 CF는 천 유로, 최근 CF는 백만 유로. CF 첫 두 열은 개별 분기, 뒤의 두 열은 누적. 미확보 2022/2024 Q4는 빈 값이며 불완전 연간은 생성하지 않음.
- [SCREEN 재무 하이라이트](https://www.screen.co.jp/en/ir/finance): FY2022–2026 연간, SPE 부문은 십억 엔 반올림 값을 백만 엔으로 변환. 연간 CAPEX는 회사 공시 설비투자 정의. [최신 발행사 결산자료 보존본](https://financialfilings.com/filings/screen-holdings-co-ltd/earnings-release/2026/55965510/)의 FY2027 Q1 및 전년 동기 분기 손익을 추가. 분기 이력은 제한적임.
- [DISCO 데이터북](https://www.disco.co.jp/eg/ir/library/doc/fr/fr20261022.xlsx): 2014년 이후 분기·연간. CAPEX는 회사 공시 설비투자 정의. Shipment는 비연결 출하액이며 연결 매출과 구분.
- [Besi 공식 발표](https://www.besi.com/investor-relations/press-releases/2026/): 정확한 천 유로 부속 표 및 수주 반올림 표. CAPEX는 별도 자산화 개발비·투자부동산 취득을 제외. [발행사 Q4 2025 실적 보존본](https://cdn.financialreports.eu/financialreports/media/filings/3819/2026/RNS/3819_rns_2026-02-19_72ffa68c-9cc6-42ac-a533-b2f8269ac0b4.pdf)의 2025 CAPEX는 15.795백만 유로.
- [Camtek 공식 IR](https://www.camtek.com/investors/): 확보된 2024 Q4 이후 일부 분기 손익은 본문 백만 달러 반올림 값. CAPEX는 연간 SEC CF 기준.
- [Advantest 결산자료](https://www.advantest.com/en/investors/ir-library/result/): 2021년 6월 이후 IFRS 누적 손익·유형자산 현금취득을 차분.
- DISCO/Advantest FY는 시작 연도, TEL/SCREEN FY는 종료 연도. 화면 라벨에 각 회사 관행을 유지.

분기 미확보는 null로 표시하며 선을 연결하지 않는다. 연간을 4로 나누거나 누락을 0으로 채우지 않는다. 연간만 있는 TEL/SCREEN/Camtek CAPEX는 연간 선택만 제공한다. 미완료 연도는 연환산하지 않는다.
