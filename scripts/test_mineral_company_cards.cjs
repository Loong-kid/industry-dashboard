const fs = require('node:fs');
const assert = require('node:assert/strict');
const vm = require('node:vm');
class Element {
  constructor() { this.children=[];this.style={};this.listeners={};this.classList={toggle(){}}; }
  appendChild(child) { this.children.push(child);return child; }
  append(...children) { this.children.push(...children); }
  setAttribute() {}
  insertBefore(child, target) { const index=this.children.indexOf(target);this.children.splice(index<0?this.children.length:index,0,child); }
  addEventListener(event, callback) { this.listeners[event]=callback; }
  querySelector(selector) { this.selectors??={};return this.selectors[selector]??=new Element(); }
}
const charts=[];
class Chart {
  constructor(canvas, config) { this.data=config.data;this.options=config.options;charts.push(this); }
  setDatasetVisibility(index, visible) { this.data.datasets[index].hidden=!visible; }
  isDatasetVisible(index) { return !this.data.datasets[index].hidden; }
  update() {}
  destroy() {}
}
const context=vm.createContext({document:{createElement:()=>new Element(),createTextNode:text=>text},Chart,
  state:{charts:[]},SERIES_COLORS:{light:['blue','green']},isDark:()=>false,css:()=>'#000',
  staleDays:()=>null,daysSince:()=>0,rangeCutoff:()=>'0000-00-00'});
const source=fs.readFileSync('assets/app.js','utf8');
vm.runInContext(source.slice(source.indexOf('function renderCard('),source.indexOf('// ── 수주 테이블')),context);
const catalog = JSON.parse(fs.readFileSync('data/catalog.json', 'utf8'));
const sections = catalog.industries.find(i => i.id === 'commodities').sections;
const companies = sections.flatMap(s => (s.companies || []).map(c => ({...c, tab: s.tab})));
assert.equal(companies.length, 6);
assert.deepEqual(companies.filter(c => c.tab === 'copper').map(c => c.id), ['fcx', 'scco']);
assert.deepEqual(companies.filter(c => c.tab === 'rare_earth').map(c => c.id), ['mp']);
for (const company of companies) {
  assert.equal(company.indicators.length, 3);
  for (const id of company.indicators) {
    const doc = JSON.parse(fs.readFileSync(`data/commodities/${id}.json`, 'utf8'));
    assert.equal(doc.id, id);
    const card = context.renderCard(doc, id);
    const stat = card.children.find(c => c.className === 'card-stat');
    assert(stat.innerHTML.includes(doc.unit));
    assert(!stat.innerHTML.includes('NaN'));
    assert(charts.at(-1).data.labels.length > 1);
    for (const points of Object.values(doc.series)) {
      assert.deepEqual(points.map(p => p[0]), [...new Set(points.map(p => p[0]))].sort());
      assert(points.every(p => p[1] == null || Number.isFinite(p[1])));
    }
    if (id.endsWith('_price')) assert.equal(doc.unit, 'USD/주');
    else {
      assert.equal(doc.default_view, 'quarter');
      assert(doc.series_views.annual);
      assert(stat.innerHTML.includes('YoY') && stat.innerHTML.includes('QoQ'));
      assert.equal(charts.at(-1).data.datasets[0].spanGaps, false);
      const annual = {...doc, ...doc.series_views.annual, series_views: undefined};
      const annualCard = context.renderCard(annual, id);
      const annualStat = annualCard.children.find(c => c.className === 'card-stat');
      assert(!annualStat.innerHTML.includes('QoQ'));
      assert(charts.at(-1).data.labels.every(date => date.endsWith('-12-31')));
    }
  }
}
const profit = JSON.parse(fs.readFileSync('data/commodities/comm_company_mp_profit.json', 'utf8'));
function transition(base, current) {
  const doc = {...profit, default_series: ['profit'], series: {profit: [['2025-06-30', base], ['2026-03-31', base], ['2026-06-30', current]]}, series_views: undefined};
  return context.renderCard(doc, 'fixture').children.find(c => c.className === 'card-stat').innerHTML;
}
for (const [base, current, label] of [[-20, 5, '흑자전환'], [20, -5, '적자전환'], [-20, -5, '적자축소'], [-5, -20, '적자확대'], [5, 0, '손익분기']]) {
  assert(transition(base, current).includes(label));
}
assert(transition(null, 5).includes('자료 없음'));
assert(transition(5, null).includes('—'));
console.log('PASS: 18 company cards, mineral placement, units, period views, sparse histories and profit transitions');
