# ESS 생산시설 비교표

ESS 탭에 테슬라 4개, 선그로우 5개, 플루언스 4개의 **시설·프로젝트 기록**을 표시한다. 이는 13개 독립 소유 공장을 뜻하지 않으며 전체 공장 목록을 보장하지 않는다. 2026-10-08에 공개 자료를 검토했다. 기존 전력 공통 지표 5개와 기업 지표 18개는 유지한다.

## 자료와 갱신

- 원본: `manual/ess_factories.json` — 사람의 자료 검토를 거쳐 갱신하는 등록부.
- 게시: `data/ess/ess_factories.json` — `python scripts/aggregate_ess_factories.py`로 생성.
- 각 면적·CAPA·가동 상태·운영 권리에 개별 기준일과 출처 ID를 기록한다. 화면의 ‘출처·범위 보기’에서 해당 근거를 확인할 수 있다.
- 일일 워크플로는 검증·단위 환산만 실행한다. 검토일이나 시설 상태를 오늘 날짜로 바꾸거나 계획일이 지났다는 이유로 가동으로 전환하지 않는다.
- 공식 발표, 공시, 지방정부, 시공사 자료를 사용했다. Tesla Brookshire 공식 X 게시물은 X의 공개 `cdn.syndication.twimg.com/tweet-result` 응답에서 계정·원문·2026-08-06 게시일을 확인했다. 원문 링크는 공식 X 게시물이다.

## 해석 원칙

**CAPA:** Tesla Q2 2026 자료(PDF 8쪽)의 Installed Annual Manufacturing Capacity는 실제 생산속도와 다르다. Lathrop 40, Shanghai 20, Nevada Powerwall >6GWh/년을 설치 CAPA 열에 넣는다. Shanghai 약 40GWh 계획, Brookshire 설계 50GWh는 별도 열이다. Brookshire는 2026-08-06 발표로 2분기 시운전 상태를 업데이트하지만 수치 기준을 설치 CAPA로 바꾸지 않는다. Powerwall과 Megapack은 별도 제품이다.

**면적:** 명시된 전체 gross construction area만 전체 연면적에 넣는다. Lathrop 시의 2023년 440,538sqft는 건물면적이지만 연면적 정의와 이후 확장 포함 여부는 불명확하다. Nevada 540만sqft는 2023년 전체 Gigafactory 시설면적으로 ESS 전용이 아니다. Shanghai 약 20만㎡와 Egypt 5만㎡는 부지다. Poland 65,400㎡는 발표에서 시설면적으로만 부르므로 부지/연면적 분류를 유보한다. Hefei 20GWh의 9,402.9㎡는 19동 한 동의 연면적이다. 위 수치는 ‘부지·기타 공표면적’에 종류와 기준일을 함께 표시한다. 1sqft = 0.09290304㎡로 환산하고 원래 값도 보존한다.

**소유:** 직접 운영, 계약생산, 건물 소유/임차를 혼동하지 않는다. Tesla 2025 10-K Properties 기준 Lathrop은 임차, Nevada는 소유, Shanghai는 건물 소유 및 토지 사용권이다. Brookshire를 Austin Gigafactory Texas와 동일 시설로 취급하지 않는다. 선그로우 신규 프로젝트 투자가 건물·토지 소유권까지 입증하지는 않는다. Fluence의 협력사 공장은 Fluence 자체 소유로 집계하지 않는다. Utah 모듈 생산라인 금융리스도 공장 건물 소유와 다르다.

**중복·기간:** 선그로우 Hefei 기존 공장, 2023년 25GWh 1기, 2026년 20GWh 프로젝트의 물리적 중복 범위가 불명확하므로 회사 총 CAPA나 독립 공장 수로 합산하지 않는다. 25GWh 기록은 2023년 공사 수주 당시 계획으로 현재 완공/가동은 미확인이다. Poland는 2026-02-05 발표 당시 12개월 내 운영 목표, Egypt는 2026-09-03 발표 당시 2027년 6월 운영 목표다.

**Fluence:** Vietnam ACE의 35GWh는 개소 발표의 projected annual capacity이며 설치 완료 능력이나 달성 생산량으로 확정하지 않는다. Utah 모듈, Goodyear 외함/BMS, Houston 열관리장치의 CAPA는 미확인이다. 부품 단계와 완제품 단계를 합산하지 않는다. Houston의 2025년 8월 가동은 2025 연차보고서 PDF 6쪽의 일정에서 확인했다.

**미확인:** 검토한 자료에서 값을 찾지 못했다는 뜻이며 ‘공시가 영원히 없다’거나 0이라는 뜻이 아니다. 구형 Sungrow-Samsung 2GWh 계획, Fluence FY2024 Utah Cube 약 6GWh 계획, 분당 생산속도로 현재 CAPA를 대신하지 않는다. ESS 제조가 확인되지 않은 Sungrow India/Thailand 인버터 공장과 공급사 전체 셀 CAPA는 제외했다.

## 검증

`python -m unittest discover -s scripts -p test_ess_factories.py`는 면적 범위·환산, 설치/설계값 구분, 하한·상한 보존, 미확인 처리, 출처 참조와 계획 시설 설치 CAPA 오표기를 검사한다. 브라우저에서는 필터 교차 적용, 출처 펼치기, 빈 결과, 모바일 표 가로 스크롤과 기존 ESS 차트 회귀를 확인한다.
