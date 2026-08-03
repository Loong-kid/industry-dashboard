# 산업 KPI 대시보드 (Industry Dashboard)

개인투자용 산업별 핵심지표(KPI) 시계열 모니터링 대시보드.
정적 사이트(GitHub Pages) + 매일 자동 데이터 수집(GitHub Actions) 구조.

## 구조

```
industry-dashboard/
├── index.html            # 대시보드 (정적, Chart.js)
├── assets/               # JS / CSS
├── data/
│   ├── catalog.json      # 산업 → 섹션 → 지표 구성 정의
│   ├── shipbuilding/     # 조선 지표 JSON
│   └── shipping/         # 해운 지표 JSON
├── manual/               # 수기입력 CSV (유료 지표용) + manifest.json
├── scripts/
│   ├── fetch_all.py            # 전체 수집 실행 (개별 실패 무시하고 진행)
│   ├── import_manual.py        # manual/*.csv → data/*.json
│   ├── extract_shinyoung.py    # 신영증권 위클리 PDF → 선가/발주량/운임 (로컬 전용)
│   └── fetchers/               # 소스별 크롤러 (kobc, kcla, stockq)
└── .github/workflows/update-data.yml  # 매일 KST 07:30 자동 갱신
```

## 주간 루틴 (신영 위클리 PDF)

새 위클리 PDF를 `Desktop\증권사레포트\조선\`에 넣은 뒤:

```bash
python scripts/extract_shinyoung.py
git add data && git commit -m "data: weekly shinyoung update" && git push
```

신조선가·중고선가·발주량·탱커/가스선 운임이 한 번에 갱신된다.

## 국내 조선 4사 DART 수주 (자동 + 버튼)

HD현대중공업·삼성중공업·한화오션·대한조선의 개별 수주 공시를 척당 단가(원화·달러)로
환산해 표·선종별 척당단가·예상매출로 보여준다. 파이프라인이 **리포 안에 self-contained**로
들어와 있어 **매일 자동 갱신**되고, 사이트의 **'수주 갱신' 버튼**으로 즉시 갱신도 가능하다.

- 데이터 흐름: `dart_extractor.py`(DART→`data/_dart/계약DB.csv` 증분) → `aggregate_korea_orders.py`
  (테이블 + 척당단가 + 예상매출 JSON) → 커밋. CI(`update-data.yml`)가 매일 + 버튼 클릭 시 실행.
- **API 키**: OpenDART 키는 GitHub Secret `DART_API_KEY`로 주입(공개 리포라 하드코딩 안 함).
- **'수주 갱신' 버튼**: 정적 사이트라 서버가 없어, 버튼이 GitHub Actions를 `workflow_dispatch`로
  원격 실행한다. 첫 사용 시 ⚙에서 본인 GitHub Fine-grained PAT(이 리포 **Actions: R/W**)를
  입력하면 브라우저 localStorage에만 저장됨(리포엔 안 올라감).

로컬에서 직접 돌리려면 (선택):

```bash
export DART_API_KEY=<OpenDART 키>   # PowerShell: $env:DART_API_KEY="..."
python scripts/dart_extractor.py --watchlist data/_dart/watchlist.txt --no-docs
python scripts/aggregate_korea_orders.py
git add data && git commit -m "data: DART orders update" && git push
```

상세·파싱 함정은 [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md) 참고.

## 로컬 실행

```bash
pip install -r requirements.txt
python scripts/fetch_all.py        # 데이터 수집
python -m http.server 8000         # file:// 로는 fetch가 막히므로 로컬 서버 필요
# → http://localhost:8000
```

## 수기입력 지표 (클락슨 신조선가 등)

`manual/` 폴더의 CSV에 값을 추가하고 커밋하면 됨. 자세한 방법은
[manual/README.md](manual/README.md) 참고. 데이터 출처별 상세 정리는
[docs/DATA_SOURCES.md](docs/DATA_SOURCES.md).

## GitHub Pages 배포

1. GitHub에 저장소 생성 후 push
2. Settings → Pages → Source: `main` 브랜치 `/ (root)` 선택
3. Settings → Actions → General → Workflow permissions: **Read and write** 선택
   (봇이 데이터 커밋을 push할 수 있어야 함)
4. 이후 매일 아침 데이터가 자동 갱신되고 Pages에 반영됨

## 새 산업/지표 추가

1. **자동수집 지표**: `scripts/fetchers/`에 페처 작성 → `fetch_all.py`의 JOBS에 등록
2. **수기입력 지표**: `manual/`에 CSV 생성 → `manual/manifest.json`에 항목 추가
3. 공통: `data/catalog.json`의 해당 산업 섹션에 지표 id 추가
   (새 산업이면 `industries` 배열에 산업 블록부터 추가)
