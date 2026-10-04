# 구리 수요 배경 · 중국·미국 건설 지표

`python scripts/fetch_copper_construction.py`는 키 없이 NBS와 Census 공식 자료를 확인하고 `data/commodities/comm_copper_{cn,us}_*.json`에 병합한다. 매일 KST 07:30 `update-data`에서도 실행한다. `construction_only=true`로 이 수집만 실행할 수 있다.

최초 PMI 과거 발표문 보충은 `python scripts/fetch_copper_construction.py --backfill --country cn`. 중국만 또는 미국만 실행하려면 `--country cn` / `--country us`를 사용한다. 빈 응답·개별 수집 실패는 기존 이력을 삭제하지 않으며 실패 상태를 기록한다. 관측 월은 월말 날짜로 저장하고 실제 수집일과 구별한다.

| 카드 | 기본 표시 | 다른 표시 | 확인한 역사 |
|---|---|---|---|
| 중국 신규 착공 | 공식 누적 전년동기비 % | 누적 백만㎡ | 2000-02~. 2000-04~12 미확보 |
| 중국 준공 | 공식 누적 전년동기비 % | 누적 백만㎡ | 2000-02~ |
| 중국 신축 상품부동산 판매 | 공식 누적 전년동기비 % | 누적 백만㎡ | 2000-02~ |
| 중국 개발투자 | 공식 누적 전년동기비 % | 누적 십억 위안 | 2000-02~ |
| 중국 건설 경기 | 사업활동 / 신규주문 | 50 기준선 | 2014-12~, 2015-01 미확보 |
| 미국 주택 건설 | 착공 / 허가 / 준공, 천 호·SAAR | 전년동월비 % | 1959 / 1960 / 1968~ |
| 미국 건설 지출 | 주거용 / 비주거용, 십억 USD·SAAR | 전년동월비 % | 1993-01~ |

중국 부동산의 1월은 별도 발표가 없으며 2월은 1~2월 합산이다. 결측을 0이나 보간으로 만들지 않는다. 증가율은 NBS 공식 비교 가능 기준을 그대로 사용한다. 전년도 저장 절대량으로 이를 재계산하지 않는다. 원자료의 万平方米→백만㎡는 ÷100, 亿元→십억 위안은 ÷10이다. 중국 시공면적을 당월 신규 공사 물량으로 바꾸는 차분은 하지 않는다.

미국 지표는 계절조정 연율(SAAR)이며 월 실적·연간 누적이 아니다. 물량은 건물 수가 아닌 주택 호수이며, 지출은 명목 금액이다. 주택 workbook의 `Seasonally Adjusted` 시트에서 미국 `Total`을 사용한다. 건설 지출은 `Total Residential`, `Total Nonresidential`이며 민간과 공공을 포함한다. 백만 USD→십억 USD는 ÷1000이다. 전년비는 12번째 이전 행이 아니라 전년 동일 월의 값과 비교한다.

PMI는 비제조업 전체 신규주문을 사용하지 않는다. NBS 공식 발표문에서 `建筑业商务活动指数`, `建筑业新订单指数` 문맥을 확인한다. 기사 URL의 202302는 사이트 이전 경로일 수 있으며 관측 월은 제목·본문 발행일로 결정한다. 2015년 6월 조사범위 확대로 과거 비교에 유의한다. API에서 사업활동만 제공하는 구간을 발표문으로 보완하고, 최신 두 항목의 월 일치를 검증한다. 누락 기간은 월축의 공백으로 보존한다.

공식 출처:

- NBS 화면: https://data.stats.gov.cn/dg/website/page.html#/pc/national/monthData
- NBS 조회: `POST https://data.stats.gov.cn/dg/website/publicrelease/web/external/stream/esData`. 공식 화면의 조회 경로이며 계약형 API/SLA를 확인한 것은 아니다.
- NBS 공식 검색: https://www.stats.gov.cn/search/s 의 공개 검색 요청 `https://api.so-gov.cn/query/s`로 공식 기사 URL만 찾는다. 외부 검색 결과·SNS는 제외한다.
- Census 주택 역사: https://www.census.gov/construction/nrc/data/series.html
- Census 건설 지출 역사: https://www.census.gov/construction/c30/historical_data.html

검증:

```text
python -m unittest discover -s scripts -p test_copper_construction.py -v
node scripts/test_construction_cards.cjs
node scripts/test_commodity_tabs.cjs
```

규모/증가율 전환은 선택 상태를 카드별로 유지하고 단위·차트·표를 함께 바꾼다. 교체된 차트를 파괴해 이벤트/차트 인스턴스를 남기지 않는다. PMI 변화는 전월 대비 지수 포인트로 표시한다. 이 자료는 구리 수요의 배경 지표이며, 가격 예측이나 인과관계를 검증한 모델이 아니다.
