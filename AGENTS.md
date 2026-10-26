# Industry Dashboard 작업 규칙

이 저장소는 여러 Codex 세션이 동시에 수정할 수 있다. 사용자 요청과 시스템·개발자 지시가 우선한다.

- 시작할 때 `git status --short --branch`, `git worktree list`, 최근 커밋을 확인한다. 다른 작업의 변경은 보존한다.
- 사용자 요청(2026-10-08): 코딩 폴더에는 최신 `industry-dashboard` 작업 폴더 하나를 유지한다. 업데이트 요청마다 루트에 `industry-dashboard-*` 폴더를 추가하지 않는다. 순차 작업은 기본 폴더에서 진행하며 기존 미커밋 변경을 보존한다.
- 실제 동시 작업으로 분리가 필요한 경우에만 임시 브랜치와 worktree를 사용한다. 임시 worktree는 코딩 폴더의 `.codex-private/worktrees/` 아래에 만들고 같은 체크아웃의 파일을 두 세션이 동시에 편집하지 않는다.
- 임시 작업이 완료되면 최신 main 통합과 커밋 포함 여부를 확인하고, 미커밋 파일·조사 자료를 보존한 뒤 `git worktree remove`로 정리한다. 해당 작업에서 띄운 미리보기 서버도 종료한다. 기본 폴더는 최신 main으로 맞추고 완료된 작업 폴더를 누적하지 않는다.
- 다른 작업의 변경을 없애기 위한 reset, restore, clean, stash를 실행하지 않는다. 다른 세션이 사용하는 worktree나 브랜치를 임의로 전환·삭제하지 않는다.
- 커밋에는 이 작업의 파일·변경만 명시적으로 stage한다. 미커밋 변경이 섞인 공유 체크아웃에서 `git add .` 또는 `git add -A`를 쓰지 않는다.
- main 통합 직전에 fetch하고 최신 main 변경을 작업 브랜치에 합친다. 충돌을 해결할 때 양쪽 기능을 보존하고, 충돌이 없더라도 공통 파일의 동작을 확인한다.
- 기본 폴더의 main 체크아웃에 다른 세션의 미커밋 변경이 있으면 그 폴더에서 pull·merge·checkout·커밋하지 않는다(그 세션이 직접 통합한다). 원격 main은 아래 "Claude·Codex 동시 작업" 순서대로 작업 브랜치에서 갱신할 수 있다.
- push는 일반 push를 사용한다. 거부되면 최신 변경을 합쳐 재검증한다. main에 force push하지 않는다.
- 배포는 최신 main에서 진행한다. 다른 작업의 커밋이 통합 이력에 포함됐는지와 관련 회귀 테스트를 확인한다. 오래된 worktree의 산출물로 다른 기능을 되돌리지 않는다.
- 주요 공통 파일은 `data/catalog.json`, `assets/app.js`, `assets/style.css`, `.github/workflows/*.yml`이다. 다른 변경이 있으면 diff를 다시 읽고 수정 범위를 제한한다.
- 이 파일은 협업 규칙이며 실시간 잠금이나 다른 대화의 자동 알림이 아니다. 이미 실행 중인 다른 세션도 이 규칙을 읽어야 동일한 방식으로 협업할 수 있다.
- 데이터 수집 API 키는 환경변수·CI Secret을 사용하고 원문 링크, 공개 JSON, 로그에 키를 저장하지 않는다.

## Claude·Codex 동시 작업 (2026-10-27 사용자 요청)

사용자는 Claude Code와 Codex에 서로 다른 작업을 동시에 맡긴다. 두 에이전트 모두 이 파일을 따른다(Claude는 `CLAUDE.md`가 이 파일을 가리킨다). GitHub Pages는 main 브랜치를 그대로 배포하므로 **main에 push하는 순간이 곧 배포**다.

1. **작업 공간**: 시작할 때 기본 폴더 `git status`에 내 것이 아닌 미커밋 변경이 있으면 기본 폴더를 쓰지 않는다. `origin/main`에서 새 브랜치(`claude/<작업>` 또는 `codex/<작업>`)를 만들어 `.codex-private/worktrees/<claude|codex>-<작업>/`에서 작업한다.
2. **작업 표시**: 시작할 때 `.codex-private/ACTIVE.md`(git 밖)에 `에이전트 | 브랜치 | 탭·기능 | 손댈 공통 파일 | 시작 시각` 한 줄을 추가하고, main 통합이 끝나면 그 줄을 지운다. 다른 세션이 같은 탭이나 같은 공통 파일을 잡고 있으면 사용자에게 먼저 알린다.
3. **공통 파일 최소 수정**: 새 탭·기능은 `assets/<기능>.js/.css`, `scripts/fetch_<기능>.py`, 별도 `update-<기능>.yml`처럼 자기 파일로 만든다. `data/catalog.json`은 자기 industry 블록만, `assets/app.js`·`style.css`는 연결 몇 줄만 고친다.
4. **main 통합 = 배포 순서**: `git fetch` → 작업 브랜치에 `origin/main` merge(충돌 시 양쪽 기능 보존) → `python scripts/run_ci_tests.py` 전부 통과 → `git push origin HEAD:main`(fast-forward만). 거부되면 다시 fetch부터. force push 금지. 봇이 하루 여러 번 main에 커밋하므로 거부는 정상이다.
5. **시험을 같이 고친다**: `app.js`·`catalog.json`처럼 다른 기능의 시험이 읽는 파일을 바꾸면 `run_ci_tests.py`로 다른 기능의 시험까지 돌리고, 깨진 시험은 같은 커밋에서 고친다. push 뒤 `ci-tests` 워크플로 결과를 확인한다. (2026-10-09 기업 순서 변경 때 시험을 안 고쳐 일일 수집이 19일간 멈췄다.)
6. **data/ 충돌**: 봇이 갱신하는 JSON 충돌은 손으로 합치지 말고 origin/main 기준으로 해당 스크립트를 다시 돌려 만든다.
7. **수집 워크플로**: 새 `update-*.yml`은 `concurrency.group: ${{ github.workflow }}`를 쓴다(그룹을 같이 쓰면 GitHub가 대기 run을 하나만 남기고 나머지를 취소한다). push는 `git pull --rebase && git push` 재시도 루프로 하고, 자기 data 경로만 `git add`한다. 새 워크플로는 `publish-data.yml`의 `workflow_run` 목록에도 추가한다. 검증 단계가 실패해도 무관한 수집이 멈추지 않게 `id` + `continue-on-error`를 붙이고, 그 검증이 지키는 수집 단계만 `if: steps.<id>.outcome == 'success'`로 막는다(`update-data.yml` 참고).
8. **끝낼 때**: 사용자에게 바뀐 탭과 커밋을 짧게 남긴다. 사용자는 두 에이전트의 결과를 나중에 사이트에서 한꺼번에 확인한다.
