# EIA 전력 데이터셋 정리 (전력 탭 소스)

전력 탭이 쓰는 원본과, 검토했지만 안 쓴 것들을 함께 남긴다.
직접 확인한 사실만 적고, 확인 안 한 건 그렇다고 표시했다.

---

## 1. EIA-860M — 발전설비 인벤토리 (공급) ✅ 사용중

- **홈**: <https://www.eia.gov/electricity/data/eia860m/>
- **파일**: 최신월 `.../eia860m/xls/{month}_generator{YYYY}.xlsx`
  과거월 `.../eia860m/archive/xls/{month}_generator{YYYY}.xlsx`
- **API 키**: 불필요
- **단위**: 발전기 1기 (1MW 이상). 월 1회 발행, 데이터월 기준 약 2개월 지연
- **시트**: `Operating` / `Planned` / `Retired` / `Canceled or Postponed` (+ `*_PR` 푸에르토리코)
- **아카이브 한계**: 2016년부터 매월 일관 존재. 2015년은 03·07월만, 2014년 이전은 없음.
  우리는 **2021-01부터 백필**(원하면 2016까지 확장 가능)
- **파일 안의 이력**: `Operating`의 준공월은 1900년까지, `Retired`의 은퇴월은 **2002년부터**(하드 한계)

무엇을 알 수 있나: 발전원별 설비 규모, 건설 파이프라인과 그 진행 단계(P→L→T→U→V→TS),
준공 지연, 신규 진입, 취소. **발행월(빈티지)을 쌓아야만** 지연·취소가 보인다.

## 2. EIA-930 — Hourly Grid Monitor (수요) ✅ 사용중

- **홈**: <https://www.eia.gov/electricity/gridmonitor/> (인터랙티브 BA 지도도 여기 있다)
- **벌크 CSV**: `https://www.eia.gov/electricity/gridmonitor/sixMonthFiles/EIA930_BALANCE_{YYYY}_{Jan_Jun|Jul_Dec}.csv`
- **API 키**: **불필요** (api.eia.gov v2는 키를 요구하지만 이 벌크 CSV는 공개)
- **단위**: BA × 1시간. 60개 BA. 파일당 30~48MB
- **범위**: **2015년 하반기부터**. 2015 상반기 파일은 없음
- **컬럼**: 수요·수요예측·순발전·구역간 조류 + 발전원별 발전량. 각각 원본/Imputed/**Adjusted** 3벌
- **문서**: <https://www.eia.gov/electricity/gridmonitor/about> (지표 정의·보정 방식)
- **서브지역 파일**: `EIA930_SUBREGION_*.csv` (PJM 내부 존 등, 26MB). 미사용

무엇을 알 수 있나: **구역별 전력 수요와 그 증가율**, 최대수요, 실제 발전 믹스.
860M이 공급이라면 이건 수요라, 둘을 같은 BA 코드로 붙이면
"수요는 X% 느는데 공급 파이프라인은 Y%"가 나온다.

### 파싱 함정
- **EIA 헤더에 오타가 있다.** `Pumped Storage  (Adjusted)`는 공백 두 칸,
  `Solar witho Integrated Battery Storage (Adjusted)`는 with가 **witho**.
  컬럼명을 하드코딩하면 조용히 누락된다 → 공백 정규화 + 정규식으로 추출한다.
- 같은 지표가 3벌(원본/Imputed/Adjusted)이다. **Adjusted가 EIA 보정 완료본**이라 이걸 쓴다.
- 날짜가 `MM/DD/YYYY`.
- 현재 반기 파일은 매일 자란다. 과거 반기는 고정 → CI는 현재 파일만 다시 받는다.

### 930의 발전원 구분은 860M보다 거칠다
가스를 복합/단순으로 나누지 않고, 풍력도 육상/해상을 나누지 않는다.
발전량(에너지)이지 설비(용량)가 아니라서다. 두 소스를 같은 축에 놓고 비교할 때 주의.

---

## 3. 검토했지만 안 쓴 것

| 소스 | 무엇 | 안 쓴 이유 |
|---|---|---|
| **EIA API v2** <br><https://www.eia.gov/opendata/> | 860M·930 포함 대부분을 JSON으로 | **API 키 필요**(무료·즉시발급). 벌크 파일로 같은 걸 키 없이 받을 수 있어 CI가 단순해짐. 과거 발행월(빈티지) 제공 여부는 **미확인** |
| **EIA-923** <br><https://www.eia.gov/electricity/data/eia923/> | 발전소별 월간 발전량·연료소비 | 이용률(가스복합이 실제로 얼마나 도는지) 산출 가능. 파일이 크고 갱신이 늦음. **후보** |
| **EIA-860 (연간)** <br><https://www.eia.gov/electricity/data/eia860/> | 860M의 연 1회 상세판 | 860M으로 충분 |
| **인터커넥션 대기열** <br>LBNL Queued Up <https://emp.lbl.gov/queues> | 860M `Planned`보다 **한 단계 앞**(접속 신청만 한 물량) | 연 1회 공개, 포맷이 매년 바뀜. 상태 사다리 앞에 칸을 하나 더 붙일 수 있어 **후보** |
| **PJM 용량시장 경매** <br><https://www.pjm.com/markets-and-operations/rpm> | 증설 부족이 가격으로 나타나는 지점 | 연 1회라 시계열이 빈약. 숫자 자체는 강력 |
| **FERC Form 714** | 계획 부하 전망 | 갱신 느리고 포맷이 무거움 |

---

## 두 소스를 붙이는 키

**BA 코드가 그대로 일치한다** (`PJM`, `MISO`, `ERCO`, `CISO`, `SWPP`, `SOCO`,
`NYIS`, `TVA`, `ISNE`, `BPAT` … 확인함).
860M은 `Balancing Authority Code` 컬럼, 930은 `Balancing Authority` 컬럼.

주의: 860M에는 BA가 빈 발전기가 일부 있고(주로 소규모), 930에는 860M에 없는
BA가 있을 수 있다. 조인은 **양쪽에 다 있는 코드만** 신뢰한다.

## 주요 BA 코드 (외우기 어려우니 여기 정리)

| 코드 | 이름 | 지역 |
|---|---|---|
| PJM | PJM Interconnection | 동부 13개주 |
| MISO | Midcontinent ISO | 중서부 |
| ERCO | ERCOT | 텍사스 |
| SWPP | Southwest Power Pool | 중부 평원 |
| CISO | CAISO | 캘리포니아 |
| SOCO | Southern Company | 조지아·앨라배마 |
| NYIS | NYISO | 뉴욕 |
| ISNE | ISO New England | 뉴잉글랜드 |
| TVA | Tennessee Valley Authority | 테네시 |
| FPL | Florida Power & Light | 플로리다 |
| DUK | Duke Energy Carolinas | 캐롤라이나 |
| BPAT | Bonneville Power | 북서부 |
| AZPS | Arizona Public Service | 애리조나 |
| PACE / PACW | PacifiCorp East / West | 유타·와이오밍 / 오리건 |
| NEVP | NV Energy | 네바다 |
| PSCO | Xcel Energy Colorado | 콜로라도 |

구역 경계를 눈으로 보려면 Grid Monitor의 지도가 가장 낫다:
<https://www.eia.gov/electricity/gridmonitor/dashboard/electric_overview/US48/US48>
(지도 이미지는 재배포 라이선스가 애매해 리포에 넣지 않고 링크만 둔다)
