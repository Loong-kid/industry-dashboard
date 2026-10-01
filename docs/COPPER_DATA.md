# 구리 수급

기존 Yahoo HG=F 가격·월물 커브·스프레드에 SHFE 주간 재고·일간 창고증권,
COMEX 총재고·등록재고·적격재고, LME 재고를 추가했다.

## SHFE

- 원문: https://www.shfe.cn/eng/reports/StatisticalData/WeeklyData/
- 현재 경로: `/data/tradedata/future/stockdata/weeklystock_YYYYMMDD/ZH/all.html`. 공식 `/images/api.js`의 `api_weeklystock_iframe`와 `/images/generateData_weeklystock.js`에서 HTML 우선·JSON 대체 순서를 확인했다.
- 과거 JSON 경로: `/data/tradedata/future/weeklydata/YYYYMMDDweeklystock.dat`. 2025-11-14까지의 보고서가 이 경로로 제공되며 이후 보고서는 새 HTML 경로에서 확인했다. JSON 404만으로 원자료 미발표를 판단하면 안 된다.
- `o_cursor`에서 구리(`铜`)의 `总计` 행만 사용한다. 지역 소계·보세/완세 소계를 다시 합산하지 않는다.
- `SPOTWGHTS`가 주간 재고(톤), `SPOTCHANGE`가 전주 대비다. `WHSTOCKS`는 가용 창고 용량이며 재고가 아니다. `WRTWGHTS` 창고증권을 재고에 더하지 않는다.
- HTML은 구리·톤·열 제목을 검증한 뒤 `总计`의 본주 재고 `小计`와 재고 증감 `小计`를 읽는다. 다른 금속·완세/보세 소계·창고증권·가용 창고 용량을 합산하지 않는다.
- 요청일과 HTML 보고서 날짜(구형 JSON은 `report_date`, `o_tradingday`) 일치, 단위, 유한한 비음수 재고, 전주 재고+증감=현재 재고를 검증한다.
- 일일 워크플로는 최근 21일 평일을 재확인한다. 404는 미발표로 건너뛰며 유효 보고서가 없으면 실패를 반환하고 기존 파일·수집일을 유지한다.
- 이력 수집: `python scripts/fetch_copper_inventory.py --backfill-weeks 156`. 기존 관측치는 보존하고 미수집 평일을 확인한다. 2025년 11월 이후 공백은 48주 평일 재수집으로 복원했다. 기존 2025년 10월 이전 이력은 금요일 중심이므로 휴일 단축 주차가 누락될 수 있다. 결측은 보간하지 않는다.
- 4주 변화는 정확히 28일 전 관측치가 있을 때만 계산한다. 주간 증감은 원문 값을 사용한다.
- 데이터 기준일이 14일 이상 지났으면 과거 자료 경고를 표시한다. 수집일이 최근이어도 경고를 숨기지 않는다.

최초 버전은 구형 JSON만 사용해 2025-11-14에서 멈췄다. 원자료 제공 중단이 아니라 수집 경로 선택 오류였다. 수정 후 2026-09-30 공식 보고서에서 재고 38,744톤, 전주 47,147톤, 증감 -8,403톤을 확인했다. 9월 24일과 9월 30일처럼 금요일이 아닌 발표일도 수집한다.

공식 원문: https://www.shfe.cn/data/tradedata/future/stockdata/weeklystock_20260930/ZH/all.html

검증: `python -m unittest discover -s scripts -p test_copper_inventory.py`

## SHFE 일간 창고증권

- `scripts/fetch_copper_warrants.py`가 공식 `dailystock_YYYYMMDD/ZH/all.html`을 읽는다.
- `地区/仓库/期货/增减` 열, 구리·톤, 기준일을 검증하고 구리의 `总计` 한 행만 사용한다.
- `期货`는 창고증권 발행 물량이다. 주간 재고와 더하지 않는다. 증권 취소·발행을 실제 소비·입출고로 해석하지 않는다.
- 일상 갱신은 14일 재확인, 최초 `--backfill-days 300`으로 201개 관측치를 확보했다. 2026-09-30: 10,011톤, 전 거래일 대비 -721톤.
- 실패 시 기존 데이터 보존. 카드의 전 거래일 증감은 원문 값이며, 4주 비교일이 없으면 자료 없음으로 표시한다.

## COMEX·LME 공개 스냅샷

- CME 공식 `Copper_Stocks.xls`는 이 실행 환경에서 403과 자동 수집 차단 메시지를 반환했다. 이를 우회하지 않고 별도 제공자의 공개 API를 사용한다.
- 제공자 카탈로그: https://thevaultreport.com/api/x402
- 카탈로그가 명시한 무료 API: https://thevaultreport.com/api/v1/snapshot
- 두 응답 모두 `license: CC BY 4.0`와 The Vault Report 링크 출처 표기를 명시한다. 일반 안내 페이지가 아닌 이 API 응답의 명시적 라이선스를 근거로 사용한다. 유료 x402 엔드포인트는 호출하지 않는다.
- `scripts/fetch_copper_snapshot.py`가 하루 한 번 최신값을 수집한다. UI와 JSON에 제공자·라이선스·원출처를 표시한다. CME/LME 직접 수집으로 표기하지 않는다.
- COMEX: `comex_copper_total`, `comex_registered_copper`의 기준일 일치 및 총재고 ≥ 등록재고를 검증한다. 적격재고는 같은 날 총재고−등록재고로 계산한다.
- COMEX 원단위 short tons를 0.90718474로 곱해 미터톤으로 환산한다. 3자리 반올림으로 구성 합계가 0.001톤 차이 날 수 있다. LME `lme_copper`는 원단위 mt 그대로 사용한다.
- API가 과거 관측치를 주지 않으므로 과거 이력을 만들지 않는다. 최초에는 한 점을 표시하고 이후 새 기준일을 누적한다. 날짜·단위·음수·NaN·라이선스 변경·날짜 역행은 오류로 처리해 기존 파일을 유지한다.
- 검증 당시 COMEX 최신 기준일은 2026-09-29, LME는 2026-09-30이었다. 갱신 일시와 데이터 기준일은 다르다.

## 다른 무료 지표 검토 (2026-10-01)

| 항목 | 실제 확인 | 결론 |
|---|---|---|
| LME 구리 재고 | The Vault Report 무료 API 200, mt·기준일·CC BY 4.0 확인 | 이번에 추가. 최신값부터 누적 |
| CFTC 구리 Managed Money 순포지션 | 공식 `72hh-3qpy.json`, 시장코드 `085692` 쿼리 200. 2026-09-22 long 96,421, short 13,899 | 추가 가능. 순매수 82,522계약. 이번 범위에는 미추가 |
| 칠레 구리 광산 생산 | 같은 무료 snapshot에 `cochilco_chile_copper_mine_output`, mt, 2026-07-01 값 확인 | 월간 공급 보조 후보. 원출처·전체 이력 검증 후 추가 가능 |
| 양산 프리미엄 | SMM 공개 기사에 일부 일간·주간 값 있음. 공식 API 문서에는 permission 0/1 및 토큰 필요 | 무료 상시 API 미확인. 일간값과 주간평균을 섞어 자동 시계열로 만들지 않음 |
| 보세/사회 재고·TC·동봉 가동률 | SMM Database Pro/API 안내 확인 | 무료 정형 수집 미확인. 이번에 자동 카드 추가하지 않음 |
| LME Cash–3M | 공식 FAQ의 XML feed는 연간 구독. 무료 snapshot에 cash/3M 쌍 없음 | 무료 상시 API 미확인. COMEX 스프레드로 대체 표기하지 않음 |
| SHFE/LME 수입 가격차 | LME 가격과 동일 시점·만기·환율·세금 보정 필요 | 원자료 확보 후 계산 가능. 아직 정확한 수입 손익으로 표시하지 않음 |

확인 출처:
- CFTC 공식 API 안내: https://publicreporting.cftc.gov/stories/s/COT-Help/p2fg-u73y/
- CFTC 데이터: https://publicreporting.cftc.gov/resource/72hh-3qpy.json
- SMM API: https://www.metal.com/smm-api
- 양산 프리미엄 권한 문서: https://data.metal.com/dataapi/copper/cu_yangshan_copper_premium_warehouse_warrant
- LME 무료 열람 및 유료 feed 구분: https://www.lme.com/en/about/faqs/market-data-faqs

추가 검증: `python -m unittest discover -s scripts -p test_copper_sources.py`, `node scripts/test_copper_card.cjs`.
