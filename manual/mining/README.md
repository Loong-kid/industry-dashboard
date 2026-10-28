# 광산기업 자료 기준

시가총액 순위는 `companies.json`의 2026-10-28 조회 스냅샷이다. 석탄 전업·주력사를 제외하고 BHP·Glencore처럼 석탄을 겸하는 복합 광산기업은 포함한다. Grupo México와 자회사 Southern Copper는 별도 상장 법인이라 둘 다 표시하지만 합산하면 중복이다. 자동 시가총액 순위 갱신은 하지 않는다.

재무 이력은 `data/commodities/mining_financial_history.json`에 원문 URL·공시일·기간·차분 구성요소와 함께 보관한다. SEC CompanyFacts와 원문 재무제표, Glencore 공식 IR, Zijin의 HKEX 공시, Grupo México의 BMV 감사보고서를 사용한다. `source_files.json`은 검증한 PDF 목록이며, 새 연차보고서는 원문·산식을 검토하고 목록에 추가한다.

`python scripts/fetch_mining.py --refresh`는 SEC 및 등록 PDF를 확인하고 마지막 성공 자료를 보존한다. `--from-state`는 원문 재요청 없이 저장된 재무 이력에서 차트를 재생성한다. 매주 화요일 오전 8시 40분(KST)에 갱신한다. 실패한 기업은 성공했던 값·기준일을 유지하고 확인 실패를 표시한다. 광물 비중은 수기 원문 검토한 기간 그대로 유지한다.

초기 확보: BHP·Southern Copper·Newmont·Freeport·Zijin·Glencore 2014년부터, Rio Tinto 2015년부터, Agnico Eagle·Barrick 2016년부터, Grupo México 2019년부터, Ero Copper 2020년부터. 분기·반기는 확보된 자료만 제공하며 다른 회사의 공시 주기로 보간하지 않는다. Ero는 2016년 설립 회사이므로 2014년 자료를 만들지 않는다.

매출 구성 표는 광물별 연결 매출을 우선한다. FCX는 차감·파생 정산 전 제품 매출, Agnico는 제품별 계약 매출, Glencore는 비례연결 조정 전 사업부 매출이 분모다. Zijin은 광물별 표의 내부거래 제거를 광물에 임의 배분하지 않고 외부매출 사업 구성을 표시한다. Grupo는 재화·서비스 구성으로 구리 단독 비중이 아니다. 행마다 기간·분모·조정 사항·출처를 표시한다.

이익은 EBITDA로 대체하지 않는다. Newmont(매출−비용·경비), Agnico(세전이익+금융비용), Barrick(세전이익−순금융손익), Glencore(세전이익+이자비용−이자수익), Grupo(매출총이익−관리비)는 계산 영업손익으로 명시한다. Zijin은 중국 회계기준 Operating profit으로 금융·투자손익이 포함될 수 있다. CAPEX는 기업별 현금흐름표 정의를 유지하며 리스·인수대금·탐사자산 등의 포함 범위는 카드 설명을 따른다. 통화 환산 없이 USD 백만, Zijin만 CNY 백만이다.
