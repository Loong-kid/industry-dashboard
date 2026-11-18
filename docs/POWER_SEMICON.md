# 전력반도체 비교 기업

`반도체 → 전력반도체`에서 기존 Innoscience·Infineon·Power Integrations와
NXP Semiconductors(NXPI)·onsemi(ON)·STMicroelectronics(STM)를 비교합니다.
세 신규 기업은 전력반도체 이외의 사업을 포함한 **전사 연결 US GAAP**입니다.

- 매출·GAAP 영업이익·CAPEX: USD 백만, 분기/연간 전환. 최초 검토 범위는
  2014년 1분기부터 2026년 3분기까지 51개 분기, 2014~2025년 12개 연간입니다.
- CAPEX: 현금흐름표의 유형자산 취득 현금지출. 무형자산·기업 인수는 제외하고,
  보조금·기여금·처분 수입은 차감하지 않습니다. STM의 Non-GAAP Net CAPEX와 다릅니다.
- 연간 값은 완결 회계연도 공시입니다. 진행 중인 연도를 연환산하지 않습니다.
  분기 재분류와 반올림으로 분기 합계와 이후 재작성 연간 값이 다를 수 있습니다.
- 주가·PER·PBR: 기존 `update-semicon-valuation`에 등록했습니다. USD 미국 상장
  NXPI·ON·STM 종가 및 전사 실적 EPS/BPS 기준이며 기존 밴드 산식을 사용합니다.

## 출처와 수집

SEC CIK는 NXP `1413447`, onsemi `1097864`, STM `932787`입니다.
`scripts/fetch_power_semicon.py`가 companyfacts를 조회하고, STM은 신규 20-F와
미국 분기 6-K의 연결 손익계산서·현금흐름표를 보충합니다. STM 유럽 IFRS
연차/반기 보고서(SAR/DAR), 조정 실적 요약 및 사업부 표는 사용하지 않습니다.

과거 API 누락 자료는 `manual/power_semicon_history.json`에 원문 URL·공시일·SHA256과
정규화된 관측값을 보존했습니다. NXP의 구형 공시는 6-K의 HTML 첨부를 사용합니다.
2015년 3분기는 동일 제출 건의 보도자료 날짜 대신 실제 중간재무제표 종료일인
2015-10-04를 사용합니다. 분기 원문은 직접 수치, 누적 CAPEX는 동일 회계연도
누적 차분입니다. NXP 구형 자료의 4분기는 연간에서 공시된 1~3분기 합계를 차감하며,
각 구성 원문의 링크를 차트 출처에 보존합니다.

자동 실적 수집은 `update-power-semicon`이 매일 08:25 KST에 실행합니다.
주가·밴드는 기존 08:10 KST 일정이며 화면의 갱신 버튼도 주가·밴드를 갱신합니다.
회사별 수집 실패·이력 후퇴·최신 분기 불완전 시 마지막 성공 값과 기준일을 유지하고
확인 실패 상태를 표시합니다. 새 STM 원문과 추출 결과는 공개 상태 파일에 누적하므로
매일 과거 전체 HTML을 다시 다운로드하지 않습니다.

```powershell
python scripts/fetch_power_semicon.py
python scripts/fetch_power_semicon.py --offline
python -m unittest discover -s scripts -p test_power_semicon.py -v
```

원문 예: [NXP 2026 Q3 10-Q](https://www.sec.gov/Archives/edgar/data/1413447/000141344726000059/nxpi-20260927.htm),
[onsemi 공식 IR](https://investor.onsemi.com/),
[STM 2026 Q3 6-K](https://www.sec.gov/Archives/edgar/data/932787/000093278726000094/stm-6k_q3x2026.htm).
