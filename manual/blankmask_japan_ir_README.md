# 일본 블랭크마스크 공급사 IR

`blankmask_japan_ir.json`은 공식 PDF에서 확인한 **실적**만 보관한다.
각 관측값에 달력 분기, 회사, 제품/사업부 범위, 단위, URL, 실제 PDF 페이지를 기록한다.
입력 금액 단위는 십억 엔(`billion_jpy`), 화면은 억 엔(입력 × 10)이다.
예: HOYA FY26 Q1 = 2026년 4~6월 = 달력 2026Q2.

- HOYA: 분기 설명회 transcript의 IT 사업부 매출, 별도로 LSI 제품군 매출 YoY와 CC YoY.
- AGC: [공식 Financial Data Book](https://www.agc.com/en/ir/pdf/data_all.pdf)의
  PDF 14쪽 사업별 **분기** 매출(원문 백만 엔 ÷ 1,000), Electronic Materials 행.
  연간 검증값은 PDF 5쪽이며 분기 합계와 1백만 엔의 반올림 차이가 있다.
- 신에츠: 분기 실적 PDF 부록 `Quarterly Operating Results`의 Electronics Materials
  **매출** 행. 영업이익 행과 혼동하지 않는다. 회사가 재작성한 2021년 비교 수치부터 사용한다.
- AGC EUV: FY2024 발표자료 PDF 45쪽의 400억 엔(연간 실적).
  2026년 6월 반도체 사업 설명회 transcript PDF 17쪽에서 재확인됐다.

최신 IR 발표 후 원문에서 새 수치를 확인해 입력하고 `checked`를 실제 확인일로 변경한다.
`python scripts/aggregate_blankmask_ir.py`로 화면 JSON을 재생성한다.
일일 CI는 입력값을 변환할 뿐 새 PDF의 값을 자동 추정하거나 수집하지 않는다.

단독 매출은 상위 사업부 매출로 대체하지 않는다. 성장률에서 절대액을 역산하거나
연간 금액을 4로 나누거나, 금액 눈금이 없는 막대 높이에서 금액을 읽지 않는다.
사업부 매출은 단독 금액과 구분한 참고 그래프에만 사용하며 3사 합계/TAM/점유율은 계산하지 않는다.
원문이 수정돼도 이미 기록된 출처와 범위가 사라지지 않도록 해당 분기 기록을 정정한다.
