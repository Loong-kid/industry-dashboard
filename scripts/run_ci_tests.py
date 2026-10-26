"""모든 워크플로의 검증 단계 시험을 한 번에 실행한다.

수집 워크플로는 검증 단계(unittest / node scripts/test_*.cjs)를 통과해야 해당 수집을 진행한다.
app.js·catalog.json 같은 공통 파일을 고친 뒤 이 시험을 안 돌리면, 다음 날 아침 수집에서야
깨진 것이 드러난다(2026-10-09~27 일일 수집이 낡은 시험 하나 때문에 19일간 멈춤).

사용: python scripts/run_ci_tests.py            # 저장소 루트에서
      python scripts/run_ci_tests.py update-oil  # 이름에 'update-oil'이 든 워크플로만
수집·집계 명령은 실행하지 않는다(네트워크·키 불필요, 데이터 파일을 바꾸지 않음).
"""
import re
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEST = re.compile(r'^(python -m unittest .*|node scripts/test_[\w.-]+\.cjs)$')


def test_commands(workflow):
    """워크플로에 적힌 시험 명령(unittest, node scripts/test_*.cjs)."""
    commands = []
    for line in workflow.read_text(encoding='utf-8').splitlines():
        text = line.strip()
        if text.startswith('run: '):
            text = text[5:].strip()
        if TEST.match(text):
            commands.append(text)
    return commands


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else ''
    seen, failed = [], []
    for workflow in sorted((ROOT / '.github' / 'workflows').glob('*.yml')):
        if only not in workflow.name:
            continue
        for command in test_commands(workflow):
            if command in seen:
                continue
            seen.append(command)
            result = subprocess.run(shlex.split(command), cwd=ROOT, capture_output=True,
                                    text=True, encoding='utf-8', errors='replace')
            ok = result.returncode == 0
            print(('PASS ' if ok else 'FAIL ') + f'{command}  [{workflow.name}]', flush=True)
            if not ok:
                lines = (result.stdout + result.stderr).strip().splitlines()
                for text in [x for x in lines if re.search(r'Error|FAIL:|ERROR:|assert', x)][:5] or lines[-5:]:
                    print('     ' + text[:240])
                failed.append(command)
    print(f'\n{len(seen) - len(failed)}/{len(seen)} passed')
    if not seen:
        sys.exit('시험 명령을 찾지 못함')
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
