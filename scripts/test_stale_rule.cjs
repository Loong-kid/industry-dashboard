// 수집 지연 판정: 분기·연간 공시는 다음 기간이 나올 때까지 지연으로 치지 않는다.
const fs = require('node:fs');
const assert = require('node:assert/strict');

const source = fs.readFileSync('assets/app.js', 'utf8');
const pick = pattern => {
  const match = source.match(pattern);
  assert.ok(match, `app.js에서 찾지 못함: ${pattern}`);
  return match[0];
};
const code = [
  pick(/const STALE_DAYS = \d+;/),
  pick(/const DISCLOSURE_DUE_DAYS = \{[^}]+\};/),
  pick(/function staleDays\(doc\) \{[\s\S]*?\n\}/),
].join('\n');
const today = Date.UTC(2026, 10, 4);
const daysSince = iso => (iso ? Math.round((today - Date.parse(`${iso}T00:00:00Z`)) / 86400000) : null);
const staleDays = new Function('daysSince', `${code}; return staleDays;`)(daysSince);

const doc = (frequency, fetched, updated, extra = {}) => ({frequency, fetched, updated, ...extra});
assert.equal(staleDays(doc('daily', '2026-10-28', '2026-10-27')), 7, '일간은 3일이 넘으면 지연');
assert.equal(staleDays(doc('daily', '2026-11-03', '2026-11-03')), null, '최근 수집은 지연 아님');
assert.equal(staleDays(doc('quarterly', '2026-10-25', '2026-09-30')), null, '새 공시 전 분기 카드는 지연 아님');
assert.equal(staleDays(doc('quarterly', '2026-10-25', '2026-06-30')), null, '공시 기간(137일) 안이면 지연 아님');
assert.equal(staleDays(doc('quarterly', '2026-10-25', '2026-03-31')), 10, '다음 분기 공시 시한을 넘기면 지연');
assert.equal(staleDays(doc('yearly', '2026-10-25', '2025-12-31')), null, '연간은 다음 해 공시 전이면 지연 아님');
assert.equal(staleDays(doc('yearly', '2026-10-25', '2025-03-31')), 10, '연간도 시한을 넘기면 지연');
assert.equal(staleDays(doc('quarterly', '2026-10-25', '2026-09-30', {stale_days: 5})), 10, '명시한 stale_days가 우선');
assert.equal(staleDays(doc('weekly', '2026-09-18', '2026-09-18', {stale_days: 10})), 47, '주간 위클리');
assert.equal(staleDays(doc('quarterly', '2026-01-01', '2026-01-01', {manual: true})), null, '수기 자료는 제외');
console.log('stale rule OK');
