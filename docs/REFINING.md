# 정유 기업 실적

`원유 → 정유`에서 Valero(VLO), Marathon Petroleum(MPC), Phillips 66(PSX),
S-Oil(010950)의 2014년 이후 전사 연결 실적을 제공합니다. 정유 부문만의 실적이
아니며 매출·손익·투자를 회사 간 합산하지 않습니다.

- 미국 3사는 USD 백만, S-Oil은 KRW 백만입니다.
- Valero: 정유·재생디젤·에탄올 포함. 현금 CAPEX는 별도 공시된 연결 VIE의
  자본지출도 합산하며 정기보수·촉매 및 비연결 JV 투자는 제외합니다.
- MPC: Refining & Marketing과 MPLX를 포함합니다. Marathon Oil과 다릅니다.
  CAPEX는 현금흐름표의 유형자산 취득입니다. 매출에는 별도 행으로 표시했던
  Sales to related parties도 합산해 연결 매출 범위를 유지합니다.
- Phillips 66: 정유·미드스트림·화학·마케팅·재생연료를 포함합니다.
  전사 영업이익을 별도 공시하지 않아 **매출 − 총비용 + 이자·부채비용**으로
  영업손익을 계산합니다. 지분법 손익·자산매각이익·기타 비매출 수익은 제외하고
  비이자 비용은 유지하므로 공시 EBIT나 조정 영업이익과 같지 않습니다.
  CAPEX는 현금흐름표의 **Capital expenditures and investments**로 지분 투자 등을
  포함합니다. 별도 표시한 기업 인수 대금은 제외하며, 과거 분류 변경에 유의합니다.
- S-Oil: 정유·석유화학·윤활 포함. CAPEX는 유형자산 현금취득이며 무형자산은 제외합니다.

## 출처와 기간 기준

미국 기업은 공개 SEC Company Facts와 10-K/10-Q 원문을 수집하지만, 실제 차트
수치는 **연결 손익계산서·현금흐름표의 해당 행**에서 추출합니다. 사업부·보증인
연결조정·증감 비교표를 제외합니다. 매출은 Sales/Operating revenues 행이며
Total revenues and other income을 매출로 사용하지 않습니다.

과거 연간은 해당 연도 최초 연차보고서 기준입니다. 이후 Speedway 매각 같은
중단영업 재분류나 현금투자 분류 변경으로 재작성한 과거 연간을 당시 분기와
혼합하지 않습니다. 분기 손익은 원문 분기를 사용하며 당시 9개월 누적과 맞는
비교 공시로 재분류를 반영할 수 있습니다. Q4는 해당 연간에서 9개월 누적을 빼고,
현금 CAPEX의 Q2·Q3도 같은 연도 누적 차분입니다. 연간을 4등분하지 않습니다.
유류세 포함·제외 등 원래 공시 기준의 시대별 차이는 인위적으로 조정하지 않습니다.

S-Oil은 주식코드 `010950`으로 OpenDART 법인을 확인해 연결 재무제표를 수집합니다.
API에 없는 2014년·2015년 분기는 [회사 공식 재무제표](https://www.s-oil.com/en/relation/ir/FinancialStatement.aspx)의
손익·현금흐름 PDF 1쪽을 대조한 `manual/refining/soil-*-reviewed.json`으로 보완합니다.
수기 PDF 항목의 `filed`는 검토일로, 당시 공시일을 뜻하지 않습니다.
각 데이터 포인트에는 원문 링크와 차분 계산의 구성 출처가 있습니다.

## 수집·검증·배포

- `scripts/collect_refining_sources.py`: 공개 원문만 `.cache/refining/`에 보관합니다.
  DART 키는 환경변수/CI Secret에서만 사용하며 파일이나 로그로 내보내지 않습니다.
- `scripts/refining_sources.py`: 원문 행·현금 CAPEX 구성·연도별 회계 기준을 검증합니다.
- `scripts/fetch_refining.py`: `data/oil/refining_state.json`과 기업별 12개 차트를 갱신합니다.
  기업별 수집 실패 시 마지막 성공 자료와 기준일을 보존하고 실패 상태를 표시합니다.
- `.github/workflows/update-refining.yml`: 매일 KST 08:50 및 화면의 ‘정유 실적 확인’으로
  실행합니다. 새 공시가 없으면 실적 기준일을 임의로 연장하지 않습니다.
- 검증: `python -m unittest discover -s scripts -p test_refining.py`
- 로컬 원문 재생성: `python scripts/fetch_refining.py --offline`
- 최초 전체 DART 수집: `python scripts/fetch_refining.py --full-history`
- 화면 검증: `python scripts/verify_refining_ui.py --url http://127.0.0.1:8768/`

주요 미국 원문: [Valero 2025 실적](https://investorvalero.com/news/news-details/2026/Valero-Energy-Reports-2025-Fourth-Quarter-and-Full-Year-Results/default.aspx),
[MPC 2025 연차보고서](https://www.marathonpetroleum.com/content/documents/Investors/Annual_Report/2025_MPC_Annual_Report_and_10K.pdf),
[Phillips 66 2025 공시](https://www.sec.gov/Archives/edgar/data/1534701/000153470126000006/psx-20251231.htm).
