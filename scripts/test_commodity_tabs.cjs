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
  'renderFootStatus', 'setRange', 'renderMineralSupply', renderCode + '\n' + routeCode + '\nreturn {route, renderIndustry};')(
  state, document, {}, location, async (industry, id) => {loaded.push(id); return {name:id, updated:'2026-10-01'};},
  () => new Element(), () => null, () => {}, () => {}, () => new Element());
(async () => {
  api.route();
  await api.renderIndustry();
  assert.equal(state.subtab, 'copper');
  assert(loaded.includes('comm_copper_total_inventory'));
  assert(loaded.every(id => id.startsWith('comm_copper') || id.startsWith('comm_komis_copper') || id === 'comm_mineral_supply'));
  assert(loaded.includes('comm_komis_copper_501') && loaded.includes('comm_mineral_supply'));
  loaded.length = 0;
  location.hash = '#/commodities/unknown';
  api.route();
  await api.renderIndustry();
  assert.equal(state.subtab, 'normal');
  assert(!loaded.some(id => id.startsWith('comm_copper')));
  assert(loaded.includes('comm_gold'));
  for (const tab of ['normal', 'copper', 'rare_earth']) {
    loaded.length = 0;
    location.hash = '#/commodities/' + tab;
    api.route();
    await api.renderIndustry();
    assert.equal(state.subtab, tab);
    const expected = catalog.industries.find(i => i.id === 'commodities').sections
      .filter(section => section.tab === tab).flatMap(section => [...section.indicators, ...(section.minerals?.length ? ['comm_mineral_supply'] : []), ...(section.minerals?.includes('MNRL0008') ? ['comm_copper_world_supply'] : [])]);
    assert.deepEqual([...new Set(loaded)], [...new Set(expected)], 'Each tab must load only its own prices and supply');
    assert(expected.length > 0);
    assert(elements.get('content').children.some(child => child.className === 'tab-description'));
  }
  const aliases = {overview:'normal', komis_base:'normal', komis_minor:'rare_earth', komis_energy:'normal', komis_other:'normal', mineral_supply:'copper'};
  for (const [old, target] of Object.entries(aliases)) {
    location.hash = '#/commodities/' + old;
    api.route();
    await api.renderIndustry();
    assert.equal(state.subtab, target, 'Old deep links should remain usable');
  }
  const commodity = catalog.industries.find(i => i.id === 'commodities');
  assert(commodity.sections.every(s => commodity.tabs.some(t => t.id === s.tab)));
  for (const section of commodity.sections) for (const id of section.indicators)
    assert(fs.existsSync(`data/commodities/${id}.json`));
  console.log('PASS: three commodity tabs, old deep links, normal fallback, descriptions, mineral/price isolation and data paths');
})().catch(e => { console.error(e); process.exitCode = 1; });
