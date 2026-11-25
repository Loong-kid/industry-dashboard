# AI 모델 비교표

데이터센터의 `AI Overview`는 **산업(AI_Datacenter)_밸류에이션** Google Sheet에서 가져온 언어·이미지·영상 모델 자료를 한 탭에 보여준다. 최신 공개 모델과 검토한 가격·AA 지수는 기존 언어모델 표에 들어간다. 예전 `#/datacenter/ai_overview2` 주소도 통합 탭으로 연결한다.

공개 자료 스냅샷 `manual/ai-overview/public-models.json`을 시트 스냅샷과 함께 빌드한다. 기업과 모델명이 일치하면 기존 행을 보완하고, 새 모델은 같은 기업 묶음에 추가한다. AA v5.0.1 점수는 셀에 v5를 표시한다. 변경된 시트 값, 캐시 단가, 벤치마크 설정과 출처는 셀 상세에서 확인할 수 있다. 새 자료를 검토하면 공개 자료 파일의 확인일과 값을 갱신한다.

- 원본: https://docs.google.com/spreadsheets/d/1OPgI46diln8IOADN1MX92e7Q5gKkqtjiekqHliStQPs/edit
- `AI Overview` (gid 1087266006): 언어모델 110개, 44개 열. 가격·사양·여러 벤치마크를 열 묶음으로 선택하거나 전체 열로 볼 수 있다.
- `AI Overview2` (gid 296217995): 이미지 모델 9개, 5개 열 / 영상 모델 11개, 8개 열. 나란히 놓인 두 표를 화면에서는 위아래로 구분한다.
- 가져온 날짜: 2026-11-04. 파일 최종 수정 시각: 2026-10-06T14:35:59.262Z. 이 날짜는 각 가격·벤치마크의 검증일이 아니다.

표시값, 숫자, 셀 메모, 원본 링크를 유지한다. 미기재는 `—`, 실제 0은 `0`으로 표시한다. LLM 입력·출력은 원본 A1의 1M token 기준이며, 이미지·영상 가격은 구독/토큰/초/클립/크레딧 등이 섞여 있어 환산하지 않는다. 평가 조건·reported/독립 평가 등 차이는 열 설명과 셀 메모로 확인한다. 값이나 열의 설명 버튼은 클릭 시 상세 창을 열며 자동으로 긴 설명을 띄우지 않는다.

기업명이 생략된 연속 블록은 그 블록에 기재된 기업명으로 표시하되 원래 셀과 보완 여부를 별도 보존한다. 빈 행을 넘어서 기업명을 채우지 않는다. `중국` 구분 행은 원본 순서에서 유지하고, 모델명이 같은 행도 원본 행 번호로 구분한다. 원본에서 값과 헤더가 모두 없는 영역의 남은 메모는 스냅샷에 보존하지만 빈 열로 만들지 않는다.

이 자료는 **자동 동기화가 아닌 시트 스냅샷**이다. 원본 시트는 수정하지 않았다. 원본 변경을 가져오려면 연결된 Drive/Sheets에서 같은 두 탭의 범위와 셀 메모·링크를 다시 읽어 `manual/ai-overview/sheet-snapshot.json`을 갱신한 뒤 다음 명령으로 생성한다. 비공개 시트를 공개 수집기로 읽는 인증 정보는 추가하지 않는다.

```sh
python scripts/build_ai_overview.py
python -m unittest discover -s scripts -p test_ai_overview.py
node scripts/test_ai_overview.cjs
```

가져온 날짜가 바뀌면 테스트의 날짜·행 수 기준도 새 원본과 비교해 갱신한다. 화면의 기업·검색·열 선택은 원본을 변경하지 않으며 CSV는 현재 표시 중인 행과 열을 저장한다.

Artificial Analysis 리더보드 스냅샷 `manual/ai-overview/aa-leaderboard.json`과 Vals Index 스냅샷 `manual/ai-overview/vals-index.json`도 같이 빌드한다(2026-11-19 확인, 화면 1회 확인값). AA 값은 시트의 HLE·Terminal-Bench 4.0·SciCode·AutomationBench-AA·AA Index 빈칸만 채우고(시트 값은 덮어쓰지 않음, 같은 모델은 반올림 차이만 있음을 확인), 시트에 없는 현행 AA 평가 8개(GDPval-AA, AA-Briefcase, FrontierCode-AA 2.0, GDP.pdf, HLE-Diamond, CritPt v2 Hard, Terminal-Bench Science, AA-Omniscience)를 열로 추가한다. 리더보드에는 단종 모델이 없어 예전 모델은 빈칸이다. AA 이용약관은 스크립트로 페이지를 반복 수집하는 것을 금지하므로 자동 수집기를 두지 않는다. 자동 갱신이 필요하면 AA 무료 API 키(출처 표기 필수)를 CI Secret으로 받아 붙인다.

`2025년 기준 벤치마크` 보기는 Epoch AI 공개 자료(`manual/ai-overview/epoch-benchmarks.json`, CC BY 4.0, 출처 표기 필수)로 만든다. GPQA Diamond·OTIS Mock AIME·FrontierMath T1-3(2025-02 문제판)·SWE-bench Verified·SimpleQA Verified는 Epoch가 직접 돌린 값, HLE·ARC-AGI-1/2·Aider Polyglot·METR 작업 시간은 Epoch가 모은 외부 공식 값이다. 시트의 GPQA·AIME 2025·SWE-bench(제공사 발표)·HLE(AA) 열과 나란히 보여 준다. 모델 이름은 날짜 꼬리표를 떼고 맞추되 출시일 60일 안쪽만 인정하고(Claude 3.5 Sonnet v1/v2 구분), 이름에 들어간 숫자(DeepSeek `1017`)는 꼬리표로 보지 않는다. 갱신은 `python scripts/extract_epoch_benchmarks.py`(zip 내려받기) 후 `python scripts/build_ai_overview.py`.

이미지·영상 표에는 시트 이후 나온 모델을 `manual/ai-overview/public-media.json`(2026-11-25 확인)에서 더한다. 공식 발표·가격 페이지로 확인한 값만 적고, 확인되지 않은 칸(가격 미공개, 참조 개수 미기재, Kling 공식 페이지 미표시 등)은 비워 두고 셀 설명에 이유를 남긴다. 새 행은 같은 기업 묶음 맨 앞(최신순)에, 시트에 없는 기업은 표 끝(기업명 없는 행 앞)에 들어간다. 시트 행은 바꾸지 않는다.