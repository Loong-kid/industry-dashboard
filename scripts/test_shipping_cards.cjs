const fs = require('node:fs');
const assert = require('node:assert/strict');
const {context, charts} = require('./test_mineral_cards.cjs');
context.daysSince = date => (Date.parse('2026-10-04') - Date.parse(date)) / 86400000;
for (const id of ['kcci', 'kdci', 'scfi', 'ccfi', 'bdi', 'bdti', 'bcti', 'hrci']) {
  const doc = JSON.parse(fs.readFileSync(`data/shipping/${id}.json`, 'utf8'));
  const points = Object.values(doc.series).flat();
  assert.equal(doc.updated, points.map(([date]) => date).sort().at(-1), 'Source date must not be replaced by fetch date');
  assert(points.every(([date, value]) => date <= doc.fetched && Number.isFinite(value) && value > 0));
  const card = context.renderCard(doc, id);
  assert(card.children.find(child => child.className === 'card-stat').innerHTML.includes(doc.updated));
  if (id === 'hrci') {
    assert(card.children.some(child => child.className === 'card-empty is-error' && child.textContent.includes('2025-06-04')), 'Stale publisher data must remain visibly old even after a successful fetch');
  } else {
    assert(!card.children.some(child => child.className === 'card-empty is-error'));
  }
  if (id === 'bdi') assert.equal(doc.frequency, 'daily');
  if (['bdi', 'bdti', 'bcti'].includes(id)) assert.equal(typeof charts.at(-1).data.datasets[0].segment.borderDash, 'function', 'Long collection gaps must be visibly distinguished');
}
console.log('PASS: shipping source dates, fresh index data, daily BDI, long gaps and stale HRCI notice');
