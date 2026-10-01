const fs = require('node:fs');
const assert = require('node:assert/strict');
const source = fs.readFileSync('assets/app.js', 'utf8');
const catalog = JSON.parse(fs.readFileSync('data/catalog.json', 'utf8'));
const state = {catalog, industry: null, subtab: null, charts: [], docErrors: new Map()};
class Element {
  constructor() { this.children = []; this.style = {}; this.dataset = {}; this.classList = {toggle(){}}; }
  set innerHTML(value) { this.children = []; }
  appendChild(child) { this.children.push(child); }
  setAttribute() {}
  remove() {}
}
const elements = new Map();
const document = {createElement: () => new Element(), querySelectorAll: () => [],
  getElementById: (id) => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); },
  querySelector: () => new Element()};
const location = {hash: '#/commodities/copper'};
const loaded = [];
const renderCode = source.slice(source.indexOf('let renderSeq = 0;'), source.indexOf('\nfunction renderFootStatus'));
const routeCode = source.slice(source.indexOf('function route()'), source.indexOf('\nfunction setRange'));
const api = new Function('state', 'document', 'window', 'location', 'loadDoc', 'renderCard', 'staleDays',
  'renderFootStatus', 'setRange', renderCode + routeCode + '\nreturn {route, renderIndustry};')(
  state, document, {}, location, async (industry, id) => {loaded.push(id); return {name:id, updated:'2026-10-01'};},
  () => new Element(), () => null, () => {}, () => {});
(async () => {
  api.route();
  await api.renderIndustry();
  assert.equal(state.subtab, 'copper');
  assert(loaded.includes('comm_copper_total_inventory'));
  assert(loaded.every(id => id.startsWith('comm_copper')));
  loaded.length = 0;
  location.hash = '#/commodities/unknown';
  api.route();
  await api.renderIndustry();
  assert.equal(state.subtab, 'overview');
  assert(!loaded.some(id => id.startsWith('comm_copper')));
  assert(loaded.includes('comm_gold'));
  const commodity = catalog.industries.find(i => i.id === 'commodities');
  assert(commodity.sections.every(s => commodity.tabs.some(t => t.id === s.tab)));
  for (const section of commodity.sections) for (const id of section.indicators)
    assert(fs.existsSync(`data/commodities/${id}.json`));
  console.log('PASS: copper deep link, overview fallback, section isolation and data paths');
})().catch(e => { console.error(e); process.exitCode = 1; });
