# 통신 섹터

`#/telecom/us`, `#/telecom/kr`, `#/telecom/jp`에서 미국·한국·일본 통신사를 구분한다. 회사마다 매출·영업이익·CAPEX를 기존 공통 재무 카드로 표시하고 분기/연간을 전환한다. 예측치·EBITDA·조정 영업이익을 실제 영업이익으로 섞지 않는다.

첫 범위는 AT&T, Verizon, T-Mobile US, SK텔레콤, KT, LG유플러스, NTT, KDDI, SoftBank Corp. 9개 업체다. SoftBank Group 투자지주회사나 NTT의 연결 자회사를 별도 통신사로 중복 합산하지 않는다. 통신장비사는 이번 범위에 포함하지 않았으며 이후 별도 회사·사업 분류와 공급 관계로 추가할 수 있다.

## 무료 원천과 갱신

- 미국: SEC Company Facts. 실제 분기·완결 회계연도와 출처를 보존한다.
- 한국: OpenDART 연결 재무제표. 기존 CI의 무료 API 키를 재사용하며 원문·공개 데이터·로그에 키를 저장하지 않는다. 손익계산서의 3개월 금액과 현금흐름표의 누적 금액을 구분한다. CF 분기는 같은 회계연도의 누적 차분, Q4는 연간−9개월로 산출한다. 누락된 누적이 있으면 추정하지 않는다.
- 일본: NTT Supplementary Data, KDDI Financial Highlights, SoftBank Corp. Data sheets의 공개 Excel 자료. KDDI 최신 분기는 IFRS 원문을 대조한 별도 자료로 보완한다. 현행 웹 원문에서 찾지 못한 과거 파일은 결측으로 남기며 카드에 확보 범위를 표시한다.
- `update-telecom.yml`은 매일 08:50(KST) 실행한다. 발표 전 미래 분기, 사업 전망·예측 열은 수집하지 않는다. 원천 조회 실패 시 기존 성공 자료와 실제 수집일을 유지한다.

SK텔레콤 2021년 4분기 매출·영업이익은 인적분할 전 9개월과 분할 후 연간의 범위가 달라 단순 차분하지 않는다. 해당 두 분기 값은 결측으로 두며 연간 및 원보고서 수치는 보존한다.

## CAPEX의 해석

통신사 전체 설비투자가 통신장비사의 발주액이나 수주액과 같지는 않다. 건물·데이터센터·소프트웨어·단말·비통신 자회사 등도 포함될 수 있으며 투자 집행과 장비 매출 인식의 시차가 있다. 회사별 정의는 `manual/telecom/companies.json`과 각 CAPEX 카드에 유지한다.

- AT&T: 현금흐름표 Capital expenditures. 별도 vendor-financing payments를 더한 Capital investment와 구분한다.
- Verizon: 현금흐름표 Capital expenditures. 자본화 소프트웨어를 포함하며 주파수·기업 인수는 별도다.
- T-Mobile·SK텔레콤·LG유플러스: 현금흐름표 유형자산 취득. 주파수·무형자산·출자금·비현금 리스 자산을 임의로 더하지 않는다. 한국 IR의 검수 기준 CAPEX 및 별도 회사 CAPEX와 범위가 다르다.
- KT: 연결 CF의 유형자산 **및 투자부동산** 취득 현금지출. 원문 합산 항목을 사용하므로 투자부동산을 임의로 분리하지 않는다. KT 별도 IR CAPEX와 범위가 다르다.
- NTT: 회사가 공시한 Capital Investment (IFRS). 현금흐름표 유형자산 취득과 같은 기준이라고 가정하지 않는다.
- KDDI: 연간 공식 Capex (cash flow basis). 최신 분기는 공시 CF의 유형·무형자산 취득 합계로 보완하며 반올림·소비세 기준 차이를 표시한다. 장기 추이를 위해 CAPEX는 연간으로 시작한다.
- SoftBank Corp.: 연결 C/F summary의 Capital expenditures 현금지출. 별도 acceptance-basis 투자와 구분한다.

## USD와 원통화

표시 단위는 백만 USD다. 원화·엔화는 해당 실적 시작일~종료일의 ECB 일별 원통화/USD 평균으로 환산한다. USD 원자료는 재환산하지 않는다. `state.json`에 원통화 금액과 원문 근거, 각 카드의 `original_series`에 원통화 시계열을 보존하고 금액·차트·표의 메모로 확인한다. 연간 USD 금액은 실제 회계연도 전체 평균을 사용하므로 분기 USD 금액 합계와 다를 수 있다.

`scripts/test_telecom.py`는 분기 CF 차분·연간 결측·회계연도·예측 열 제외·원통화 보존을 확인한다. `scripts/validate_telecom.py`는 9개 회사와 27개 지표의 값·출처·환산 여부를 검증한다.
