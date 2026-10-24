# CPU 기업 지표

`#/semicon/cpu`는 메모리·파운드리와 같은 회사별 매출 / 영업이익 / CAPEX
세 열을 제공한다. Intel·AMD는 2014년 1분기, 현재 상장 Arm은 확보 가능한
2022년 9월 종료 분기(FY2023 Q2)부터 시작한다. Qualcomm·Apple은 2014년
3월 종료 분기(FY2014 Q2)부터 제공한다. 구 상장 Arm·SoftBank
비상장기의 연간 실적을 분기 데이터로 분할하거나 이어 붙이지 않는다.

`scripts/fetch_cpu_companies.py`는 키 없이 SEC Company Facts를 확인한다.
CIK는 Intel 50863, AMD 2488, Arm 1973239, Qualcomm 804328,
Apple 320193이다. Arm의 구조화된 6-K도
포함한다. `update-cpu.yml`은 매일 KST 08:20에 실행하며 CPU 화면의 갱신
버튼에서도 같은 작업을 실행한다. 회사별 실패는 마지막 성공 자료와 수집일을
유지하고 확인 실패를 별도로 표시한다. 원본 캐시는 `.cache/cpu/`에만 둔다.

단위는 USD 백만, 영업이익은 GAAP이다. Qualcomm CAPEX는 현금흐름표에
표시된 Capital expenditures(PaymentsToAcquireProductiveAssets)이며,
다른 회사는 자체 유형자산 현금취득액이다. 동일 PP&E 태그로 강제 치환하지 않는다.
Intel 발표자료의 Gross/Net CAPEX·금융리스·보조금·파트너
분담액, AMD 외주 파운드리 투자, Arm 무형자산 취득과 구분한다. 원문에서
미확인인 분기는 0이나 추정값으로 채우지 않는다.

52/53주 결산의 실제 종료일과 회계 분기를 보존한다. FY는 종료 연도이며
Arm은 3월, Qualcomm·Apple은 9월 결산이다. 직접 분기 공시는 최신 비교 수치를 사용한다. 누적 차분은
최초 누적 공시와 그때 확인 가능한 동일 회계연도 시작일·동일 태그의 직전
누적을 사용한다. 이후 연간 재분류 수치와 예전 9개월 실적을 혼합하지 않는다.
분기별 공시 시점의 기준 차이가 있으므로 합계가 이후 재작성 연간 보고서와
다를 수 있다. 차분의 두 출처를 표의 원문 링크로 확인할 수 있다.

메모리·파운드리·CPU·SSD의 기업 실적 및 사업 매출 카드 48개 모두 `분기`와
`연간`을 선택할 수 있다. CPU 전사·사업 매출의 연간 값은 SEC 원문에 공시된
완결 회계연도 실적을 사용한다. 다른 반도체 기업 실적은 같은 회계연도의
4개 분기 값이 모두 있는 시리즈만 합산한다. 진행 중이거나 일부 분기가 없는
연도는 연환산하지 않는다. 회사별 결산월을 유지하므로 FY와 달력 연도는 다를 수 있다.

`scripts/cpu_business_history.py`는 SEC 제출 공시의 원본 XBRL에서 사업·제품
차원을 읽는다. Company Facts에는 이 세부 차원이 포함되지 않아 별도 수집이
필요하다. Apple의 과거 제품 매출처럼 숫자 태그가 없던 공시는 같은 공시의
MD&A 제품별 순매출 표를 읽으며, 판매 대수와 증감률은 제외한다. 기존 최근
분기만 보이던 구간은 공시 누락이 아니라 초기 수집 범위의 한계였다.

Arm 로열티·라이선스는 2022년 9월부터 16개 분기, Qualcomm QTL은 2014년
3월부터 50개 분기를 확보했다(2026-10-25 확인). Qualcomm QCT 세부 매출은
공시 분류를 확인할 수 있는 2019년 12월부터 제공한다. `manual/cpu_segments.json`은
시리즈 정의·설명과 초기 원문 대조 표본을 유지하며, 전체 이력은 자동 수집한
원문 자료에서 생성한다. Intel CCG/CCPG·DCAI의 재분류, AMD Client와 Gaming의
구분, Data Center의 CPU·GPU 혼합을 카드에 설명한다. 사업 매출의 누적 차분은
선행 분기와 일치하는 공시 기준을 확인하며, Apple은 제품 합계와 연결 매출도
대조한다. 확인하지 않은 중간 분기는 선을 연결하지 않는다. CPU 출하량·점유율·
CPU 단독 매출은 추정하지 않는다. 사업별 수집 실패 역시 마지막 성공 이력을 보존한다.

Apple Silicon은 별도 공시 사업부가 아니다. Apple 전사 매출·손익·CAPEX와
Mac·iPad·iPhone·Services·Wearables/Home/Accessories 매출을 별도로 표시한다.
iPhone·Mac·iPad·Services는 2014년 3월부터 50개 분기를 확보했다. 현재 분류의
Wearables/Home/Accessories와 과거 iPod·Accessories·Other Products는 서로
다른 시리즈로 유지한다. 과거 분류는 기본 숨김이며 범례에서 선택할 수 있다.
제품 매출을 M/A 시리즈 칩의
매출·이익·출하량으로 환산하지 않는다. 2014년부터의 전사 그래프에는 Mac용
Apple Silicon 전환 이전도 포함된다. Qualcomm QCT의 휴대폰·자동차·IoT 매출도
CPU 전용 실적이 아니며 IoT에는 PC·XR·네트워크·산업용 등이 함께 포함된다.

오프라인 재생성: `python scripts/fetch_cpu_companies.py --offline`

검증: `python -m unittest discover -s scripts -p 'test_cpu*.py' -v`

연간 집계 검증: `python -m unittest discover -s scripts -p test_company_period_views.py -v`
