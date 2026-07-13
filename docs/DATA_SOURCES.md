# 데이터 소스 정리 (2026-07 리서치)

## 범례
- ✅ 자동수집 구현·검증 완료
- ✍️ 수기입력 (유료/로그인 필요 → CSV 파이프라인)
- 🔍 후보 (추후 검토)

---

## 조선

| 지표 | 상태 | 소스 | 비고 |
|---|---|---|---|
| 클락슨 신조선가 지수 | ✍️ | Clarksons Research (원본 유료) | 아시아시스(asiasis.com) 주간 게시(무료가입 필요, **https 인증서 깨져 있어 http로만 접속됨**), 또는 뉴스 인용값. 주 1회 수기입력 |
| 선종별 신조선가 (LNG/VLCC/컨/벌커) | ✍️ | 위와 동일 | 백만달러 단위 |
| 클락슨 중고선가 지수 | ✍️ | Clarksons Research (유료) | 주간 리포트 인용 기사에서 수기입력 |
| CNPI (중국 신조선가지수) | ✍️ | [cnpi.org.cn](https://cnpi.org.cn/english/) | 매월 30일 발표, 월 1회 수기입력. 크롤링 가능성 추후 검토 |
| 수주잔량/발주량 | 🔍 | Clarksons WFR(유료), KOSHIPA, 한국수출입은행 해외경제연구소 분기보고서 | 확장 후보 |
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
| LNG 스팟 운임 (Spark30S/25S) | ✍️ | [Spark Commodities](https://www.sparkcommodities.com/lng-freight/) (API 유료) | 홈페이지 공개 주간값 또는 LNG Prime 기사에서 수기입력 |
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
