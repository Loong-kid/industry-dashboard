const fs = require('node:fs');
const assert = require('node:assert/strict');
const {context, charts} = require('./test_mineral_cards.cjs');
const catalog = JSON.parse(fs.readFileSync('data/catalog.json', 'utf8'));
const macro = catalog.industries.find(i => i.id === 'macro');
assert(macro.tabs.some(t => t.id === 'market_size' && t.name === '시장규모'));
const ids = macro.sections.filter(s => s.tab === 'market_size').flatMap(s => s.indicators);
assert.equal(ids.length, 7);
for (const id of ids) {
  const doc = JSON.parse(fs.readFileSync(`data/macro/${id}.json`, 'utf8'));
  const points = doc.series['시장규모'];
  const card = context.renderCard(doc, id);
  const chart = charts.at(-1);
  assert.equal(chart.data.labels.length, points.length, 'Annual and long history must remain visible');
  assert.equal(chart.data.datasets[0].data.at(-1), points.at(-1)[1]);
  assert.equal(doc.unit, '조 달러');
  assert.equal(doc.updated, points.at(-1)[0], 'Data period must not be replaced by collection date');
  assert(points.every(([date, value]) => Number.isFinite(value) && value > 0 && date <= doc.fetched));
  const basis = card.children.find(c => c.tag === 'details');
  assert(basis.innerHTML.includes('집계 기준 자세히'));
  assert(!basis.innerHTML.includes('가격 기준 자세히'));
  const stat = card.children.find(c => c.className === 'card-stat');
  assert(stat.innerHTML.includes(context.periodLabel(doc, doc.updated)));
  const table = context.buildTable(doc, doc.series);
  assert(table.includes(context.periodLabel(doc, points[0][0])), 'Table must include the oldest collected observation');
  assert(table.includes(doc.quarter_labels ? '달력 분기' : '연도'));
  if (id === 'market_sp500_q') {
    const dates = points.map(([date]) => date);
    assert.equal(context.periodLabel(doc, '2025-09-30'), '2025 Q3');
    assert.equal(chart.options.plugins.tooltip.callbacks.afterBody([{label:'2024-06-30'}])[1], '원문 거래일: 2024-06-28');
    assert(dates.every(d => ['03-31', '06-30', '09-30', '12-31'].includes(d.slice(5))));
  } else {
    assert(points.every(([date]) => date.endsWith('12-31')));
  }
}
console.log('PASS: seven market cards, full history, observation dates, basis details, annual/quarter labels, units and actual trading dates');
