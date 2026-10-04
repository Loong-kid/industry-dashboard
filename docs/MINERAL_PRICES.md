# 우라늄·농축서비스·희토류 가격

`scripts/fetch_mineral_prices.py`가 Cameco·EIA 가격과 `fetch_komis_prices.py`의 전체 광물 수집을 실행한다. KOMIS는 49개 광종·79개 가격 기준을 수집한다. 화면은 `normal` / `구리` / `희토류` 세부 탭으로 분류하고, 각 광물의 모든 가격과 생산량·매장량을 함께 배치한다. 비철·철·에너지·귀금속·흑연과 희토류 외 희소금속은 normal, 구리 가격은 구리, 희토류 14종 가격은 희토류에 표시한다.
API 키나 로그인이 필요하지 않으며 일일 `update-data.yml`에서 실행한다.

## 우라늄

- 원문: https://www.cameco.com/invest/markets/uranium-price
- 현물과 장기계약 지표는 U₃O₈ 기준 USD/lb의 **월말 가격**이다. 월평균이나 일별 선물 종가로 표시하지 않는다.
- Cameco는 UxC와 TradeTech의 월말 가격을 평균한다. 2004년 5월 이전 장기 가격은 TradeTech 단일 자료원이다.
- 최초 확인: 현물 1988-01~2026-09, 465개월; 장기 1996-03~2026-09, 367개월.
- 날짜·현물·장기 가격이 함께 있는 숨김 HTML 표를 헤더로 식별한다. 최근 5개년 요약 표를 읽지 않는다.
- 구간에 따라 월초로 표기된 원문 날짜도 해당 월말로 통일한다. 같은 달의 동일한 중복 행은 제거하고 서로 다른 가격이면 실패한다.
- 장기 가격의 초기 빈칸은 관측치 없음으로 유지한다. 0이나 현물 가격으로 채우지 않는다.
- 장기 지표는 특정 만기의 선물 가격이 아니다. UxC의 일반 정의는 최소 3년 뒤 인도 시작, 최소 5년간 공급하는 계약의 기준가격이며 인도 시 가격 조정이 붙을 수 있다. Cameco가 평균하는 TradeTech 지표에는 공개 정의상 동일한 고정 연수 조건이 명시되어 있지 않으므로 이 숫자를 모든 계약의 공통 조건으로 설명하지 않는다.
- 정의: https://www.uxc.com/p/uxw?key=19475 및 https://www.uranium.info/uranium_price_definitions.php

## 농축서비스 구매가격 (SWU)

- 원문: https://www.eia.gov/uranium/marketing/summarytable2.php
- 대조 표: https://www.eia.gov/uranium/marketing/table16.php
- 미국 민간 원전 사업자가 해당 연도에 구매한 농축서비스의 실제 평균 지불가격이다. 기존 계약 인도분도 포함하므로 신규 현물·장기계약 시장가격으로 설명하지 않는다.
- 단위는 **USD/SWU**(분리작업량 단위), 연간 명목 가격이며 물가 조정을 하지 않는다.
- 최초 확인: 2006~2025년, 20개; 2025년 108.70 USD/SWU. 원문의 2003~2005년 미공개 가격은 0이나 다른 연도 값으로 채우지 않는다.
- S2의 `Year`와 `Average price (US$ per SWU)` 헤더로 열을 찾고, Table 16의 같은 단위 가격 행과 최근 5개년을 대조한다. 물량 행은 가격으로 읽지 않는다.
- 저장 날짜의 `12-31`은 연간 관측치의 정렬용 키이다. `year_labels: true`로 카드·차트 축·툴팁·표에는 연도만 표시한다. 월별 데이터로 확장하지 않는다.
- 다음 해의 연간 보고서로 갱신된다. 두 표의 최신 연도·값이 다르거나 규격이 바뀌면 기존 파일을 보존한다.

## KOMIS 전체 광물

- 확인일: 2026-10-04. 공개 광종 목록 49종, 가격 옵션 83개 중 실제 공개 가격 행이 있는 **79개**를 모두 수집한다.
- `scripts/komis_prices.json`에 상품·규격·인도조건·통화·중량단위·자료원 표시를 고정한다. 바뀌면 해당 카드 파일을 덮어쓰지 않고 실패를 보고한다. 같은 광종의 다른 지역·순도·제품·만기도 서로 다른 카드다.
- 분류: 비철 6종/13개, 희소·희토류 34종/56개(희토류 14종 포함), 철·에너지 3종/4개, 귀금속·흑연 6종/6개.
- 공개 POST `/ajax/common/getMnrlKndInfoCodeList`에 `cdType=HP000`, `cdGrp=HP001~HP004`를 보내 광종을 조회한다. 각 광종의 모든 옵션을 `getMnrlPriceCrtr`로 조회하고 `getMnrlPrcByMnrkndUnqCd`의 게시 기준가격을 가져온다. 공식 외부 OpenAPI로 부르지 않는다.
- 공개 가격 행이 없는 4개 옵션(네오디뮴 지수 전용 746, 옛 디스프로슘 754, 란탄 753, 테르븀 755)은 레지스트리 `excluded`에 이유를 기록한다. 매일 재조회하며 값이 생기면 갱신 실패로 알린다. 옵션 추가·삭제도 발견하여 누락이 조용히 지속되지 않게 한다.
- 가격을 통화·단위 환산하거나 다른 제품과 이어 붙이지 않는다. 카드별 `가격 기준 자세히`에 규격 원문, 해설, 발표 방식, 단위 및 원문 오류를 보여준다.

### 가격 기준과 자료원

| 분류 | KOMIS의 기준 | 설명 |
|---|---|---|
| LME 비철·코발트 | CASH / 3개월 / 15개월 | CASH는 통상 2영업일 후 인도·결제, 나머지는 해당 만기의 가격. KOMIS 공개 기준에는 매수·매도/종가 구분이 명시되지 않아 특정 호가나 종가로 단정하지 않는다. |
| 금·은 | 런던 LBMA PM 금 / 은 기준가격 | 현물 인도 기준가격. 과거 fixing 명칭과 현대 경매 체계가 포함된 이력이다. 금 PM은 런던 15시, 은은 정오 경매로 설명한다. |
| 백금·팔라듐·루테늄 | Johnson Matthey London | 도매 고객 대상 스펀지 금속 매도 고시가격. 백금·팔라듐 99.95% 이상, 루테늄 99.9% 이상. |
| 지역별 광물 | ISE 또는 자료원 미표기 | `isISE=Y`인 카드만 ISE로 명시한다. 오산화바나듐·페로바나듐은 원자료원이 명시되지 않아 ISE/LME로 추정하지 않는다. |
| 우라늄 | Nuexco 주간 U₃O₈ USD/lb | KOMIS 원문 표기 그대로. Cameco 월말 가격과 합치지 않는다. |

FOB는 선적항 본선 적재 조건으로 이후 해상 운임·보험료는 매수자 부담, CIF는 목적항 운임·보험료 포함(위험 이전은 통상 선적항), EXW는 공장·사업장 인도 조건이다. CNF는 C&F/CFR 관행 표기로 운임 포함이며 보험료 포함을 단정하지 않는다. Delivered 및 창고·항구 가격은 원문에 세부 비용이 없으면 통관·보험·세금 포함 여부를 추정하지 않는다.

- 정의 출처: [LME](https://www.lme.com/market-data/lme-reference-prices/lme-official-price), [LBMA](https://www.lbma.org.uk/prices-and-data/about-lbma-daily-auction-prices), [Johnson Matthey](https://matthey.com/products-and-markets/pgms-and-circularity/pgm-management/base-price-trading-disclaimer), [ICC Incoterms](https://library.iccwbo.org/clp/clp-incoterms.htm).
- `ton`·`mt`는 미터톤, `troz`·`ozt`는 트로이온스, `mtu`는 1톤의 1%인 함유량 10kg 기준이다. 몰리브덴 정광의 USD/mtu는 제품 톤당 가격으로 변환하지 않는다.

### 리튬 전환

- `comm_lithium`: 탄산리튬 99.5%min CIF China, USD/kg, 2018-01-08부터. 기존 수기 카드에는 실제 가격이 없었으므로 빈 자리만 전환하며 `manual/manifest.json`에서 제외해 수기 importer의 덮어쓰기를 막는다. `manual/lithium.csv` 원본은 보존한다.
- 수산화리튬 일수화물: LiOH 56.5%min FOB China, USD/kg, 2020-12-18부터. 원문의 `Magnets 0.0001%max`는 뜻이 명확하지 않아 그대로 표기한다.
- 스포듀민: Li₂O 6%min CIF China, USD/mt, 2020-12-18부터. 리튬 화합물 가격이나 순수 금속 가격과 구분한다.
- 미공개·0 가격은 제외하고 날짜를 기록하며 최신값이 미공개면 파일을 덮어쓰지 않는다.
- `cmercPrc`가 공개 기준가격이다. 최저·최고 보조 필드에는 일부 원문 오류가 있다(납 2024-07-18, 갈륨 EXW 2026-01-08, 철광석 일부 2026년 행). 보조 범위만으로 기준가격을 수정하지 않고 날짜를 `data_quality` 및 카드 설명에 표시한다. 우라늄 과거 0 값 9개도 표시한다.

### 기존 희토류 카드

- 화면: https://www.komis.or.kr/Komis/RsrcPrice/MinorMetals
- KOMIS의 공개 화면이 사용하는 POST 응답을 읽는다. 공식적으로 보장된 외부 OpenAPI라고 부르지 않는다.
- 가격 기준은 **FOB China, USD/kg**. 네오디뮴·디스프로슘·프라세오디뮴은 순도 99.5% 이상, 테르븀은 99.99% 이상이다. 금속·내수·다른 순도의 가격과 합치지 않는다.
- 네오디뮴: `MNRL1001`, 가격기준 `757`, `Neodymium Oxide`; 최초 확인 2010-07-02~2026-09-24, 3,753개.
- 디스프로슘: `MNRL1004`, 가격기준 `803`, `Dysprosium Oxide`; 최초 확인 2013-03-21~2026-09-24, 3,128개.
- 테르븀: `MNRL1005`, 가격기준 `806`, `Terbium Oxide`; 최초 확인 2019-01-16~2026-09-24, 1,692개.
- 프라세오디뮴: `MNRL1056`, 가격기준 `758`, `Praseodymium Oxide`; 최초 확인 2010-07-02~2026-09-24, 3,753개.
- `getMnrlPriceCrtr`에서 상품명·순도·가격기준 ID를 먼저 검증하고 `getMnrlPrcByMnrkndUnqCd`의 `data.defaultMnrl`을 읽는다.
- `dataAvg.INFO`의 광종명·통화·중량단위·인도조건, 최신가격 요약과 행의 일치 여부를 확인한다.
- 과거 일부 행의 최저/최고 가격 0/0은 범위 미제공을 뜻한다. 실제 가격은 `cmercPrc`이며 0은 미공개로 기록하고 제외한다. 음수·비유한 값은 거부한다.
- **2026년 자료원 변경:** KOMIS는 2026년 1월부터 희토류 등 자료원을 단계적으로 변경한다고 공지한다. 같은 규격도 과거와 차이가 날 수 있다. 공지에는 품목별 정확한 전환일이 없어 임의의 단절 날짜를 만들지 않는다. 카드에 비교 주의사항을 표시한다.
- 일자별 게시값이지만 매일 새로운 거래나 가격 변화를 뜻하지 않는다. 현재 화면은 ISE를 자료원으로 표시한다.

## 갱신·실패 처리

```powershell
python scripts/fetch_mineral_prices.py
python scripts/fetch_mineral_prices.py --backfill
python -m unittest discover -s scripts -p test_mineral_prices.py
node scripts/test_mineral_cards.cjs
python -m unittest discover -s scripts -p test_komis_prices.py
node scripts/test_komis_cards.cjs
node scripts/test_commodity_tabs.cjs
```

최초에는 전체 이력을 읽는다. 이후 KOMIS는 현재·직전 연도를 재확인하고 기존 오래된 관측치를 보존한다. `--backfill`은 전체 이력을 다시 확인한다. KOMIS의 오전 10시경 갱신과 사이트의 KST 07:30 수집 시점이 달라 당일 발표분은 다음 수집에 반영될 수 있다.
원문의 같은 날짜 정정은 반영한다. 미래 날짜·규격 변경·잘못된 가격·최신일 역행·빈 응답은 기존 파일을 덮어쓰지 않는다. 각 카드가 독립적으로 수집되어 한 소스 실패가 다른 카드 수집을 막지 않는다.

`fetched`는 한국 시간 수집일, `updated`는 실제 자료 기준일이다. 수집에 성공해도 자료 기준일이 오래되면 카드에 경고한다(Cameco 우라늄 70일, SWU 730일, KOMIS 21일).
