# 양자컴퓨터 산업

무료 SEC Company Facts·SEC 재무제표 원문·ECB 일별 기준환율·ETF 운용사 공개 보유 내역을 사용한다. 유료 API와 로그인은 필요 없다.

ETF 탭은 QTUM·QTUP·미국 WQTM·런던 QNTM.L의 일별 가격 차트를 먼저 보여준다. 수정종가·종가·처음=100 보기와 공통 기간 필터를 제공하며, 아래 `구성종목·추적 기업 보기`는 기본으로 접힌다. QTUM·QTUP의 전체 포지션은 각 상품 안에서 별도로 펼칠 수 있고 현물·파생상품·현금을 구분한다. 기존 10개 추적 기업 비교 표도 유지한다.

가격은 Yahoo Finance의 완료된 거래일 USD 자료다. 미국 WQTM은 동명 UCITS와 다르며, QNTM은 [런던 상장 ETF](https://www.londonstockexchange.com/stock/QNTM/van-eck-global/company-page)의 QNTM.L을 사용한다. 거래소·ETF 유형·티커·통화·일별 표본을 검증하며 동명 개별 기업이나 미완료 장중 가격은 배제한다. 수정종가는 분할·분배 조정을 포함하고 NAV와 다르다. QTUP의 이전 티커 LQTM 이력은 공급자가 제공한 범위에서 이어진다.

`scripts/fetch_quantum_prices.py`는 기존 `update-quantum.yml`에서 매일 KST 09:10에 함께 실행한다. 출처 실패 시 직전 성공 이력을 유지하고 실패 상태를 표시한다. 가격은 별도 `prices_state.json`에 보존하며 재무 공시·보유 비중과 기준일을 혼합하지 않는다.

## 추적 범위

- 미국 QTUM·QTUP, 미국 WQTM, 유럽 QNTM UCITS를 소개한다. WQTM 미국/UCITS와 QNTM ETF/동일 티커 개별 기업을 구분한다.
- QTUM·QTUP의 전체 포지션을 공시 기준일과 함께 보존한다. UI의 편입 비중은 **현물 보통주**만 표시한다. QTUP 스왑의 평가비중을 현물에 더해 총 경제적 노출로 해석하지 않는다. WQTM·QNTM의 비중은 현재 수집하지 않는다.
- 초기 10개사는 QTUP 2026-10-26 공개 현물 보유 내역에서 확인: IONQ, RGTI, QBTS, QUBT, QNT, INFQ, XNDU, PSQL, IQMX, HQ.
- IBM·Alphabet 등 양자 사업 매출이 분리되지 않는 대기업은 제외. ARQQ·BTQ·QNC 등 보안·난수 기업은 컴퓨팅 기업과 분리하여 설명한다.
- 기업 전체 연결 실적이다. 센서·사이버보안·광자 부품·파운드리·크라이오스탯·정부 연구 계약 등을 포함할 수 있다. 매출 합계는 양자컴퓨팅 TAM이 아니다.

## 재무제표와 기간

`manual/quantum/companies.json`에 법인 CIK·사업 범위·검토된 XBRL 태그를 둔다. 미국 6개사는 Company Facts를 매일 갱신한다. Infleqtion은 2026년 운영기업 공시에 포함된 비교 이력만 사용하여 종전 SPAC 실적을 배제한다. 2026 Q2 수정 공시의 H1−Q2로 2025 Q1 수정 매출 8.195백만 USD를 반영한다.

해외 4개사 및 Quantinuum IPO 전 연간 실적은 `manual/quantum/sources.json`의 명시적 표·열·단위·행 매핑으로 원문에서 재추출한다. 헤더가 바뀌면 실패 처리하고 이전 성공 자료를 보존한다. 신규 6-K·20-F에서 새 연결 손익계산서를 감지하면 미검토 공시 상태와 링크를 공개한다. 해당 표의 검토·매핑을 추가해야 새로운 기간이 반영된다. 새 공시 목록 조회 성공을 새로운 실적 수집 성공으로 표시하지 않는다.

분기·반기·연간은 각 실제 보고기간이다. 같은 연도 YTD 차감 또는 같은 공시의 H1−Q2로만 분기를 계산한다. 반기·연간 균등 분할, 0 채움, 전망·수주잔고의 매출 대입, IPO 가정 pro forma는 사용하지 않는다. 분기 이력이 없는 Pasqal은 반기를 기본으로 열고 분기 미확보 상태를 표시한다.

순이익은 비지배지분을 포함한 연결 당기순손익이다. Quantinuum의 `NetIncomeLoss`는 모회사 귀속 값이므로 연결 전체 `ProfitLoss`를 우선한다. 상장·주식보상·워런트 평가 등 비현금 항목은 조정하여 지우지 않는다. Quantinuum의 IPO 전 운영기업 연간 실적과 상장 후 연결 기준 차이는 카드에 명시한다.

Horizon의 2024·2025 연간은 운영기업 **SGD** 원자료를 사용한다. 신설 지주회사 2025년 설립 비용과 편의상 USD 환산열을 사용하지 않는다. 2025·2026 분기 비교표는 회사가 공시한 USD 연결 실적을 사용한다. 분기 합계와 연간 환산값이 환율·표시통화 변경으로 완전히 일치하지 않을 수 있다.

## 환산과 출처

USD 공시는 그대로 표시한다. EUR·SGD는 실제 실적 기간의 ECB 일별 `원통화/USD` 산술평균으로 나누어 백만 USD를 만든다. 연간·반기는 각 전체 보고기간의 관측치를 평균한다. 원자료·공시 항목·환율·관측 범위·차감 구성 공시는 메모와 원문 링크로 보존한다. 평균환율 미확보 시 인접 분기·현재 환율로 대체하지 않는다.

## 실행

```sh
pip install requests beautifulsoup4
python -m unittest discover -s scripts -p test_quantum.py -v
python scripts/fetch_quantum.py
python scripts/validate_quantum.py
```

공개 원문은 `.cache/quantum/`에 저장하며 Git에는 넣지 않는다. 원문 캐시가 있으면 `--offline`으로 재생성할 수 있다. `--asof YYYY-MM-DD`로 해당 날짜 이후 공시·보유 내역을 제외한다. 데이터 보존본은 해당 날짜까지 확보한 이력이므로 과거 시점으로 되돌릴 때는 별도 빈 출력 디렉터리/체크아웃을 사용한다.

`update-quantum.yml`은 매일 KST 09:10 실행한다. UI는 현재 탭의 9~12개 차트만 만들고 탭 전환 시 해제한다. 공유 금융 카드의 분기·반기·연간 버튼, 표, 원통화 메모를 사용한다.
