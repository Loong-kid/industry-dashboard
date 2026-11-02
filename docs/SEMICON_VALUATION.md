# 반도체 주가·PER·PBR

반도체 15개 보기(메모리·파운드리·CPU·GPU·AI ASIC·SSD·장비 세부 분야·블랭크마스크·MOCVD·웨이퍼·링)에 기업별 주가와 실적 TTM PER·PBR 밴드를 표시한다. 기존 기업 실적과 제품 표는 유지한다. 회사 실적 아래 세 차트를 붙이고 실적 섹션이 없는 GPU·ASIC 설계사와 협력사 등은 별도 기업별 구역에 배치한다. 각 보기 상단에는 최신 종가·PER·PBR·재무 기준일 비교 표를 두며 검색, 배수 정렬, 회사 차트로 이동을 지원한다.

등록 69개 중 상장사 65개는 주가·EPS·BPS를 확보했다. Huawei/HiSilicon·CETC는 비상장 조직 범위, NuFlare는 상장폐지, TOPEC은 기존 법인 검토 상태를 유지한다. 다른 회사나 모회사 주가를 대신 넣지 않는다. CXMT는 2026-07-27 상장한 688825.SS로 등록한다. Sandisk는 2025-02-24 분사 상장 이후만 사용하고 구 Sandisk의 2016년 이전 주가와 합치지 않는다. Kioxia·Tekscend 등도 신규 상장일 전 주가를 만들지 않는다.

주가는 Yahoo Finance의 일별 **Close**로 2014년 이후 가능한 전체 이력을 저장한다. 분할은 반영하되 배당 재투자가 포함되는 Adjusted Close로 PER·PBR을 계산하지 않는다. 각 거래소 시간대와 정규장 종료 시각을 확인해 진행 중인 장중 값은 종가에서 제외한다. 통화·종목·일별 주기를 검증한다. 현재 대표 종목은 ASML 암스테르담 보통주(EUR), TSMC 대만 보통주(TWD), SMIC 중국 A주(CNY), Baidu 홍콩 보통주(HKD) 등으로 선택해 ADR·보통주 주당 기준을 혼동하지 않는다.

국내 기업의 EPS·BPS는 NAVER/FnGuide 공시 기반 표에서 읽으며 **isConsensus=N**인 값만 사용한다. TTM EPS는 실제 연속 4개 분기 EPS 합계이고 완결 연간 EPS도 같은 12개월 실적으로 사용한다. 전망치인 2026년 연간·분기 값은 제외한다. 삼성전자처럼 우선주가 있는 회사는 임의로 자본을 보통주 수로만 나누지 않고 제공된 보통주 BPS를 사용한다. 분기 EPS 합계는 가중 주식수를 다시 계산하는 다른 사이트의 EPS와 조금 다를 수 있다.

해외 기업은 Yahoo Finance Financials의 실제 annualDilutedEPS·trailingDilutedEPS, CommonStockEquity와 같은 날짜의 OrdinarySharesNumber를 사용한다. EPS는 희석 기준, BPS는 보통주 귀속 자본/기말 보통주 유통주식수다. 재무 통화와 거래 통화가 다르면 같은 주가 날짜 이전의 7일 이내 실제 환율로 EPS·BPS를 거래 통화로 바꾼다. 예를 들어 SMIC의 USD 재무값을 CNY 주가와 그대로 나누지 않는다. 환율이나 분모가 없으면 계산하지 않는다.

가격은 전 기간 분할 보정되어 있으나 일부 공급사 과거 TTM EPS는 분할 전 단위이고 연간 EPS는 이미 재작성되어 있다. `ttm_split_reviews.json`은 원본 일별 분할 이벤트, 동일 기말 연간 EPS와 TTM 배수 및 전환 시점을 대조한 10종목의 정규화 기록이다. NVDA·LRCX·AVGO·KLA·Tokyo Electron 등에서 예전 TTM EPS만 보정하고 이미 보정된 연간 EPS를 중복 조정하지 않는다. 공급사가 TTM도 재작성하면 연간 앵커의 비율을 확인해 재차 나누지 않는다. 검토되지 않은 새 분할 이전 TTM은 보수적으로 제외하고 확인된 완결 연간 EPS를 남긴다. 일일 수집 시 롤링 API 범위 밖의 과거 실적은 보존하고 새로 발생한 분할은 보존 이력에도 반영한다.

PER=종가/실적 TTM EPS, PBR=종가/기말 BPS다. EPS·BPS가 0 이하이면 **N/M**이며 음수 배수나 0으로 대체하지 않는다. 과거 밴드는 2022년 이후 확보된 양의 유효 PER/PBR의 중앙값을 기준으로 0.5·0.75·1·1.25·1.5배의 고정 배수를 정해 당시 EPS·BPS에 곱한 참고 주가선이다. EPS가 0에 근접한 기간의 극단적인 최고 배수가 모든 선을 눌러버리지 않도록 중앙값을 사용한다. 초록색은 실제 종가, 회색 다섯 선은 고정 배수다. 주가 차트는 전체 이력, 밴드는 해당 실적이 확보된 기간부터 표시한다.

**밴드는 사후 확인·재작성된 회계기간 기준이다. 공시 접수일 당시 투자자가 알 수 있던 정보를 재현하는 백테스트가 아니다.** EPS·BPS는 결산기준일 이후 다음 확보된 값까지 유지하되 460일 이상 지난 값은 만료시킨다. 누락된 분기 EPS를 추정하거나 연간 전망을 실제 TTM으로 쓰지 않는다. 해외 재무 시계열은 보통 2022~2023년 이후, 국내 표는 현재 제공되는 실제 연간·분기 범위부터이며 과거 PER/PBR 밴드 이력이 2014년부터 모두 존재하는 것은 아니다. 원자료 갱신 시 재작성으로 과거 밴드와 중앙 배수가 변할 수 있다.

성능: 각 탭은 가벼운 비교 목록만 먼저 받고, 회사 구역이 화면 근처에 들어올 때 그 회사 JSON 하나를 읽어 주가·PER·PBR 세 차트를 그린다. 공통 주가 배열 한 개로 세 차트를 계산하며 밴드 다섯 개의 일별 가격 배열을 따로 저장하지 않는다. 한 차트는 최대 약 640개 대표 점과 실적 변경 경계를 사용하되 구간의 최고·최저와 첫·마지막 점을 보존한다. 화면에서 벗어난 회사의 Chart 인스턴스는 제거하고 되돌아오면 캐시에서 복원한다. 표는 한 번에 50행만 그린다. 카드 높이·너비는 기존 financial-grid와 220px 차트 높이를 따른다.

`update-semicon-valuation.yml`은 매일 **08:10 KST**에 독립 수집한다. 사전·사후 검사, 전용 concurrency, 자기 데이터 폴더만 stage, 일반 push 재시도, publish-data 후속 배포를 사용한다. 조회 실패 시 검증된 과거 이력을 보존하고 상태를 표시한다. 신규 분할과 재무 조회 실패가 겹치면 오래된 분모와 새로운 분할 주가를 섞지 않도록 가격도 이전 이력으로 보존한다. 공개 JSON에는 API 키·계정 정보가 없다.

공식 종목 확인: [CXMT 거래소 상장 공고](https://www.sse.com.cn/disclosure/announcement/listing/ipo/c/c_20260724_10826610.shtml), [Tekscend IR](https://www.us.photomask.com/en/ir/faq/), [Sandisk 상장·분사 공지](https://investor.sandisk.com/news-releases/news-release-details/sandisk-celebrates-nasdaq-listing-after-completing-separation), [NuFlare 상장폐지 공고](https://www.jpx.co.jp/english/news/1021/20200309-12.html). 시세·재무 출처는 각 카드와 비교 목록의 원문 링크로 확인한다.

검증: `python -m unittest discover -s scripts -p test_semicon_valuation.py -v`, `node scripts/test_semicon_valuation.cjs`, 전체 `python scripts/run_ci_tests.py`. 테스트는 장중 값 제외, 배당 조정 가격과 종가 구분, 분할 중복 보정 방지, 전망치 제외, 실제 4분기 TTM, 통화 변환·적자·순자산·자료 만료, 전 종목·탭 연결 및 실패 복구를 확인한다.
