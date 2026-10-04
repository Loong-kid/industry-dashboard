# 매크로 시장규모

매크로 → 시장규모(`#/macro/market_size`)에 요청한 6개 시장과 S&P 분기 상세를 표시한다. 모두 명목 조 달러이며 전망·빈 연도 보간은 없다.

| 카드 | 공개 자료 | 주기/범위 |
| --- | --- | --- |
| 미국·글로벌 전체 주식 | World Bank WDI CM.MKT.LCAP.CD, USA/WLD | 연말 상장 국내기업 시총, 1975~2025 최초 확보 |
| 미국·글로벌 전체 채권 | SIFMA Fact Book의 BIS Global Fixed Income Markets Outstanding | 연말 발행잔액, 2011~2025 최초 확보 |
| 나스닥 | SIFMA/WFE U.S. Stock Market Capitalization, Nasdaq 열 | 거래소 미국 국내기업 시총, 2011~2025. Composite/100 아님 |
| S&P 연말·분기 말 | press.spglobal.com 공식 Buybacks 보고서 MARKET VALUE 열 | 연말 2006~2024, 분기 말 2006Q4~2025Q3 최초 확보 |

## 기준

- World Bank USD 값을 1조로 나누고 SIFMA/S&P 십억 달러를 1,000으로 나눈다. 자료원 간 연결·가격지수의 고정 배수 환산·구성종목을 현재 명단으로 역산하지 않는다.
- World Bank 세계 합계와 SIFMA 세계 합계는 범위·빈티지가 달라 다르다. 세계 주식은 World Bank 한 출처를 유지한다.
- 채권은 은행대출을 포함한 총부채나 시가평가 자산 합계가 아니다. SIFMA의 별도 최신 미국 요약 중 MBS/ABS 제외 값은 사용하지 않는다. 2018년 BIS 통계 편입국 증가에 따른 세계 합계 단절은 카드에 명시한다.
- S&P는 공식 표의 Market Value를 그대로 표시한다. 구성기업 전체 시총과 유동주식 조정 지수 시총을 동일시하지 않는다. `12 Mo` 행은 제외하고 실제 연도/날짜 행만 사용한다. 연말 실제 Q4 값도 연간 자료로 사용한다. 2025년 연말은 이 수집 경로에서 아직 확보되지 않아 만들지 않았다.
- 주식시장은 부분집합이 겹치므로 6개 규모를 합산한 TAM으로 표시하지 않는다. 각 카드의 `집계 기준 자세히`에 포함범위와 갱신 방식이 있다.

## 자동 갱신

기존 `.github/workflows/update-data.yml`은 매일 KST 07:30 실행이다. 연간 자료 전용으로 1월 1일만 실행하는 방식이 아니다. IMF 등 기존 자동 수집 연간 자료도 매일 새 발표를 확인한다. 수기 CSV/수기 원본 자료는 이 실행으로 새 원본이 생기지 않는다.

`fetch_market_size.py`도 이 워크플로에 연결했다. World Bank API의 새 연간값·전체 과거 정정, SIFMA 최신판 링크 및 최신판의 과거 정정, S&P 최신 보도자료의 과거 정정을 반영한다. 공표 시점은 자료원마다 다르며 새 발표가 없으면 마지막 관측연도는 유지된다. `fetched`는 성공한 자료확인일, `updated`는 마지막 관측기간이다. 실패한 소스는 기존 공개 파일을 유지하며 실행 로그에 오류를 기록한다.

SIFMA와 S&P 이력은 `data/_market_size/`에 숫자·원문 링크·원문 연도/공표일을 보존한다. 최신 보고서의 이동하는 이력 범위 밖 관측값을 삭제하지 않으며, 새로운 빈티지가 겹치는 기간을 수정한다. PDF 표/HTML 표 형식이 바뀌어 검증에 실패하면 기존 값을 지키고 파서 점검이 필요하다. 공개 보도자료가 멈추면 자동 실행만으로 관측기간이 연장되지는 않는다.

검증: `python -m unittest discover -s scripts -p test_market_size.py`, `node scripts/test_market_size.cjs`, 실제 Chrome에서 탭·집계 기준·표·분기 툴팁·다크 모드 확인.
