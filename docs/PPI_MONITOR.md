# PPI 모니터 통합

KPI의 `PPI` 탭 (`#/ppi`)에서 기존 PPI-Monitoring의 세 가지 보기를 사용한다.

- Overview: 섹터·제목/ID 필터, YoY/MoM 상승률 상위 4~24개, 2~4열 미니 차트.
- Detail: 섹터 탐색 또는 전체 카탈로그 AND 검색, 최대 8개 비교, 요약 및 FRED 원문.
- Table: 최근 6~36개월, 최신값·YoY·MoM, 정렬, 100행 페이지, 전체 결과 CSV.
- 차트: Level / YoY % / MoM % / Indexed (=100), 1Y / 3Y / 5Y / 10Y / 20Y / MAX.

화면은 기존 모니터의 옵션 패널과 차트 구성을 유지하며 KPI 테마를 따른다.
Streamlit 서버나 기존 PPI-Monitoring URL을 사용하지 않는다.

## 데이터 및 성능

기존 FRED Industry Based 카탈로그 6,135개를 이관했다. 카탈로그 분류의
기준일(`catalog_built`)과 관측값 수집일(`updated`)은 별도로 보존한다.
FRED 공개 CSV를 CI에서 묶음 수집하므로 추가 API 키가 필요 없다.
기존 Overview/Table의 BLS 벌크 대신 동일 시리즈의 FRED 원값을 사용한다.
Detail의 실시간 API 요청은 마지막 성공 수집 시점의 전체 이력으로 바뀌었다.
실시간 요청이 필요하면 시리즈의 FRED 링크를 이용한다.

PPI 자바스크립트와 카탈로그는 PPI 탭을 열 때만 읽는다. 스캐너는 선택한
섹터의 최근 49개월만 읽고, 차트는 표시할 시리즈의 전체 이력만 읽는다.
YoY/MoM은 행 위치가 아닌 정확한 달을 기준으로 계산하며 빈 관측값은 채우지 않는다.
Indexed는 표시 기간 내 첫 유효 관측값을 100으로 둔다.
스캐너는 100행씩 표시하며 CSV에는 필터·정렬을 반영한 전체 행이 포함된다.
PPI를 떠나거나 표시 옵션을 바꾸면 차트 인스턴스를 정리한다.

## 갱신

`update-ppi.yml`은 매월 10~20일과 매주 월요일 한국 시간 08:00에 수집한다.
KPI의 상단 `PPI 갱신`도 이 워크플로만 실행한다. 기존 갱신 버튼과 동일한
GitHub Actions 권한을 사용한다. 자동 갱신에는 사용자 토큰이 필요 없다.
네트워크/파싱 실패 시 CI가 실패하고 기존 배포 데이터를 보존한다.
성공한 수집 뒤 `publish-data.yml`이 KPI 사이트를 다시 배포한다.

로컬 갱신:

```powershell
python scripts/fetch_ppi.py
python -m unittest discover -s scripts -p test_ppi.py
node scripts/test_ppi.cjs
```

카탈로그를 갱신할 때는 기존 `build_catalog.py`로 생성한 분류를 명시한다:

```powershell
python scripts/fetch_ppi.py --catalog ../ppi-monitor/data/catalog.json
```

## 기존 배포 종료

통합된 KPI 배포에서 세 가지 보기와 자동 수집이 정상 동작하는 것을 확인한 뒤
기존 Streamlit Community Cloud 앱을 종료할 수 있다. PPI-Monitoring GitHub 저장소와
로컬 원본은 이력 보존용으로 남길 수 있으며 통합 사이트는 이에 의존하지 않는다.
PPI-Monitoring은 GitHub Pages 사이트가 아닌 Streamlit 배포이므로 실제 종료는
Streamlit 앱 관리 화면에서 수행한다.
