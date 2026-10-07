# 포토마스크 패터닝 지표

에스앤에스텍 탭의 일본 3사 다음에 Photronics와 Tekscend를 회사별로 배치한다.
완성 포토마스크 매출/구성비이며 블랭크마스크 단독 매출, 출하량 또는 전체 시장 규모가 아니다.

## Photronics

- 공식 SEC 자료함: https://photronicsinc.gcs-web.com/financial-information/sec-filings
- `scripts/fetch_mask_patterning.py --backfill`: FY2021부터 회사 IR의 10-Q/10-K 제품 매출 주석을 수집.
- 기본 실행: 최근 제출을 확인하고 새 PDF만 파싱. `--offline`: 보관한 숫자 표에서 재생성.
- `data/_mask_patterning/photronics_filings.json`: 출처 URL·PDF 페이지·공표일·실제 종료일·천 달러 단위 숫자 표.
- Q1~Q3는 Three Months Ended 열. Q4는 연간 금액 − Q3의 Nine Months Ended 열. 각 Q4 표에서 두 원문으로 이동 가능.
- 화면 단위는 백만 달러. 원문 천 달러 정밀도를 유지하며 MD&A의 반올림된 백만 달러 표는 사용하지 않는다.
- 회사 FY와 실제 종료일을 표시. 2026-08-02는 FY2026 Q3이다. 달력 Q3로 바꾸지 않으며 YoY/QoQ도 FY·분기 번호로 연결한다.
- IC 고급은 28nm 이하이며 EUV 단독이 아니다. FPD 고급은 회사 분류의 AMOLED·LTPS·G10.5+다.
- 각 제품 합계는 고급+범용과 일치해야 한다. 연간 대비 분기 합의 전체 IC/FPD 차이는 천 달러 반올림 오차(최대 2)만 허용한다.
- FY2022 IC 고급 분기 합은 누적 기준보다 $389k 작고 범용은 $390k 크다. Q2의 6개월 누적 고급 금액도 다음 해 비교표에서 $97,896k→$98,285k로 달라지지만 비교 3개월 금액은 유지돼 있다. 원문 3개월 금액을 유지하고 분류 차이를 카드 집계 기준에 공개한다. 차이를 임의의 분기에 배분하지 않는다.
- 일일 update-data에서 새 제출을 확인한다. 수집·검증 실패 시 기존 공개 차트 파일을 유지한다.

## Tekscend (옛 TOPPAN Photomask)

- 공식 자료함: https://www.photomask.com/en/ir/results-briefing/
- `manual/tekscend_sales_mix.json`: PDF 그래프에서 확인한 공정별 3개·용도별 2개 비중. 달력 2024 Q2~2026 Q2, 9개 분기.
- 2026-06-19 정정된 연간 설명자료 PDF 8~9쪽으로 FY2024/FY2025의 8개 분기를 확인했다.
- 2026-08-06 FY2026 Q1 설명자료 PDF 6~7쪽의 최신 FY2026 Q1 막대만 추가했다. 이전 분기 축 표기와 막대 순서가 어긋나는 부분은 해당 자료에서 재추출하지 않고 정정 연간 자료를 유지했다.
- 연간 막대는 분기 시계열에 넣지 않는다. 선단은 ≤28nm, 중간은 원문 28~90nm, 성숙은 >90nm라는 회사 표기를 보존한다.
- FY2026 Q1(4~6월)=달력 2026 Q2. 최신 공정 비중 35/35/30, 로직·기타/메모리 89/11.
- 분모는 포토마스크 제품 매출이다. 연결 총매출에 곱해 제품별 매출을 역산하지 않는다.
- 구성비 합계는 반올림을 고려해 100±1%만 허용한다. 발표 때 수기 검토 후 스냅샷을 갱신한다.

## 검증

```
python -m unittest discover -s scripts -p test_mask_patterning.py
node scripts/test_blankmask_ir.cjs
```
