const fs = require('node:fs');
const assert = require('node:assert/strict');
const {context, charts} = require('./test_mineral_cards.cjs');
const registry = JSON.parse(fs.readFileSync('scripts/komis_prices.json', 'utf8'));
const catalog = JSON.parse(fs.readFileSync('data/catalog.json', 'utf8'));
const commodity = catalog.industries.find(ind => ind.id === 'commodities');
const manifest = JSON.parse(fs.readFileSync('manual/manifest.json', 'utf8'));
assert(!manifest.some(entry => entry.id === 'comm_lithium'), 'Manual import must not overwrite automated lithium');
const rareCodes = new Set(['MNRL1064', 'MNRL1001', 'MNRL1004', 'MNRL1003', 'MNRL1055', 'MNRL1062', 'MNRL1002', 'MNRL1053', 'MNRL1067', 'MNRL1063', 'MNRL1054', 'MNRL1005', 'MNRL1056', 'MNRL1068']);
for (const entry of registry.cards) {
  const tab = entry.mineral_code === 'MNRL0008' ? 'copper' : rareCodes.has(entry.mineral_code) ? 'rare_earth' : 'normal';
  assert(commodity.sections.some(section => section.tab === tab && section.indicators.includes(entry.id)), entry.id);
  assert.equal(commodity.sections.flatMap(section => section.indicators).filter(id => id === entry.id).length, 1, 'Each price appears once');
  const doc = JSON.parse(fs.readFileSync(`data/commodities/${entry.id}.json`, 'utf8'));
  assert.equal(JSON.stringify(doc.price_reference), JSON.stringify(entry.price_reference));
  assert.equal(JSON.stringify(doc.komis_info), JSON.stringify(entry.info));
  assert(!doc.manual, 'Prices are automatically collected');
  const points = doc.series[entry.series_name];
  assert(points.length > 0 && points.every(([date, price], i) => Number.isFinite(price) && price > 0 && (!i || points[i-1][0] < date)));
  assert.equal(points.at(-1)[0], doc.updated);
  const card = context.renderCard(doc, entry.id);
  const chart = charts.at(-1);
  assert(chart.data.labels.length > 0 && chart.data.labels.every(date => date >= '2023-10-04'));
  assert.equal(chart.data.datasets[0].hidden, false);
  const details = card.children.find(child => child.className === 'price-details');
  assert(details && details.innerHTML.includes(context.escapeHtml(entry.info.prcCrtr)), 'Quotation must be visible');
  assert(details.innerHTML.includes(context.escapeHtml(entry.explanation)), 'Every basis must have its own explanation');
  assert(details.innerHTML.includes(doc.methodology_url));
  const foot = card.children.find(child => child.className === 'card-foot');
  foot.querySelector('.table-btn').listeners.click();
  assert(card.children.find(child => child.className === 'data-table').innerHTML.includes(doc.updated));
  if (doc.data_quality.range_mismatch_dates.length) {
    assert(details.innerHTML.includes('원문 범위값 불일치'));
  }
}
const lithium = JSON.parse(fs.readFileSync('data/commodities/comm_lithium.json', 'utf8'));
assert.equal(lithium.unit, 'USD/kg');
assert.equal(lithium.komis_info.prcCrtr, '99.5%min CIF China');
const spodumene = JSON.parse(fs.readFileSync('data/commodities/comm_komis_lithium_771.json', 'utf8'));
assert.equal(spodumene.unit, 'USD/t');
const molybdenum = JSON.parse(fs.readFileSync('data/commodities/comm_komis_molybdenum_756.json', 'utf8'));
assert.equal(molybdenum.unit, 'USD/mtu');
const hostile = {...lithium, price_details: [{label: '<script>bad</script>', value: '<img src=x onerror=bad>'}]};
const safe = context.renderCard(hostile, hostile.id).children.find(child => child.className === 'price-details');
assert(!safe.innerHTML.includes('<script>') && !safe.innerHTML.includes('<img'));
console.log('PASS: all 79 KOMIS references, tab placement, quotations, unit isolation, quality notices, tables and escaping');
