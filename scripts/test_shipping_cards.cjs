const fs = require('node:fs');
const assert = require('node:assert/strict');
const {context, charts} = require('./test_mineral_cards.cjs');
context.daysSince = date => (Date.parse('2026-10-04') - Date.parse(date)) / 86400000;
const starts = {kcci: '2022-11-07', kdci: '2013-06-28', scfi: '2014-06-05', ccfi: '2014-06-05', bdi: '2014-06-05', bdti: '2021-12-07', bcti: '2021-12-07', hrci: '2002-01-02', harpex: '2024-10-04'};
assert.equal(JSON.parse(fs.readFileSync('data/catalog.json', 'utf8')).industries.find(i => i.id === 'shipping').default_range, 'all');
context.state.range = 'all';
for (const id of Object.keys(starts)) {
  const doc = JSON.parse(fs.readFileSync(`data/shipping/${id}.json`, 'utf8'));
  const points = Object.values(doc.series).flat();
  assert.equal(points.map(([date]) => date).sort()[0], starts[id], 'Historical backfill start');
  for (const series of Object.values(doc.series)) assert.equal(series.length, new Set(series.map(([date]) => date)).size, 'Duplicate dates');
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
  if (id === 'harpex') {
    assert(doc.note.includes('HRCI') && doc.note.includes('별도 지수'));
    assert(doc.series.HARPEX.length >= 105);
    assert.equal(charts.at(-1).data.datasets[0].data.length, doc.series.HARPEX.length);
  }
  if (['bdi', 'bdti', 'bcti'].includes(id)) assert.equal(typeof charts.at(-1).data.datasets[0].segment.borderDash, 'function', 'Long collection gaps must be visibly distinguished');
}
console.log('PASS: shipping source dates, fresh index data, daily BDI, long gaps and stale HRCI notice');
