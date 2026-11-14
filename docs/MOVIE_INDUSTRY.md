# 영화 산업

`#/movies/slate`는 연도별 개봉·흥행, `#/movies/imax`는 IMAX 실적, `#/movies/peers`는 극장·광고 기업 비교다. 작품 표를 먼저 배치하고 영화의 티켓 판매 총액과 기업 재무제표를 구분한다.

## 공개 개봉·흥행 데이터

- The Numbers 북미(미국·캐나다) 개봉 일정: `/movies/release-schedule/{year}`
- The Numbers의 해당 연도 개봉작 분류에 따른 세계 누적 흥행 상위 100편: `/box-office-records/worldwide/all-movies/cumulative/released-in-{year}`
- 원문 `/movie/...` ID로만 연결한다. 비슷한 제목으로 다른 영화·리메이크를 합치지 않는다. 일반 개봉·IMAX·확대 개봉·재개봉 이벤트는 한 작품 아래 보존한다.
- 연도는 북미 개봉 일정과 해당 연도 개봉작의 세계 누적 흥행 차트의 합집합이다. 해외 흥행 상위 작품은 이 연도의 북미 일정이 없을 수 있다. 제목의 저작권 연도로 개봉일을 추정하지 않는다.
- 세계 상위 100편 밖에서는 북미 누적액만 확보될 수 있다. 미확보 해외·세계 금액을 0으로 채우지 않는다. 금액은 작품 누적이며 연간 티켓 매출·해당 재개봉 성적·제작사 매출·순이익이 아니다. 재개봉의 기존 누적 성적도 원문대로 보존한다.
- IMAX 표시는 공개 일정의 IMAX 이벤트 또는 `manual/movies/imax-reviewed.json`의 공식 IR 근거다. 미표시는 비상영 판정이 아니다. 중국 등 지역 한정 IR을 북미 상영으로 확대하지 않는다. 미래 IR 예상작의 일자가 없으면 연도만 남긴다.
- 초기 2014~현재+2년을 수집한다. 매일 전년~현재+2년을 재확인하고 이전 연도는 보존한다. `--full-history`로 모든 연도를 다시 조회할 수 있다. 공개 일정은 모든 국가·모든 IMAX 상영작의 완전한 목록이 아니다.

`release_index.json`의 연도별 성공 여부·실제 확인일과 각 `films_{year}.json`의 수집일을 함께 보존한다. 일부 조회 실패 시 해당 연도의 마지막 검증 데이터를 유지하고 표에 갱신 실패를 표시한다. 초기 조회 실패를 빈 정상 데이터로 게시하지 않는다.

## 기업 실적

IMAX, Cinemark, AMC Entertainment, Marcus, National CineMedia의 2014년 이후 SEC 연결 매출·GAAP 영업이익·현금 유형자산 취득이다. 실제 분기 종료일과 회계연도를 표시한다. 직접 분기 또는 동일 시작일·동일 태그의 당시 누적 차분만 사용한다. 후속 재작성 연간과 당시 기준 차분의 합계가 다를 수 있다.

Cinemark는 공동 제출 공시의 `CnkMember`를 선택하며 Cinemark USA 법인과 합치지 않는다. Marcus의 2015년 7개월 결산 전환기는 12개월 연간 또는 정상 분기로 늘리지 않는다. National CineMedia는 2023년 4월~8월 NCM LLC 연결 제외·재편입으로 연결 범위가 달라진 공시 수치를 그대로 표시한다. IMAX의 유형자산 현금취득 차트에는 별도 항목인 JRSA 장비 투자·무형자산 취득이 포함되지 않는다. AMC는 회사의 현금 CAPEX 태그 `PaymentsToAcquireProductiveAssets`를 사용한다.

회사마다 주석을 표시하며 박스오피스를 매출 또는 이익으로 변환하지 않는다. 첫 수집의 IMAX 2018 Q3 유형자산 누적 차분은 음수로 정합성을 확인하지 못해 빈칸으로 보존한다. 0이나 분기 평균값으로 메우지 않는다.

## 수집·검증

```powershell
python scripts/fetch_movies.py --full-history
python scripts/fetch_movies.py --offline
python -m unittest discover -s scripts -p test_movies.py -v
node scripts/test_movies.cjs
```

`update-movies.yml`이 매일 09:05 KST에 자동 실행한다. 원본 캐시는 `.cache/movies/`, 게시 문서는 `data/movies/`에 둔다. 원문 오류 시 재무 이력을 지우지 않고 마지막 성공 자료와 실패 상태를 보존한다. 성공한 워크플로 뒤 Pages를 배포한다.
