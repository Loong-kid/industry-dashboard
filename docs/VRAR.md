# VR/AR 기업 실적

국내 사피엔반도체(452430)·라온텍(418420), 해외 Vuzix(VUZI)·Kopin(KOPN)·HTC(2498.TW)·Meta(META)를 등록한다. VR/AR 기기·광학·마이크로디스플레이의 상장 비교군이며 시장 전체나 순수 VR/AR 매출 순위가 아니다. 공식 기업 링크·역할·실적 범위는 `manual/vrar/companies.json`과 전체 비교 표에서 확인한다.

각 회사 매출·영업손익·현금 CAPEX를 기존 실적 카드로 표시한다. 분기와 완결 회계연도를 따로 제공하며 통화는 KRW·USD·TWD 원통화 백만이다. 회사별 실적은 통화·사업 범위가 달라 단순 합산하지 않는다. Meta는 전사 3개 카드와 Reality Labs 사업부 매출·영업손익·영업이익률 3개 카드를 구분한다. Reality Labs의 별도 CAPEX는 추정하지 않는다.

## 원자료와 계산

- 국내: OpenDART의 정기보고서 전체 계정 API. 회사 코드는 종목코드·이름을 동시에 검증한다. 기존 `collect_ring_sources`·`ring_financial_sources`·`fetch_cosmetics`의 연결 우선, 비교표시, 누적 차감 로직을 재사용한다. 상장 전 실제 사업 실적은 후속 공시 비교열에서 확보되며 SPAC 사업 실적은 제외한다.
- Vuzix·Kopin·Meta 전사: SEC Company Facts의 연결 GAAP 매출·영업손익·유형자산 현금 취득. 기존 CPU 재무 파서를 재사용한다. 2014년부터, 실제 52/53주 결산일을 보존한다.
- Reality Labs: SEC 원본 XBRL의 `RealityLabsMember` 또는 `FacebookRealityLabsMember` 문맥을 직접 읽는다. Company Facts에서 사업부가 누락됐다고 미공시로 판단하지 않는다. 2021년 이후 정기보고서의 비교열을 포함한 실제 공개 범위부터 표시한다. 영업손실의 부호를 보존하며 영업이익률은 같은 기간 영업손익÷매출×100이다.
- HTC: 공식 IR 분기 목록의 연결 재무제표 PDF를 탐색한다. 링크에 남아 있는 `investors-express.htc.com`은 같은 공식 문서 경로를 제공하는 `investors.htc.com`으로 정규화하고 `download=1`을 사용한다. PDF의 회사명·연결 제목·연도·신타이완달러 천 단위를 검증하고 백만으로 변환한다. 일부 잘못 연결된 과거 IR 파일은 후속 재무제표의 실제 전기 비교열로 보완한다. 손익은 공시 3개월 금액을 우선하며 Q4는 연간−Q3 누적, CAPEX는 연초 누적−직전 누적이다. 순이익·매각이익을 영업손익으로 사용하지 않는다. PDF 확인 날짜를 출처 메타데이터에 저장하며 실제 공시 제출일로 해석하지 않는다. 2026 Q3 취득지출 누적은 Q2보다 작아 분기 CAPEX를 공백으로 두고 카드 집계 기준에 표시한다.

CAPEX는 유형자산 취득 현금지출로 무형자산·M&A·비현금 리스와 외주 생산업체 설비투자를 제외한다. 연결·별도 및 동일 회계연도 누적 기준이 일치하지 않으면 차감하지 않는다. 확인되지 않은 분기를 연간의 1/4이나 0으로 채우지 않는다. 수집 실패 시 마지막 성공 자료를 보존하고 카드의 갱신 상태에 표시한다.

## 업데이트

`update-vrar.yml`은 매일 10:05 KST에 공개 원문을 확인한다. DART 키는 기존 CI Secret만 사용하며 공개 JSON·로그에 기록하지 않는다. 새로운 HTC PDF와 SEC 공시를 자동 탐색하며 캐시·기존 정규화 이력으로 과거 자료를 보존한다. 수동 갱신 버튼은 같은 워크플로를 실행한다.

```text
python scripts/collect_vrar_korea.py --full-history
python scripts/fetch_vrar.py --refresh --full-history
python scripts/fetch_vrar.py --from-state
python -m unittest discover -s scripts -p test_vrar.py -v
```

원문 캐시 `.cache/vrar`는 공개 배포에 포함하지 않는다. 정규화 이력은 `data/vrar/state.json`, 국내 원문 계정 이력은 `data/vrar/korea_state.json`, 차트 파일은 `company_vrar_*.json`이다. 공개본에는 키가 포함된 요청 URL을 저장하지 않는다.
