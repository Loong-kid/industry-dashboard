const fs = require('node:fs');
const assert = require('node:assert/strict');
const {context, charts} = require('./test_mineral_cards.cjs');
const doc = JSON.parse(fs.readFileSync('data/commodities/comm_mineral_supply.json', 'utf8'));
const catalog = JSON.parse(fs.readFileSync('data/catalog.json', 'utf8'));
const commodity = catalog.industries.find(ind => ind.id === 'commodities');
assert.deepEqual(commodity.tabs.map(tab => tab.name), ['normal', '구리', '희토류']);
const placements = commodity.sections.flatMap(section => section.minerals || []);
assert.equal(placements.length, doc.minerals.length);
assert.equal(new Set(placements).size, placements.length, 'Supply must appear once per product');
assert(doc.minerals.every(mineral => placements.includes(mineral.id)));
assert(commodity.sections.find(section => section.indicators.includes('comm_gold')).minerals.includes('MNRL0046'));
assert(commodity.sections.find(section => section.tab === 'copper' && section.indicators.includes('comm_copper')).minerals.includes('MNRL0008'));
assert(commodity.sections.find(section => section.minerals?.includes('MNRL0006')).tab === 'rare_earth');
let available = 0;
for (const mineral of doc.minerals) {
  if (!mineral.available) continue;
  available++;
  for (const field of ['production', 'reserves']) {
    const data = context.mineralSupplyChart(doc, mineral, field);
    assert.equal(data.unit, '톤');
    assert.equal(data.span_gaps, false);
    if (!Object.keys(data.series).length) continue;
    for (const points of Object.values(data.series)) {
      assert(points.every(([date, value], i) => date.endsWith('-12-31') && value > 0 && Number.isFinite(value) && (!i || points[i-1][0] < date)));
    }
    const card = context.renderCard(data, data.id);
    const oldest = Object.values(data.series).flat().map(point => point[0]).sort()[0];
    assert.equal(charts.at(-1).data.labels[0], oldest, 'Keep the complete available annual history');
    assert(charts.at(-1).data.datasets.filter(d => !d.hidden).length <= 3);
    const foot = card.children.find(child => child.className === 'card-foot');
    foot.querySelector('.table-btn').listeners.click();
    assert(card.children.find(child => child.className === 'data-table').innerHTML.includes(oldest.slice(0, 4)));
  }
}
assert.equal(available, doc.available_count);
const country = (id, code) => doc.minerals.find(m => m.id === id).countries[code];
assert.equal(country('MNRL0008', 'CL').production.at(-1)[1], 5300000);
assert.equal(country('MNRL0024', 'CN').production.at(-1)[1], 900);
assert.equal(country('MNRL0024', 'CN').reserves.length, 0);
assert.equal(country('MNRL0001', 'AU').production.at(-1)[1], 92000);
assert.equal(country('MNRL0014', 'ZA').production.at(-1)[1], 120);
assert(doc.minerals.find(m => m.id === 'MNRL0014').reserve_basis.includes('PGM'));
assert.equal(doc.minerals.find(m => m.id === 'MNRL0035').updated, '2020-12-31');
assert(doc.minerals.find(m => m.id === 'MNRL0017_IM').source_warning);
const copper = doc.minerals.find(mineral => mineral.code === 'MNRL0008');
for (const field of ['production', 'reserves']) {
  const chartDoc = context.mineralSupplyChart(doc, copper, field);
  const totalLabel = '전체 · 공개 국가 합계';
  assert.equal(chartDoc.default_series[0], totalLabel);
  for (const [date, total] of chartDoc.series[totalLabel]) {
    const sum = Object.values(copper.countries).reduce((sum, country) => sum + (country[field].find(point => point[0] === date)?.[1] || 0), 0);
    assert.equal(total, sum);
  }
  assert(chartDoc.note.includes('세계 전체와 다르며'));
  const card = context.renderCard(chartDoc, chartDoc.id);
  assert.equal(charts.at(-1).data.datasets[0].label, totalLabel);
  assert.equal(charts.at(-1).data.datasets[0].hidden, false);
  assert(card.children.find(child => child.className === 'card-stat').innerHTML.includes(totalLabel));
}
assert.equal(context.mineralSupplyTotals(copper, 'production').at(-1)[1], 20013000);
assert.equal(context.mineralSupplyTotals(copper, 'reserves').at(-1)[1], 770200000);
const gaps = {countries: {A:{production:[['2020-12-31',5],['2022-12-31',10]]}, B:{production:[['2020-12-31',2]]}}};
assert.equal(JSON.stringify(context.mineralSupplyTotals(gaps, 'production')), JSON.stringify([['2020-12-31',7],['2022-12-31',10]]));
const world = JSON.parse(fs.readFileSync('data/commodities/comm_copper_world_supply.json', 'utf8'));
for (const field of ['production','reserves']) {
  const chartDoc = context.mineralSupplyChart(doc, copper, field, world);
  assert.equal(chartDoc.default_series[0], '전체 · 세계(USGS)');
  assert.equal(chartDoc.series['전체 · 세계(USGS)'].at(-1)[1], field === 'production' ? 23000000 : 980000000);
  assert(chartDoc.series['전체 · 공개 국가 합계'].at(-1)[1] < chartDoc.series['전체 · 세계(USGS)'].at(-1)[1]);
  assert(chartDoc.point_sources['2025-12-31'].url.includes('mcs2026.pdf#page=77'));
  const card = context.renderCard(chartDoc, chartDoc.id);
  assert.equal(charts.at(-1).data.datasets[0].hidden, false);
  assert.equal(charts.at(-1).data.datasets[1].hidden, true);
  const foot = card.children.find(child => child.className === 'card-foot');
  foot.querySelector('.table-btn').listeners.click();
  assert(card.children.find(child => child.className === 'data-table').innerHTML.includes('세계 전체 · USGS'));
}
console.log(`PASS: ${available} mineral/product selections, unified placement, copper totals, tons, annual gaps, defaults, history, PGM scope and old-data notices`);
