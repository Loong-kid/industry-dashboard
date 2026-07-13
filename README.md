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
│   ├── fetch_all.py      # 전체 수집 실행 (개별 실패 무시하고 진행)
│   ├── import_manual.py  # manual/*.csv → data/*.json
│   └── fetchers/         # 소스별 크롤러 (kobc, kcla, stockq)
└── .github/workflows/update-data.yml  # 매일 KST 07:30 자동 갱신
```

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
