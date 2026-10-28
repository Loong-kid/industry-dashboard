# Flex LNG / Golar LNG 실적

천연가스 → **가격·LNG** 탭의 기존 LNG 해운 주가 카드 아래에 두 기업의 매출·영업이익·연결 전체 순이익을 추가했다. 각각 분기/연간 버튼, 출처가 연결된 표, 원금액·집계 메모를 제공한다. 단위는 원문 그대로 백만 USD이다. 기존 가격·선물·LNG 공급·선단·비료 지표는 유지한다.

## 기업과 공시 범위

- **Flex LNG Ltd., FLNG, CIK 1772253**: LNG 운반선 보유·용선 운영 연결 전체. 부유식 액화설비 일반명 FLNG와 종목 코드를 구분한다. 초기 상업 운항 전 실제 매출 0과 손실을 보존한다. 2019년 전후 IFRS·US GAAP 표시 전환, 선단 증가, EUA 포함 매출과 TCE 수익 차이를 설명한다.
- **Golar LNG Limited, GLNG, CIK 1207179**: Golar LNG Partners LP와 다른 법인. 과거 운송·FSRU와 현재 FLNG 중심 사업이 다르다. 액화 서비스·판매형 리스·선박 관리 등 공시된 연결 전체 매출과 영업손익을 사용한다. 순이익은 **비지배지분 포함 전체 순손익**이며 주주 귀속 수치를 쓰지 않는다. 파생상품 평가·자산 매각·중단영업이 포함될 수 있다.

예: 2026 Q2 Flex 매출/영업이익/순이익은 $106.799m / $59.468m / $44.851m. Golar는 $130.479m / $64.440m / $55.835m이며, 헤드라인의 주주 귀속 $38.265m와 구분한다.

## 이력·원문

두 회사 모두 2014 Q1~2026 Q2 50개 분기와 2014~2025 12개 연간을 확보했다. `manual/lng-carriers/reports.json`에는 공식 분기 PDF **97건**의 URL·발행일·SHA256·실제 손익계산서 페이지·행·수치·열의 실제 보고기간·천 USD 단위를 보존한다. 초기 검토 시 전 원문의 해시 및 실제 행을 대조했다. 요약표·사업 부문 표·조정 EBITDA·주당 수치·현금흐름표를 연결 손익계산서로 사용하지 않는다.

분기는 당시 공시와 같은 회계연도의 후속 분기 공시에서 명시된 실제 전분기 수치다. 빠진 단일 분기는 실제 누적과 확인된 다른 분기를 차감할 때만 복원한다. 예: 같은 공시 H1−Q2, 같은 해 9M−실제 Q1−실제 Q3. 연간/4 또는 선형 보간은 없다. 차감 원문을 모두 보존한다.

연간은 SEC Company Facts의 해당 연도 최초 확보한 완전한 감사 연결 공시를 우선한다. Golar의 총 순이익은 `us-gaap:ProfitLoss`, Flex는 해당 법인의 `us-gaap:NetIncomeLoss`다. 세 지표는 동일 accession에서 확보한다. 후속 연도 중단영업 재분류로 과거 사업 범위를 일괄 교체하지 않는다. SEC 감사 공시 미확보 초기 Flex 2014~2016 연간은 공식 결산 발표 수치이며 감사 전임을 메모에 표시한다.

감사 조정·사업 범위 변경으로 실제 분기 합계와 감사 연간이 다른 기간은 숫자를 억지로 맞추지 않는다. `reconciliation`과 차트·표 메모에서 해당 연도/지표를 알린다. 공표된 과거 매출/순손익과 이후 계속영업 범위를 같은 것으로 해석하지 않는다.

## 운영

`update-natgas.yml`의 `lng_carriers`가 매일 08:55 KST 독립 병렬 실행한다. 가격·미드스트림 수집에 의존하지 않는다. 자체 검증에 실패해도 다른 job은 계속되며, 변경 데이터는 `carrier_*.json`, `lng_carriers_state.json`만 stage한다.

SEC 감사 연간과 공식 분기 목록·최신 원문을 매일 조회한다. 현재 검토되지 않은 새 분기나 교체된 PDF는 원문 검토 필요 상태로 표시하고 마지막 성공 이력을 유지한다. 검토 이력이 없는 새 레이아웃을 자동 추정하지 않는다. 최초 실행에서 검토 PDF를 검증하며 이후 immutable 과거 자료는 재사용한다. 키나 유료 API는 필요 없다.

```sh
python scripts/fetch_lng_carriers.py
python scripts/fetch_lng_carriers.py --offline
python -m unittest discover -s scripts -p test_lng_carriers.py
python scripts/validate_lng_carriers.py
```

원문 캐시 `.cache/lng-carriers/`는 사이트 배포에서 제외한다.

공식 출처: [Flex 분기 보고서](https://www.flexlng.com/category/quarterly-reports/), [Golar 분기 보고서](https://www.golarlng.com/investors/quarterly-reports/2026.aspx), [SEC Flex](https://data.sec.gov/api/xbrl/companyfacts/CIK0001772253.json), [SEC Golar](https://data.sec.gov/api/xbrl/companyfacts/CIK0001207179.json).
