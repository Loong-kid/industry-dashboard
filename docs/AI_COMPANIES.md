# AI 기업: ARR·인프라 발표

데이터센터 → AI 기업에서 Anthropic과 OpenAI의 회사 발표 연환산 매출, 사용 가능 컴퓨팅, 대표 센터, 발표일별 계획·변경 이력을 본다. 검토 기준일은 2026-11-05이며 새 발표를 검토해 반영하는 스냅샷이다. 전수 센터 목록이나 실시간 전력 관측 자료가 아니다.

`manual/ai-companies/reviewed.json`이 검토 원장이다. 각 기록은 회사/운영사/개발사/SEC 공식 출처, 발표일, 기준 시점, 단위, 비교 기준을 보존한다. `python scripts/build_ai_companies.py`로 표시 JSON을 재생성한다. 미공개 값은 null이며 목표일이 지났다고 가동 상태를 바꾸지 않는다.

- ARR: 회사 전체의 직접 발표 10점과 월 매출 단순 연환산 1점을 구분한다. 계산값은 기본 제외한다. 제품별 ARR나 회계 매출을 회사 ARR에 합치지 않는다. 연/월 발표값은 대표 날짜로 그리되 표와 상세에는 실제 공개 정밀도를 표시한다. 점 사이의 선은 비교를 돕는 연결선이며 관측값을 추가하지 않는다.
- OpenAI 2023~2025년 0.2/0.6/약 1.9GW는 CFO가 2026-01-18에 회고한 사용 가능 컴퓨팅이다. 회사 전체 실제 수전 총량으로 이름을 바꾸지 않는다. Anthropic 전체 수전 총계는 미확인이다.
- Anthropic 2026-05의 470억 달러 초과는 이번 검토에서 정량 확인한 회사 발표다. 이후 공개 S-1의 Run-Rate Revenue 수치 공란은 채우지 않는다. 기사·추정 ARR를 직접 회사 발표로 넣지 않는다.
- 센터 계획 MW, 전력 가용 MW, 가동 건물 MW, 컴퓨팅 계약 MW는 서로 다른 기준이다. Abilene의 초기 200MW 건물 가동과 이후 75% 인도율도 각각의 날짜·기준으로 보존하며 곱셈으로 추정하지 않는다. 인접 Microsoft 900MW는 OpenAI 용량에서 제외한다.
- Oracle 사이트 고객 공급 목표 2027년 상·하반기는 2026-06/09 자료를 반영한다. Milam의 1.2GW 임대와 Lordstown·Milam 합계 1.5GW는 겹치는 프로그램이다. Texas/New York Fluidstack 계획은 합산 투자이며 두 행의 투자액으로 중복 집계하지 않는다.
- NVIDIA·AMD·Cerebras 공급 계약, AWS/Google 계약, Stargate 전체 계획과 개별 사이트는 겹칠 수 있다. `overlap_group`을 보존하고 합계는 제공하지 않는다. Colossus 1 300MW 초과는 접근 계약으로, 인도 완료나 실측 수전으로 승격하지 않는다.

화면은 기존 대시보드의 system-ui/Malgun Gothic을 사용한다. 바탕 #f9f9f7, 표 #fcfcfb, 본문 #0b0b0b, 보조 #898781, 기업 선 #2a78d6/#1baf7a를 따른다. 작은 회사별 현황 뒤에 같은 크기의 ARR·컴퓨팅 차트 두 개를 놓고, 그 아래 센터·발표 이력·ARR 원장을 나열한다. 숫자는 오른쪽, 긴 내용은 고정 높이 셀의 말줄임 및 클릭 상세 창에 둔다. 이 화면에서 회사가 직접 소유한 센터로 오인하지 않도록 개발·운영 역할을 표시한다.

검증:

```sh
python -m unittest discover -s scripts -p test_ai_companies.py
node scripts/test_ai_companies.cjs
python scripts/run_ci_tests.py
```
