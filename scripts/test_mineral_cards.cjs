// Exercise the actual card, table, chip and chart builders with the new data.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync('assets/app.js', 'utf8');
class Element {
  constructor(tag) {
    this.tag = tag; this.children = []; this.innerHTML = ''; this.textContent = '';
    this.style = {}; this.listeners = {}; this.classList = {toggle() {}};
  }
  appendChild(child) { this.children.push(child); return child; }
  append(...children) { this.children.push(...children); }
  addEventListener(event, callback) { this.listeners[event] = callback; }
  querySelector(selector) {
    this.selectors ??= {};
    return this.selectors[selector] ??= new Element(selector);
  }
}
const charts = [];
class Chart {
  constructor(canvas, config) { this.data = config.data; this.options = config.options; charts.push(this); }
  setDatasetVisibility(index, visible) { this.data.datasets[index].hidden = !visible; }
  isDatasetVisible(index) { return !this.data.datasets[index].hidden; }
  update() {}
}
const context = vm.createContext({
  document: {createElement: tag => new Element(tag), createTextNode: text => text},
  Chart, state: {charts: []}, SERIES_COLORS: {light: ['blue', 'green']},
  isDark: () => false, css: () => '#000', staleDays: () => null,
  daysSince: () => 0, rangeCutoff: () => '2023-10-04',
});
vm.runInContext(source.slice(source.indexOf('function renderCard('), source.indexOf('// ── 수주 테이블')), context);
const catalog = JSON.parse(fs.readFileSync('data/catalog.json', 'utf8'));
const industry = catalog.industries.find(ind => ind.id === 'commodities');
for (const id of ['comm_uranium', 'comm_neodymium', 'comm_dysprosium']) {
  assert(industry.sections.some(section => section.tab === 'overview' && section.indicators.includes(id)), `${id} must appear in 기타 원자재`);
  const doc = JSON.parse(fs.readFileSync(`data/commodities/${id}.json`, 'utf8'));
  const card = context.renderCard(doc, id);
  const chart = charts.at(-1);
  const stat = card.children.find(child => child.className === 'card-stat');
  assert(stat.innerHTML.includes(doc.updated), 'Headline must show data date, not fetch date');
  assert(stat.innerHTML.includes(doc.unit));
  assert(chart.data.labels.length > 10);
  assert(chart.data.labels.every(date => date >= '2023-10-04'), 'Respect selected range');
  assert(card.children.some(child => child.innerHTML?.includes(doc.source_url)), 'Source must be linked');
  const foot = card.children.find(child => child.className === 'card-foot');
  foot.querySelector('.table-btn').listeners.click();
  const table = card.children.find(child => child.className === 'data-table');
  assert.equal(table.style.display, 'block');
  assert(table.innerHTML.includes(doc.updated));
  if (id === 'comm_uranium') {
    assert.equal(chart.data.datasets.length, 2);
    assert(chart.data.datasets.every(dataset => !dataset.hidden), 'Both uranium series visible');
    const chips = card.children.find(child => child.className === 'chips');
    const termCheckbox = chips.children[1].children[0];
    termCheckbox.checked = true;
    termCheckbox.listeners.change();
    assert(stat.innerHTML.includes('장기계약 가격'));
    assert(stat.innerHTML.includes('96.5'));
    assert(table.innerHTML.includes('현물 가격') && table.innerHTML.includes('장기계약 가격'));
  } else {
    assert(card.children.some(child => child.innerHTML?.includes('2026년')));
  }
}
console.log('PASS: mineral card placement, chart ranges, data dates, sources, tables and uranium series toggle');
