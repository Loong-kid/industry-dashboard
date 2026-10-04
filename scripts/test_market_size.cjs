const fs = require('node:fs');
const assert = require('node:assert/strict');
const {context, charts} = require('./test_mineral_cards.cjs');
context.daysSince = date => (Date.parse('2026-10-04') - Date.parse(date)) / 86400000;
const catalog = JSON.parse(fs.readFileSync('data/catalog.json', 'utf8'));
const macro = catalog.industries.find(i => i.id === 'macro');
assert(macro.tabs.some(t => t.id === 'market_size' && t.name === '시장규모'));
const ids = macro.sections.filter(s => s.tab === 'market_size').flatMap(s => s.indicators);
assert.equal(new Set(ids).size, 21);
for (const id of ['market_equity_kr', 'market_kospi', 'market_kosdaq', 'market_equity_cn', 'market_equity_jp',
  'market_equity_uk', 'market_equity_de', 'market_equity_fr', 'market_equity_it', 'market_equity_es', 'market_equity_nl', 'market_equity_ch', 'market_equity_eu_recent']) assert(ids.includes(id));
for (const id of ids) {
  const doc = JSON.parse(fs.readFileSync(`data/macro/${id}.json`, 'utf8'));
  const points = Object.values(doc.series)[0];
  const card = context.renderCard(doc, id);
  const chart = charts.at(-1);
  const axisLength = doc.annual_axis ? Number(points.at(-1)[0].slice(0,4)) - Number(points[0][0].slice(0,4)) + 1 : points.length;
  assert.equal(chart.data.labels.length, axisLength, 'Full history and unpublished annual gaps must remain visible');
  assert.equal(chart.data.datasets[0].data.at(-1), points.at(-1)[1]);
  assert.equal(doc.unit, ['market_kospi','market_kosdaq','market_equity_kr_krw'].includes(id) ? '조 원' : id === 'market_equity_eu_recent' ? '조 유로' : '조 달러');
  assert.equal(doc.updated, points.at(-1)[0], 'Data period must not be replaced by collection date');
  assert(Object.values(doc.series).every(ps => ps.every(([date, value]) => Number.isFinite(value) && value > 0 && date <= doc.fetched)));
  if (doc.annual_axis) assert.equal(chart.data.datasets[0].spanGaps, false);
  if (id === 'market_equity_uk') {
    const missing = chart.data.labels.indexOf('2015-12-31');
    assert.equal(chart.data.datasets[0].data[missing], null, 'Unpublished UK years must not appear as a continuous line');
    assert(card.children.some(c => c.className === 'card-empty is-error'), 'Old national series must be visibly identified');
  }
  if (id === 'market_equity_eu_recent') {
    assert.equal(chart.data.datasets.length, 8);
    assert.equal(chart.data.datasets.filter(d => !d.hidden).length, 5);
    assert.equal(points.length, 2, 'First ESMA release has two real observations, no fabricated history');
  }
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
console.log('PASS: 21 market cards, country coverage, real annual gaps, stale-history notices, ECOS/ESMA units, full history and trading dates');
