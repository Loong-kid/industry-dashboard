# 미국 전력·ESS 비용과 태양광 시장

## NLR Electricity ATB

공개 OEDI 전력 ATB Parquet의 판본과 수정 번호를 확인해 최신 버전을 수집한다. 첫 반영은 2025 Electricity ATB `v2.0.0`이다. 비용은 2023년 기준 실질 달러이고 2023년 점은 기준연도 추정, 이후는 모형값이다. [ATB 데이터와 정오표](https://atb.nlr.gov/electricity/2025/data)

- **ESS 시장 현황**은 미국 60MW / 240MWh LFP 배터리의 중간·보수·낙관 시나리오를 비교한다. 시스템 CAPEX `$/kW`를 4시간으로 나눠 `$/kWh`로 표시한다. 고정 운영비는 원자료 `$/kW·년`을 사용한다.
- **전력**은 중간 기술 시나리오와 R&D 금융 조건, 30년 비용회수, 세액공제 미적용 값을 사용한다. 대형 태양광·태양광+ESS Class 5, 육상풍력 Class 4, 고정식 해상풍력 Class 3, 탄소 포집 장치가 없는 H급 2-on-1 가스복합을 비교한다. 가스복합은 설치비·고정 운영비·열소비율을 표시한다.

## 태양광 시장 현황

- **Berkeley Lab**은 미국 5MWac 초과 지상 설치 프로젝트를 집계한다. 준공량은 `PV Capacity over Time`의 각 완결 연도 12월 누적 준공량이다. 설치비는 `CapEx Trend (PV-only)`의 AC 기준 중앙값과 설비용량 가중평균이다. PPA는 `LCOE vs. PPA Price (PV only)`에서 PPA와 LCOE가 모두 있는 프로젝트의 발전량 가중평균이며, 가로축은 계약 체결연도가 아닌 상업운전 개시연도다. 설비이용률은 `CF by Project Vintage`의 준공연도별 용량 가중평균이다. 첫 반영은 2026년판이며 비용은 2025년 실질 달러다. [Berkeley Lab 데이터](https://eta-publications.lbl.gov/publications/us-utility-scale-solar-2026-edition) · [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
- **EIA**는 Electric Power Monthly 표 6.1.B의 1MW 미만 태양광 설비용량을 사용한다. 미국 전체, 주택용, 상업용, 산업용을 원자료 MW에서 GW로 환산한다. 월간 보기에는 이전에 수집한 월을 남기고 EIA가 새로 공개한 월과 수정분을 적용한다. 연말 보기는 원본의 연말 스냅샷을 사용한다. [EIA 표 6.1.B](https://www.eia.gov/electricity/monthly/epm_table_grapher.php?t=table_6_01_b)

## 갱신

`update-energy-market.yml`이 매주 수요일 08:00 KST에 세 출처를 확인한다. 각 출처의 실제 발간 주기는 ATB와 Berkeley Lab이 연간, EIA가 월간이다. 태양광 시장 탭의 갱신 버튼도 이 워크플로를 실행한다. 출처별로 원본의 열·단위·기간을 검증하며 수집 실패 시 해당 자료의 직전 성공본을 유지한다.

```sh
python scripts/fetch_energy_market.py atb
python scripts/fetch_energy_market.py berkeley
python scripts/fetch_energy_market.py eia
python scripts/run_ci_tests.py update-energy-market
```
