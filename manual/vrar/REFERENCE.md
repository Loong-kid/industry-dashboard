# VR/AR 비교표 및 사피엔반도체 계약 공시

## 구글 시트 비교표

`reference-sheet.json`은 사용자 소유 [산업(VR)_밸류에이션](https://docs.google.com/spreadsheets/d/1tjD_mDi44NNX87ggFguUYMDgHyQCSNLeVhTW4U69YMI/edit)의 2026-11-05 읽기 전용 스냅샷이다. VR 기기·AR 기기의 제품 사양 및 사피엔반도체 오른쪽 AC:BE 계약 메모만 포함한다. 기업가치 계산 등 왼쪽 개인 투자 계산 영역은 수록하지 않는다.

`python scripts/build_vrar_reference.py`로 `data/vrar/reference_tables.json`을 재생성한다. VR/MR 13개, AR/스마트 글래스 22개, 라이트엔진 15개, 패널 40개, 백플레인 6개다. 보조칩 행은 상위 제품에 연결하고, 제품명이 없는 개발 메모와 렌즈 제조사만 있는 행은 제품으로 세지 않는다. 미래 일정, 물음표, 오기와 통화 기재를 원문대로 보존한다. Google Sheets 실시간 자동 연결은 설정하지 않았다.

## DART 계약 팔로업

OpenDART 회사코드 01676642 / 종목 452430의 2024년 이후 거래소 공시 전체 페이지를 조회한다. `last_reprt_at` 필터를 사용하지 않아 정정 전 원문도 보존한다. API 키는 GitHub Actions Secret `DART_API_KEY`를 사용한다.

`python scripts/fetch_vrar_contracts.py --refresh`는 원문을 수집·파싱하고 `contract_source_state.json` 및 `contract_watch.json`을 생성한다. 원문은 receipt별 불변 캐시 또는 기존 상태에서 재사용한다. 수집 실패 시 마지막 정상 원문과 이력을 보존하고 확인 필요 상태를 표시한다.

동일 계약은 원문에 명시된 관련공시 링크로만 연결한다. KIND 접수번호 00xxxx와 DART에 이관된 거래소 접수번호 90xxxx는 동일 날짜·일련번호의 실제 존재하는 공시에 한해 연결한다. 계약일자는 정정 때 바뀔 수 있어 식별자로 쓰지 않는다. 계약일자·고객명이 같다는 이유로 서로 다른 계약을 합치지 않는다.

표의 금액·종료일은 가장 최근 공시의 값이다. 금액은 누적 매출이나 수주잔고가 아니며 정정 전후 금액을 더하지 않는다. 종료일 경과는 납품·수금 완료를 의미하지 않는다. USD는 공시의 기타 투자판단 문구에 직접 기재한 금액이며 원화 환산 추정치가 아니다. 시트의 Meta/JBD 등 고객 실명 추정과 의견은 공식 계약상대방과 별도 열에 보존한다.

기존 `update-vrar.yml`의 매일 10:05 KST 일정에서 재무와 계약을 독립 작업으로 갱신한다. 수동 `contracts_only` 입력은 계약만 갱신하며, `review_contracts_only`는 원문 검토용 artifact만 생성한다. GitHub Actions 대기 상황에 따라 실제 실행 시각은 늦어질 수 있다.

검증: `python -m unittest discover -s scripts -p test_vrar_reference.py -v`. 실제 공시 원문 fixture 및 출처는 `scripts/fixtures/vrar/contracts/`에 있다.
