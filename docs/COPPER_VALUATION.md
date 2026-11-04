# 구리 기업 주가·PER·PBR

원자재 → 구리 → 구리 기업에 Southern Copper(SCCO), Freeport-McMoRan(FCX), Ero Copper(ERO)의 최신 비교 표와 기업별 주가·PER·PBR 밴드 세 차트를 표시한다. 기존 영업이익·생산량과 Ero 실적은 유지한다. 기존 SCCO/FCX의 일반 주가 카드만 같은 종목의 확대 가능한 새 주가 카드로 통일했다. 이전 공개 JSON과 수집은 보존한다.

세 종목 모두 NYSE 보통주와 USD 기준이다. SCCO/FCX 종가는 2014년 이후, ERO는 실제 NYSE 거래 개시일인 **2021-06-15** 이후만 표시한다. Yahoo의 ERO 가격 응답은 이전 OTC 이력을 포함하므로 이 날짜로 자른다. CAD 종목 ERO.TO와 섞지 않는다. [NYSE 상장 공지](https://www.sec.gov/Archives/edgar/data/1853860/000095014221002028/eh210160855_ex9901.htm).

무료 Yahoo 일별 Close(분할 반영·배당 재투자 제외), reported fundamentals timeseries를 사용한다. EPS는 희석 TTM/완결 연간, BPS는 보통주 귀속 자본을 동일 기말 보통주 수로 나눈 값이다. 전망·조정 EPS를 실제 EPS로 대체하지 않는다. 공급자 rolling window가 짧아져도 수집한 기존 이력은 보존하고 실패 시 마지막 성공 자료와 확인 필요 상태를 유지한다. 밴드는 재작성된 결산기간 기준이며 공시 접수일 당시 정보로 하는 백테스트가 아니다. 결산기준일 이후 다음 값까지 유지하고 460일을 초과하면 만료한다.

SCCO는 빈번한 주식배당으로 과거 trailing EPS의 주식수 기준이 annual/quarterly EPS와 일치하지 않는다. 해당 trailing 값은 전부 버리고 공급자가 현재 주식수 기준으로 재작성한 연간 EPS 또는 **연속 네 실제 분기 EPS 합계**만 사용한다. 초기 구간은 연말 값만, 2026년 2분기부터 확보된 연속 분기 합계를 사용한다. 확보되지 않은 분기를 역산·추정하지 않는다. 공유 반도체 수집의 분할 검증은 완화하지 않는다. [SCCO 2026 Q3 공시](https://www.sec.gov/Archives/edgar/data/1001838/000110465926120639/scco-20260930x10q.htm).

확보된 EPS/BPS는 2022년 말 이후이며 일별 종가 전체와 밴드 기간은 다르다. 공급자 반영이 공시보다 늦을 수 있고 실제 EPS·BPS 기준일을 비교 표에 표시한다. 초기 배수는 2022년 이후 양의 PER/PBR 중앙값의 0.5/0.75/1/1.25/1.5배다. 적자 EPS와 0 이하 자본은 N/M, 적자 PER 구간은 밴드를 끊고 음영으로 표시한다. 원자료의 음수 EPS는 유지한다.

기존 공통 밴드 화면의 기간 선택·돋보기 확대·사용자 PER 배수 설정·표·원문 링크·지연 로딩·화면 밖 Chart 정리를 사용한다. 기업별 파일과 비교 목록은 `data/commodities/valuation/`에 독립 보관하며 반도체 목록·파일을 수정하지 않는다. 공통 모듈의 데이터 경로와 캐시 키를 산업별로 구분했다.

`update-copper-valuation.yml`은 매일 **08:20 KST** 독립 실행한다. 무료·키 불필요. 수집 명령 `python scripts/fetch_copper_valuation.py`; 검증 `python -m unittest discover -s scripts -p test_copper_valuation.py -v`. 소스 캐시는 `.cache/copper-valuation/`이며 git에 포함하지 않는다.
