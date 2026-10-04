const fs = require('node:fs');
const assert = require('node:assert/strict');
const {context, charts} = require('./test_mineral_cards.cjs');
for (const id of ['sov_debt_imf', 'sov_debt_usd', 'sov_gdp', 'sov_deficit']) {
  const doc = JSON.parse(fs.readFileSync(`data/macro/${id}.json`, 'utf8'));
  const card = context.renderCard(doc, id);
  const chart = charts.at(-1);
  const labels = chart.data.labels;
  const firstProjection = labels.findIndex(date => date >= doc.forecast_from);
  assert(firstProjection > 1, 'Chart must contain historical and forecast observations');
  assert.equal(chart.data.datasets.length, Object.keys(doc.series).length, 'Country toggles must remain one dataset each');
  for (const dataset of chart.data.datasets) {
    const dash = dataset.segment.borderDash;
    assert.equal(dash({p0DataIndex:firstProjection-2, p1DataIndex:firstProjection-1}), undefined, 'History remains solid');
    assert.equal(JSON.stringify(dash({p0DataIndex:firstProjection-1, p1DataIndex:firstProjection})), '[6,4]', 'Connector into first forecast must be dashed');
    assert.equal(JSON.stringify(dash({p0DataIndex:firstProjection, p1DataIndex:firstProjection+1})), '[6,4]');
  }
  assert(card.children.some(child => child.className === 'forecast-legend' && child.innerHTML.includes('실적·추정') && child.innerHTML.includes('IMF 전망')));
  assert(card.children.find(child => child.className === 'card-stat').innerHTML.includes('전망'));
  const tooltip = chart.options.plugins.tooltip.callbacks.title;
  assert.equal(tooltip([{label:labels[firstProjection-1]}]), labels[firstProjection-1].slice(0,4));
  assert.equal(tooltip([{label:labels[firstProjection]}]), labels[firstProjection].slice(0,4) + ' · IMF 전망');
  const table = context.buildTable(doc, doc.series);
  assert(table.includes('forecast-tag') && table.includes('전망'));
  assert(!table.includes(`${labels[firstProjection-1].slice(0,4)} <span class="forecast-tag">`));
  const chips = card.children.find(child => child.className === 'chips');
  const toggle = chips.children.at(-1).children[0];
  toggle.checked = true;
  toggle.listeners.change();
  assert(card.children.find(child => child.className === 'card-stat').innerHTML.includes('전망'));
  // Selected ranges wholly within the forecast must not restore solid lines.
  const filtered = Object.fromEntries(Object.entries(doc.series).map(([name, points]) => [name,points.filter(([date])=>date>=doc.forecast_from)]));
  const forecastOnly = context.drawChart({},doc,filtered);
  assert.equal(JSON.stringify(forecastOnly.data.datasets[0].segment.borderDash({p0DataIndex:0,p1DataIndex:1})), '[6,4]');
}
for (const id of ['sov_debt_q', 'sov_yield_10y']) {
  const doc = JSON.parse(fs.readFileSync(`data/macro/${id}.json`, 'utf8'));
  const card = context.renderCard(doc, id);
  assert(!doc.forecast_from);
  assert(!card.children.some(child=>child.className==='forecast-legend'));
  assert(charts.at(-1).data.datasets.every(dataset=>dataset.segment===undefined));
}
const sparse = {forecast_from:'2026-01-01',highlight_gaps:true,series:{test:[['2025-01-01',1],['2025-01-15',2],['2026-01-01',3]]}};
const gap = context.drawChart({},sparse,sparse.series).data.datasets[0].segment.borderDash;
assert.equal(JSON.stringify(gap({p0DataIndex:0,p1DataIndex:1})), '[5,5]', 'Historical gap styling remains available');
assert.equal(JSON.stringify(gap({p0DataIndex:1,p1DataIndex:2})), '[6,4]', 'Forecast styling takes precedence');
console.log('PASS: four IMF forecast boundaries, legend, headline, tooltip, tables, toggles, forecast-only ranges and unaffected historical charts');
