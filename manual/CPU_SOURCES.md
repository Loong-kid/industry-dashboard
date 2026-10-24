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

`manual/cpu_segments.json`은 최근 공식 실적 발표를 대조한 별도 스냅샷이다.
이는 SEC 기본 재무와 달리 새 발표 후 원문 검토를 거쳐 추가한다. Intel
CCG/CCPG·DCAI의 재분류, AMD Client와 Gaming의 구분, Data Center의
CPU·GPU 혼합, Arm 로열티·라이선스를 카드에 설명한다. 확인하지 않은 중간
분기는 선을 연결하지 않는다. CPU 출하량·점유율·CPU 단독 매출은 추정하지 않는다.

Apple Silicon은 별도 공시 사업부가 아니다. Apple 전사 매출·손익·CAPEX와
Mac·iPad·iPhone 완제품 매출을 별도로 표시한다. 제품 매출을 M/A 시리즈 칩의
매출·이익·출하량으로 환산하지 않는다. 2014년부터의 전사 그래프에는 Mac용
Apple Silicon 전환 이전도 포함된다. Qualcomm QCT의 휴대폰·자동차·IoT 매출도
CPU 전용 실적이 아니며 IoT에는 PC·XR·네트워크·산업용 등이 함께 포함된다.

오프라인 재생성: `python scripts/fetch_cpu_companies.py --offline`

검증: `python -m unittest discover -s scripts -p test_cpu_companies.py -v`
