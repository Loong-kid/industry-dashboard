// 기간 달력 입력 정리와, 갱신 버튼이 가리키는 파일·워크플로가 실제로 있는지 시험.
const fs = require('node:fs');
const assert = require('node:assert/strict');

const app = fs.readFileSync('assets/app.js', 'utf8');
const start = app.indexOf('function normalizeCustomRange(');
const normalize = new Function(`${app.slice(start, app.indexOf('function setCustomRange(', start))}\nreturn normalizeCustomRange;`)();
assert.deepEqual(normalize('2024-01-01', '2025-01-01'), ['2024-01-01', '2025-01-01']);
assert.deepEqual(normalize('2025-01-01', '2024-01-01'), ['2024-01-01', '2025-01-01'], '시작이 늦으면 뒤바꿈');
assert.deepEqual(normalize('2024-01-01', ''), ['2024-01-01', ''], '시작만');
assert.deepEqual(normalize('', '2024-01-01'), ['', '2024-01-01'], '종료만');
assert.equal(normalize('', ''), null, '둘 다 비우면 전체');

const html = fs.readFileSync('index.html', 'utf8');
for (const id of ['range-from', 'range-to']) assert.ok(html.includes(`id="${id}"`), id);
assert.ok(fs.readFileSync('assets/card-resize.js', 'utf8').includes('card-size-reset'), '크기 초기화 버튼');

// 삭제된 파일을 가리키면 버튼이 새 데이터를 확인하지 못한다.
const refresh = fs.readFileSync('assets/refresh.js', 'utf8');
for (const [, file] of refresh.matchAll(/file:\s*"([^"]+)"/g)) assert.ok(fs.existsSync(file), `갱신 대상 없음: ${file}`);
for (const [, wf] of refresh.matchAll(/workflow:\s*"([^"]+)"/g)) assert.ok(fs.existsSync(`.github/workflows/${wf}`), `워크플로 없음: ${wf}`);
const targetStart = refresh.indexOf('function currentTarget()');
const target = new Function('window', `${refresh.slice(targetStart, refresh.indexOf('const PAT_KEY', targetStart))}\nreturn currentTarget();`);
for (const [subtab, workflow] of [['osat_summary', 'update-semicon-osat.yml'], ['osat_korea', 'update-semicon-osat.yml'], ['osat_global', 'update-semicon-osat.yml'], ['cleaning_summary', 'update-semicon-cleaning.yml'], ['equipment_summary', 'update-equipment.yml'], ['cpu', 'update-cpu.yml']]) {
  const current = target({dashboard: {state: {industry: {id: 'semicon'}, subtab}}});
  assert.equal(current.workflow, workflow);
  assert.ok(fs.existsSync(current.file));
}
console.log('range and refresh OK');
