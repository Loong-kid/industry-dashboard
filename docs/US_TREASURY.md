# 미국 국채

경로: `#/us_treasury/qra`, `#/us_treasury/auctions`, `#/us_treasury/yields`.
정책·예산 메뉴에 위치하며 기존 국가예산·DARPA 화면과 독립적이다.

## 공식 자료와 자동 갱신

- QRA: [최근 자료](https://home.treasury.gov/policy-issues/financing-the-government/quarterly-refunding/most-recent-quarterly-refunding-documents), [차입계획 아카이브](https://home.treasury.gov/policy-issues/financing-the-government/quarterly-refunding/quarterly-refunding-archives/quarterly-refunding-financing-estimates-by-calendar-year), [발행정책 아카이브](https://home.treasury.gov/policy-issues/financing-the-government/quarterly-refunding/quarterly-refunding-archives/official-remarks-on-quarterly-refunding-by-calendar-year).
- 잠정 경매 일정 XML은 최근 QRA 페이지에서 링크를 발견해 갱신한다. 휴일·단기물·TIPS·FRN을 제외한 만기별 공고·경매·결제 예정일을 표시한다. 일정은 잠정이며, 발행규모가 공시된 월까지만 예정액을 연결한다. 과거 월간 발표본을 선택해도 일정 표에는 **최신 QRA**임을 명시한다.
- 경매: [Fiscal Data](https://fiscaldata.treasury.gov/datasets/treasury-securities-auctions-data/). 공개 API `v1/accounting/od/auctions_query`와 `v1/accounting/od/treasury_securities_auctions_v2`를 연결한다. 전자는 `auction_date`, `inflation_index_security`, 후자는 `comp_auction_close_date`, `inflation_protected`를 사용한다. `record_date`는 경매일이 아니므로 사용하지 않는다.
- 시장금리: [재무부 XML 안내](https://home.treasury.gov/treasury-daily-interest-rate-xml-feed). `pages/xml?data=daily_treasury_yield_curve&field_tdr_date_value=YYYY`를 연도별로 수집한다. [DGS10](https://fred.stlouisfed.org/series/DGS10)은 교차확인 링크이며 FRED API 키에 의존하지 않는다.
- `python scripts/fetch_us_treasury.py`는 세 출처를 독립적으로 갱신한다. 실패한 출처는 이전 관측치·성공일을 유지하고 `ok:false`·확인일을 기록하며, 다른 출처 수집을 계속한다. 실패 종료코드는 모니터링에 사용한다. `--only qra|auctions|yields`로 특정 출처만 확인할 수 있다.
- `update-us-treasury.yml`: UTC 평일 05:20·11:20·17:20·23:20, 즉 KST 14:20·20:20·익일 02:20·08:20. 미국 장 마감 후 금리와 경매 결과를 확인한다. 수동 갱신 버튼도 연결한다. API 키는 필요 없다.
- JSON은 화면별로 나누고 필요한 화면에서만 로드한다. 다른 산업 진입 시 금리 이력을 다운로드하지 않는다.

## 금융 정의

1. 금액은 십억 USD, 금리는 %, 응찰배율은 배, 배정 비중은 %, 장단기 금리차는 bp다.
2. QRA 순차입은 민간보유 시장성 국채 기준이며 차환을 포함한 총발행액과 다르다. 최초·최종 예상과 실제는 발표본별로 보존한다. 분기는 달력연도다. TGA는 분기 말 목표·실제이며 일별 현재 잔고가 아니다.
3. 월별 발행표는 선택 발표본의 명목 고정금리 만기별 경매 규모다. 과거 기재 실적과 당시 계획을 구분한다. 경매 데이터의 실제 금액은 경매일이 속한 월의 공모액이며 단기물·TIPS·FRN을 합산하지 않는다. 구조화 표가 없는 과거 QRA는 원문 링크와 명시적 안내만 제공하고 수치를 추정하지 않는다.
4. 2014년부터 차입계획·정책 발표본 각각 52개를 수집했다(최초 배포 시점). 2015-08-03 차입계획만 공식 PDF로 제공되어 `manual/us-treasury/borrowing-2015-08-03.json`에 검증한 세 분기 값을 보관한다. 공통 파서는 `issue/issued`, `borrow/borrowed`, `pay down/paid down/payed down`과 trillion 단위를 처리한다.
5. 경매 키는 `(CUSIP, 경매일)`이다. 같은 CUSIP의 재발행을 덮어쓰지 않는다. 명목 Note·Bond만 포함하며 TIPS·FRN을 제외한다. 경매에 명시된 만기가 2·3·5·7·10·20·30년이면 이를 우선한다. 9년 10개월처럼 줄어든 일반 재발행은 원래 만기로 연결한다. [2026-01-26의 2년물](https://www.treasurydirect.gov/instit/annceresult/press/preanre/2026/SPL_20260126_1.pdf)처럼 5년물 CUSIP의 추가 발행으로 전환된 경매도 2년물로 분류한다.
6. 공모액 10억 달러 미만은 `small_value:true`로 보존한다. 기본 입찰 차트·월간 계획 대비 실제·시장금리 경매 표식에서는 제외하고, 입찰 화면 체크박스로 포함할 수 있다. [2019-06-21의 소액 시험 경매 공고](https://www.treasurydirect.gov/instit/annceresult/press/preanre/2019/BPD_SPL_20190620_4.pdf)를 일반 월간 수요와 혼동하지 않기 위한 구분이다. 모든 소액 경매가 시험이라는 뜻은 아니다.
7. 응찰배율은 공식 `bid_to_cover_ratio`, 낙찰금리는 `high_yield`를 사용한다. 쿠폰금리와 혼동하지 않는다. 직접·간접·딜러 비중의 분모는 세 경쟁입찰 배정액 합계다. 비경쟁·SOMA 추가 배정은 포함하지 않는다. 간접 응찰자가 전부 외국인은 아니다.
8. 결과 미발표 경매는 `completed:false`이며 응찰배율·낙찰금리·배정 비중을 빈 값으로 유지한다. 향후 공고와 공식 잠정 일정 링크를 표시하며 미래 결과를 생성하지 않는다. 10년물은 월간 이벤트로 표시하고 주간 보간하지 않는다. 12회 이동평균은 유효한 12회 결과가 있을 때부터 계산한다.
9. 시장금리는 오후 약 15:30 ET 호가에 기반한 Daily Treasury Par Yield Curve Rates다. 특정 CUSIP의 실시간 호가가 아니다. 경매 낙찰금리는 실제 경매일의 별도 점으로 표시한다. WI 호가가 없으므로 테일은 계산하지 않는다. 휴일·결측 보간은 하지 않는다.

## 검증

`python -m unittest discover -s scripts -p test_us_treasury.py -v`, `node scripts/test_us_treasury.cjs`.
정의 검증: 재발행 키, TIPS·FRN 제외, 2년물 CUSIP 전환, 소액 구분, 신·구 API 연결,
미발표 결과, 순상환 부호, trillion 단위, 연도 경계, 발표본 비교, 이동평균·금리차.
공통 파일 변경 후 `python scripts/run_ci_tests.py`로 전체 수집 워크플로 시험을 실행한다.
