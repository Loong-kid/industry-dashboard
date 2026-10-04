# 기관 / 미국 운용사 / 헤지펀드 업계·전략

`scripts/fetch_hedge_funds.py`는 API 키 없이 매일 07:30 KST의 기존
`update-data.yml`에서 새 공표·정정을 확인한다. 실패한 소스는 기존 자료를
보존하며 나머지 소스는 계속 수집한다. 업데이트 실패는 CI 로그에 남는다.

## 미국 운용사

Bridgewater Associates (CRD 105129), Citadel Advisors (148826), Point72 Asset
Management (283077), Two Sigma Investments (137137), D. E. Shaw & Co. (108679),
Pershing Square Capital Management (132982)를 독립적인 신고 법인으로 추적한다.

- 공식 원문: `https://reports.adviserinfo.sec.gov/reports/ADV/{crd}/PDF/{crd}.pdf`
- Form ADV Item 5.F.(2)(c)의 RAUM, 재량·비재량 금액, 신고일, PDF SHA-256을
  `data/institution/us_raum_*.json`에 저장한다. CRD·법인명과 구성금액 합계를 검증한다.
- 가로축은 **신고일**이다. AUM 평가일이나 연말 잔고를 추정하지 않는다.
  연중 변경 신고는 AUM을 다시 평가했음을 보장하지 않는다.
- RAUM은 부채를 차감하지 않는 규제상 계산으로, 일반적인 회사 발표 AUM이나
  투자자 NAV와 다르다. 그룹 관계사의 신고를 더하거나 13F 보유액으로 대체하지 않는다.
- 최신 공식 PDF부터 이력을 누적한다. 과거 벌크 파일은 공개되어 있으나 초기
  수집 환경에서 SEC 다운로드가 403이므로 역사적 연말 값은 아직 연결하지 못했다.
- 디렉터리 `us_managers.json`은 개별 카드의 확보 자료에서 만든다. 각 기관의
  확인일을 별도로 표시하고 실패한 기관의 확인일을 오늘로 바꾸지 않는다.

## 업계 자산 / OFR

원문·방법론: <https://www.financialresearch.gov/hedge-fund-monitor/datasets/fpf/>

공개 API `https://data.financialresearch.gov/hf/v1/series/full?mnemonic=...`의
`FPF-ALLQHF_NAV_SUM`, `FPF-ALLQHF_GAV_SUM` 및 9개 `FPF-STRATEGY_*`의
순자산·총자산을 사용한다. 2013 Q1부터의 분기 말 관측값을 USD 십억으로 변환한다.

Qualifying Hedge Funds 표본으로 미국 소재 전체 펀드 통계가 아니다. NAV는
투자자 지분, GAV는 대차대조표 총자산이다. 파생상품 명목 익스포저와 다르다.
비공개 `null`은 유지하고 보간·역산하지 않는다. 원단위·분기 말 날짜·원시 ID와
이력 보존을 검증한다. 과거 정정은 허용한다.

## 성과 / PivotalPath

제공자 공식 사이트의 Public data 링크: <https://www.pivotalpath.com/>
공개 저장소: <https://github.com/pivotalpath/publicdata>
라이선스: CC BY 4.0, 화면에 PivotalPath 출처와 라이선스 링크를 표시한다.

- GitHub의 한 커밋 SHA에 고정해 `metadata.json`, `index_catalog.csv`,
  `index_return.csv`를 읽는다. SHA와 기준월은 카드에 기록한다.
- 10개 실제 공개 수익률 지수만 사용한다. 카탈로그 전체 항목 수를 확보된
  성과 시계열 수로 해석하지 않는다. 글로벌 표본으로 미국 전용 지수가 아니다.
- 보수 차감 후 USD 월별 수익률이다. 종합·크레딧·분산 주식·섹터 주식·이벤트·
  매크로·변동성은 자산가중, CTA·멀티전략은 동일가중. 퀀트 원문에 가중 방식은
  명시되지 않아 단정하지 않는다. OFR와 표본이 달라 자산과 성과를 연결해 계산하지 않는다.
- 원수익률은 소수(`0.01=1%`)다. 월별 표시는 100을 곱한다. 연간은 12개월이
  모두 존재할 때만 `product(1+r)-1`로 계산한다. 당해 YTD를 연간 값으로 섞지 않는다.
- 누적 성과는 10개 지수의 공통 기간 직전인 2002-12-31을 100으로 놓고
  2003-01부터 복리 계산한다. 기간 필터를 바꾸어도 기준점은 바뀌지 않는다.
- 누락 월이 있으면 복리를 계속 계산하지 않고 해당 소스의 기존 문서를 보존한다.
  정정은 날짜를 보존하면서 반영하고 라이선스·단위·스키마 변경은 검토가 필요하다.

## 개별 상품 / PSH

`manual/psh_performance.csv`는 PSH 2025 연차보고서 PDF 4페이지(인쇄 2페이지)
Company Performance 표에서 **2013~2025 PSH**와 동일 표의 S&P 500 총수익을
확인한 값이다. 2004~2012 PSLP와 연결하지 않는다. PSH NAV 성과와 PSH 주가,
PSCM 운용사 전체의 성과를 구분한다.

`manual/psh_monthly.csv`는 공식 NAV 웹 표에서 확인한 2026-01~09의 MTD 값이다.
공표값 반올림 때문에 월별 복리값과 공식 YTD가 조금 다를 수 있다. 월별과 연간
값은 별도 카드로 표시한다. 공식 웹 사이트의 자동 요청이 403이므로 PSH는
**공식 자료 확인 후 수동 갱신**이다. CI의 변환은 새로운 발표의 자동 수집이 아니다.

## 검증

`python -m unittest discover -s scripts -p test_hedge_funds.py`로 복리 계산,
미완성 연도 제외, 공통 기준점, 누락 월·비정상 수익률, 비공개 null 보존,
SEC 법인/금액 검증, 실패 시 기존 소스 파일 보존을 확인한다.

필요시 `--source ofr|pivotal|adv|psh`로 한 소스만 갱신할 수 있다. 기존 국내
기관 프로필·DART 필터·공시 자료는 이 수집기에서 수정하지 않는다.
