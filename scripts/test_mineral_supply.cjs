const fs = require('node:fs');
const assert = require('node:assert/strict');
const {context, charts} = require('./test_mineral_cards.cjs');
const doc = JSON.parse(fs.readFileSync('data/commodities/comm_mineral_supply.json', 'utf8'));
const catalog = JSON.parse(fs.readFileSync('data/catalog.json', 'utf8'));
const commodity = catalog.industries.find(ind => ind.id === 'commodities');
assert(commodity.tabs.some(tab => tab.id === 'mineral_supply'));
assert(commodity.sections.some(section => section.table_kind === 'mineral_supply' && section.indicators.includes(doc.id)));
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
console.log(`PASS: ${available} mineral/product selections, tons, annual gaps, country defaults, history tables, PGM scope and old-data notices`);
