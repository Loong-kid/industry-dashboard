# 드론 섹터

## 추적 범위

`manual/drone_universe.json`에서 기업과 ETF를 관리한다. 첫 등록은 미국 상장사 5개이며 전 세계 드론 기업 수나 드론 단독 시장 규모를 뜻하지 않는다.

| 세부탭 | 기업·상품 | 집계 범위 |
| --- | --- | --- |
| ETF·개요 | DRNZ, JEDI | ETF 설명·보수·가격 및 같은 날 100 비교 |
| 기업 주가 | RCAT, UAVS, UMAC, AVAV, ONDS | 수정종가·종가·개별 시작일 100·공통 시작일 100 |
| 드론·비행체 | Red Cat, AgEagle | 연결 매출·영업손익·순손익 |
| 부품·FPV | Unusual Machines | 드론 부품 사업을 포함한 연결 실적 |
| 확장 방산·자율시스템 | AeroVironment, Ondas | 인수·사업 다각화를 포함한 연결 실적 |

AeroVironment는 BlueHalo 인수 이후 우주·사이버 등 사업도 포함한다. Ondas도 대드론·지상 로봇·통신 등으로 범위가 넓다. 이들을 순수 드론 매출로 합산하지 않는다. 비상장 DJI·Anduril·Shield AI·Skydio와 드론 비중을 분리하기 어려운 대형 방산사는 제외했다. 청산된 AdvisorShares UAV도 가격 추적에서 제외했다.

## 출처

- 기업 실적: [SEC Company Facts](https://www.sec.gov/search-filings/edgar-application-programming-interfaces), SEC submissions와 개별 공시. 각 그래프의 포인트에 실제 공시·기간·XBRL 태그·차분 근거를 남긴다.
- 상품 범위·보수: [REX DRNZ](https://www.rexshares.com/drnz/), [Defiance JEDI](https://www.defianceetfs.com/jedi/). 2026-10-27 확인, 자동 변경하지 않는 메타데이터다.
- 가격: Yahoo Finance chart의 일별 USD 종가와 수정종가. 범위 지정으로 일별 자료를 요청하고, 주간·월간으로 축약된 응답은 거부한다.
- 사업 범위: 기업 IR과 공시. 원문 링크는 개요 테이블 및 기업별 집계 기준에 표시한다.

## 실적 처리

기본은 실제 분기이며 각 카드에서 완결 회계연도 실적으로 전환한다. 단위는 USD 백만이다. 매출·영업손익은 연결 기준이다. 순손익은 NetIncomeLoss, AeroVironment는 보통주 귀속 손익을 우선하며 해당 태그가 없는 구간의 ProfitLoss는 비지배지분을 포함할 수 있다. 사용 태그를 포인트 메모에서 확인할 수 있다.

연간을 4로 나누지 않는다. 직접 공시한 3개월 또는 같은 회계연도·같은 태그의 누적 차분만 사용한다. 결측은 선을 끊고 손실의 부호를 보존한다. 52/53주 결산은 회사의 실제 보고일을 따른다.

Red Cat의 2024년 5~12월 8개월 전환기는 연간·정규 분기와 별도 보기로 제공한다. 전환기 3개월 공시는 분기에서 별도 기간명으로 표시하며 회계연도 변경 전후의 전년비를 연결하지 않는다. 과거 영업손익 태그가 없는 구간은 동일 공시·동일 기간의 매출총이익에서 영업비용을 빼고 계산 근거를 남긴다. 일부 공시의 계약매출 태그는 부분 매출이므로 연결 총매출 Revenues를 우선한다.

2014년 이후 가용 공시를 수집하되 Red Cat·AgEagle의 드론 전환 이전 셸·과거 사업 이력과 Unusual Machines의 영업 개시 전 이력은 제외한다. ETF 가격은 실제 첫 거래일 이후만 사용한다.

## 가격과 갱신

미국 정규장이 끝난 거래일만 표시한다. 기본 수정종가는 분할·분배 등의 조정을 반영하며 현재 거래가격이나 ETF NAV와는 다르다. 종가 보기도 Yahoo의 과거 분할 조정 기준을 따른다. 공통 비교는 모든 대상에 가격이 있는 첫 거래일을 100으로 맞춘다. 개별 가격 카드는 각 종목의 더 긴 이력을 유지한다.

`update-drone.yml`이 매일 KST 09:25에 실행하며 수동 갱신도 같은 워크플로를 호출한다. 출처별 실패 시 마지막 성공 이력을 보존하고 상태를 표시한다. 실적·가격 검증 이후 `data/drone/`만 커밋하며 `publish-data.yml`로 배포한다. 장 마감 가격은 일별, SEC 실적은 새 공시가 올라온 뒤 반영된다.

```sh
python scripts/fetch_drone.py
python -m unittest discover -s scripts -p test_drone.py -v
```

로컬 응답 캐시는 `.cache/drone/`에만 저장하고 커밋하지 않는다. `--offline --asof YYYY-MM-DD`는 캐시를 이용한 재현 옵션이다. 공개 `state.json`은 정규화한 기간·가격 및 공시 근거이며 원본 응답 전체를 포함하지 않는다.
