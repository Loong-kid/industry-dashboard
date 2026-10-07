# 마스크 패터닝 장비 업체 검토

확인일: 2026-10-07. 이번 변경은 패터닝 업체 차트 4개까지이며 아래 장비 지표는 추가 구현하지 않았다.

## 업체와 공시 범위

| 업체 | 제품/범위 | 확보할 수 있는 정량 지표 | 판단 |
|---|---|---|---|
| JEOL | 단일빔 마스크 장비, IMS와 협력하는 멀티빔 마스크 장비. Industrial Equipment에는 spot-beam 직접 묘화 등 다른 장비도 포함 | 산업기기 매출/이익, 연결 수주·잔고, 일부 제품 수주/매출 지수 | 마스크 전용 매출·대수와 구분해야 함. 제품별 컨콜 설명을 함께 보관 |
| NuFlare | 전자빔 마스크 묘화, 마스크 검사, 에피 성장 장비 | 과거 상장 공시, 현재 기술 로드맵·제품 발표. 최신 분기 마스크 전용 수주/매출의 지속 공개는 미확인 | JEOL과 함께 기억한 회사의 후보. 2020년 상장폐지 이력 때문에 최근 분기 시계열 접근성이 제한됨 |
| IMS Nanofabrication | 멀티빔 마스크 장비, JEOL과 전략적 협력 | 기술 세대·신제품·증설 발표. 독립된 공개 분기 재무 시계열은 이번 확인 범위에서 미확보 | JEOL과 독립 경쟁사로 단순 합산하면 안 됨 |
| Mycronic | 레이저 마스크 장비. Pattern Generators는 반도체·디스플레이 및 서비스 등을 포함 | 사업부 수주액·잔고·매출, 모델별 수주/납품/잔고 대수, 예정 납기 | 정량 추적 우선 후보. 전체 회사 수치와 구분해야 함 |

## 공식 자료에서 확인한 사례

### Mycronic 2026 Q2

공식 분기보고서 PDF 4쪽, 분기 과거 표는 22쪽:
https://storage.mfn.se/c8f3d92b-f205-4f1a-9552-77f0d11afede/interim-report-january-june-2026.pdf

- Pattern Generators 수주 SEK 675m, 매출 SEK 905m, 잔고 SEK 1,706m.
- 부문 수주/매출로 계산한 book-to-bill은 약 0.746. 순수 마스크 장비만의 값이 아니라 해당 부문 전체 기준.
- 당분기 SLX 수주 4대. 그중 맞춤형 1대는 USD 27~30m이며 비반복 거래라고 명시.
- 잔고에 시스템 13대. 납품계획: 2026 Q3 5대, Q4 3대, 2027 Q1 3대, Q2 1대, 2028 1대.
- 당분기 납품 5대: Prexision 8 Evo 1대, Prexision 8 Entry Evo 1대, Prexision Lite 8 Evo 2대, MMX 1대. 모델/용도 구분 없이 5대 전체를 반도체 증설로 읽으면 안 됨.
- 2026 Q1 납품한 Prexision 8000 Evo가 Photronics 한국 사업장에서 가동에 들어갔다고 발표: 장비 수주→납품→패터닝 업체 생산으로 연결할 수 있는 사례.
- 신규 증설과 노후 장비 교체, 단가·제품 구성, 서비스 매출을 구분해야 함. 분기 수주 변동은 큰 거래 하나로 흔들려 TTM도 함께 보는 것이 적절하다는 분석 판단.

공식 실적 발표/웹캐스트:
https://www.mycronic.com/news-events/our-press-releases/interim-report-january-june-2026/

### JEOL

최근 2026년 4~6월 설명자료 PDF 7쪽:
https://www.jeol.com/assets/pdf/ir/financial_results/financial_results_briefing_2026_1q_en_dibwU8.pdf

- Industrial Equipment 매출 50억 엔(전년 145억 엔, -65.6%), 영업이익 2억 엔(전년 72억 엔).
- 멀티빔 장비 프로젝트의 매출 인식 시점, 단일빔 장비 수출통제 영향, spot-beam 장비의 견조한 수주를 별도로 설명.
- 따라서 이 사업부 매출 감소를 블랭크마스크 수요 감소율로 옮기지 않는다.

2026년 연간 설명자료 PDF 30/33/34쪽:
https://www.jeol.com/assets/pdf/ir/financial_results/financial_results_briefing_2026_dab6Ky.pdf

- MBMW-401은 High-NA/10Å 세대 지원을 설명.
- Spot-beam 장비 수주/매출 지수(기준 FY2024=100)는 DFB 레이저 생산 등 직접 묘화 수요다. 마스크 생산 장비 수주로 오인하면 안 됨.
- 공식 IR Data Book에는 Excel도 제공: https://www.jeol.co.jp/ir/data_book/

JEOL-IMS 관계 공식 발표:
https://www.jeol.com/news/pr/20231024.10643.php

### NuFlare

- 제품: https://www.nuflare.co.jp/english/corporate/business/
- 2020-03-30 상장폐지, 2020-04 Toshiba Electronic Devices & Storage 완전자회사 편입 이력: https://www.nuflare.co.jp/english/corporate/history/
- 최신 기술 발표 MBM-4000(A14 노드): https://www.nuflare.co.jp/wp-content/uploads/index/news_20260610.pdf
- 최신 단독 연간 결산공고가 제3자 관보 데이터베이스에 검색되지만 공식 원문과 제품별 범위 확인 전에는 검증된 마스크 장비 매출로 차트에 사용하지 않는다.

## 다음 장비 차트 후보

1. Mycronic Pattern Generators 수주/매출/수주잔고 + TTM book-to-bill.
2. 모델별 수주대수·납품대수, 납품예정 잔고 대수. 반도체용/디스플레이용 구분.
3. JEOL 산업기기 매출과 마스크 관련 발언을 함께 표시. 순수 마스크 수요 지표라는 표기는 금지.

패터닝 업체 CAPEX와 장비 업체 수주를 비교할 때 환율·서비스·장비 교체·생산성 향상 및 인식 시차를 구분한다. 장비 투자액이나 대수를 블랭크 출하 장수로 직접 변환하지 않는다.
