# 수기입력 데이터

자동 수집이 안 되는 지표는 여기 CSV에 직접 입력한다.
`python scripts/import_manual.py` 실행 시 `data/` JSON으로 변환·머지된다
(GitHub Actions에서도 매일 자동 실행되므로, CSV만 채워서 push하면 됨).

> 클락슨 신조선가·중고선가·선종별 선가·해상운임은 원래 수기입력 대상이었으나
> **신영증권 위클리 PDF 추출**(`scripts/extract_shinyoung.py`)로 대체되어 CSV가 삭제됨.
> 현재 수기입력은 CNPI 하나뿐.

## 포맷

- 첫 줄: `date,시리즈명1,시리즈명2,...`
- 날짜: `YYYY-MM-DD`
- 빈 칸은 건너뜀 (일부 시리즈만 입력해도 됨)
- 같은 날짜를 다시 쓰면 새 값으로 덮어씀

## 입력 소스

| 파일 | 어디서 보고 적나 |
|---|---|
| `cnpi.csv` | https://cnpi.org.cn/english/ (매월 30일 발표, 월 1회) |

새 지표를 추가하려면: CSV 파일 생성 → `manifest.json`에 항목 추가 →
`data/catalog.json`의 해당 산업 섹션에 id 추가.
