# 수기입력 데이터

자동 수집이 안 되는(유료) 지표는 여기 CSV에 직접 입력한다.
`python scripts/import_manual.py` 실행 시 `data/` JSON으로 변환·머지된다
(GitHub Actions에서도 매일 자동 실행되므로, CSV만 채워서 push하면 됨).

## 포맷

- 첫 줄: `date,시리즈명1,시리즈명2,...`
- 날짜: `YYYY-MM-DD`
- 빈 칸은 건너뜀 (일부 시리즈만 입력해도 됨)
- 같은 날짜를 다시 쓰면 새 값으로 덮어씀

## 입력 소스 (주 1회, 5분 컷)

| 파일 | 어디서 보고 적나 |
|---|---|
| `clarksons_nb_index.csv` | 아시아시스(asiasis.com, 무료가입) 주간 게시 / Clarksons 관련 뉴스 기사 |
| `newbuild_prices.csv` | 위와 동일 (선종별 신조선가, 백만달러) |
| `secondhand_index.csv` | Clarksons 주간 리포트 인용 기사 |
| `cnpi.csv` | https://cnpi.org.cn/english/ (매월 30일 발표) |
| `lng_freight.csv` | https://www.sparkcommodities.com/lng-freight/ (주간 무료 공개값) / LNG Prime 기사 |

새 지표를 추가하려면: CSV 파일 생성 → `manifest.json`에 항목 추가 →
`data/catalog.json`의 해당 산업 섹션에 id 추가.
