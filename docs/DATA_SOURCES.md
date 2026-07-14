# 데이터 소스 정리 (2026-07 리서치)

## 범례
- ✅ 자동수집 구현·검증 완료
- 📄 신영증권 위클리 PDF 추출 (로컬 `scripts/extract_shinyoung.py`)
- ✍️ 수기입력 (유료/로그인 필요 → CSV 파이프라인)
- 🔍 후보 (추후 검토)

---

## 신영증권 「조선/운송 위클리」 PDF (주력 소스)

`C:\Users\공도일\Desktop\증권사레포트\조선\`의 주간 레포트(2024.5~, 자료: 클락슨)에서
`scripts/extract_shinyoung.py`로 추출. 레포트당 (전주, 금주) 2개 주간 컬럼이 있어
겹치며 이으면 끊김 없는 주간 시계열이 됨. **새 레포트 PDF를 폴더에 넣고 스크립트
실행 → 커밋**이 주간 루틴.

추출 지표: 신조선가지수, 선종별 신조선가(15종), 선종별 발주량(연초누적),
중고선가지수(종합/탱커/벌커), 선종별 중고선가(Resale·5년, 18종),
탱커/벌커 운임($/day), VLGC·LNG 운임, ClarkSea Index

### 파싱 함정 (수정 시 필독)
- 페이지가 2단 구성이라 y좌표만으로 행을 묶으면 본문 텍스트가 섞임.
  표 제목 rect(`page.search_for`)의 x0를 왼쪽 경계로 필터링하고,
  표가 왼쪽 단에 있는 경우(발주량)는 값 뒤 추세어(`FIRMER!!`)/%에서 행 절단.
- 헤더 날짜 '3-Jul -26' 공백 변형 존재. 공백 제거하고 파싱하면 옆 컬럼과 붙어
  연도 오염('2610') — 토큰 경계 유지한 채 매칭할 것.
- 중고선가 표는 Tanker/Bulker 섹션 양쪽에 Panamax가 있어 섹션 추적으로 구분.
  Container 섹션은 포맷 변동이 잦아 제외.
- 라벨 드리프트: '84k cbm LPG'→'VLGC(미주/중동-동아시아)'(2026.2~),
  '160k cbm LNG'→'174k cbm LNG'(2024.12~) — 구기준은 별도 시리즈로 유지.

## 조선

| 지표 | 상태 | 소스 | 비고 |
|---|---|---|---|
| 클락슨 신조선가 지수 | 📄 | 신영 위클리 | 2024-05-17 ~ 현재, 주간 |
| 선종별 신조선가 (15종) | 📄 | 신영 위클리 | 백만달러 |
| 신조선 발주량 (선종별, 연초누적 척수) | 📄 | 신영 위클리 | 매년 1월 리셋되는 누적값 |
| 클락슨 중고선가 지수 (종합/탱커/벌커) | 📄 | 신영 위클리 | |
| 선종별 중고선가 (Resale·5Y) | 📄 | 신영 위클리 | |
| CNPI (중국 신조선가지수) | ✍️ | [cnpi.org.cn](https://cnpi.org.cn/english/) | 매월 30일 발표, 월 1회 수기입력 |
| 수주잔량 | 🔍 | Clarksons WFR(유료), KOSHIPA, 한국수출입은행 분기보고서 | 확장 후보 |
| 후판 가격 | 🔍 | asiasis Raw Material 게시판, 중국 철강가격 사이트 | 확장 후보 |

## 해운

| 지표 | 상태 | 소스 | 비고 |
|---|---|---|---|
| KCCI (컨테이너 종합, 13개 항로) | ✅ | [KOBC 해양정보서비스](https://www.kobc.or.kr/ebz/shippinginfo/kcci/gridList.do?mId=0304000000) | timeseries 엑셀 POST 다운로드(세션쿠키 필요). 2022-11부터 전체 히스토리. 주간(월요일 14시) |
| KDCI (건화물, CAPE/PMX/SMX/HANDY) | ✅ | [KOBC](https://www.kobc.or.kr/ebz/shippinginfo/kdci/gridList.do?mId=0301000000) | 그리드 페이지 인라인 JS 파싱. 최근 며칠치만 제공 → 매일 누적. 일간 16시 |
| SCFI (상하이 컨테이너) | ✅ | [한국관세물류협회](https://www.kcla.kr/web/inc/html/4-1_3.asp) | HTML 테이블. 당해년도 주간치 게시 → 누적. 원본은 Shanghai Shipping Exchange |
| CCFI (중국 수출컨테이너) | ✅ | [KCLA](https://www.kcla.kr/web/inc/html/4-1_2.asp) | 위와 동일 |
| HRCI (컨테이너선 용선지수) | ✅ | [KCLA](https://www.kcla.kr/web/inc/html/4-1_4.asp) | 갱신이 다소 늦음. 원본 [harperpetersen.com](https://www.harperpetersen.com/) 크롤링 대체 검토 가능 |
| BDI (발틱 건화물) | ✅ | [KCLA](https://www.kcla.kr/web/inc/html/4-1_5.asp) (일간 히스토리) + [StockQ](https://en.stockq.org/index/BDI.php) (최신값) | 두 소스 머지. 원본 Baltic Exchange는 유료 |
| BDTI (더티탱커 운임) | ✅ | [StockQ](https://en.stockq.org/index/BDTI.php) | 최신값만 제공 → 매일 누적 (히스토리는 쌓이면서 생김) |
| BCTI (클린탱커 운임) | ✅ | [StockQ](https://en.stockq.org/index/BCTI.php) | 위와 동일 |
| 탱커 운임 Average Earnings (VLCC 등 5종) | 📄 | 신영 위클리 | $/day, 주간 |
| 벌커 운임 Average Earnings (케이프 등 3종) | 📄 | 신영 위클리 | $/day, 주간 |
| 가스선 운임 (VLGC 2항로 + LNG 174k) | 📄 | 신영 위클리 | Spark 수기입력 계획을 대체함 |
| ClarkSea Index (종합 해운운임) | 📄 | 신영 위클리 | $/day, 주간 |
| FBX (Freightos 글로벌 컨테이너) | 🔍 | freightos.com/fbx | 확장 후보 |
| 공공데이터포털 KCCI/KDCI 파일 | 🔍 | [data.go.kr KCCI](https://www.data.go.kr/data/15131881/fileData.do) | KOBC 직접 수집이 더 나아서 미사용 (백업 경로) |

## 구현 메모 (페처 수정 시)

- **KOBC 엑셀**: GET으로 grid 페이지 방문해 `JSESSIONID` 획득 후 POST 해야 함.
  GET이나 쿠키 없는 POST는 405/오류. `sDay`/`eDay` 파라미터로 기간 지정.
  응답은 구형 `.xls`(OLE2) → `xlrd` 필요. **주의: timeseries 엑셀은 mId와 무관하게
  KCCI만 반환** (KDCI는 timeseries 페이지 자체가 없음 → 그리드 JS 파싱으로 구현).
- **KCLA**: `4-1_1.asp`(KCFI)는 404로 사라짐. 테이블 구조 = 1행 날짜(`YYYY.MM.DD`),
  2행 값. 연도별 과거 데이터는 페이지에 없음(당해년도만) → 매일 돌려서 누적.
- **StockQ**: 첫 번째 `align=center>숫자` 셀이 최신값, `MM/DD` 셀이 날짜(연도 추정 필요).
- **asiasis.com**: https 인증서가 깨져 있음(TLS 핸드셰이크 실패). `http://`로는 접속됨.
  메인의 클락슨 지수 차트는 2020-21 데이터로 방치 상태이고, 게시판(jisu1: 신조선가,
  jisu2: 해운지수, jisu3: 원자재)은 로그인 필요. 무료가입 후 크롤링 가능한지 추후 확인.
