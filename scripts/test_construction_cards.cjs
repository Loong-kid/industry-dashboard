const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync('assets/app.js', 'utf8');
class Element {
  constructor(tag) { this.tag=tag; this.children=[]; this.innerHTML=''; this.textContent=''; this.style={}; this.listeners={}; this.attributes={}; this.classList={toggle(){}}; }
  appendChild(child) { this.children.push(child); if (typeof child==='object') child.parent=this; return child; }
  append(...children) { children.forEach(child=>this.appendChild(child)); }
  setAttribute(name,value) { this.attributes[name]=value; }
  addEventListener(event,callback) { this.listeners[event]=callback; }
  querySelector(selector) { this.selectors??={}; return this.selectors[selector]??=new Element(selector); }
  insertBefore(child,target) { const i=this.children.indexOf(target); this.children.splice(i<0?this.children.length:i,0,child);child.parent=this; }
  replaceWith(other) { const i=this.parent.children.indexOf(this);this.parent.children[i]=other;other.parent=this.parent; }
}
const charts=[];
class Chart {
  constructor(canvas,config) { this.data=config.data;this.options=config.options;charts.push(this); }
  setDatasetVisibility(i,v) { this.data.datasets[i].hidden=!v; }
  isDatasetVisible(i) { return !this.data.datasets[i].hidden; }
  update() {}
  destroy() { this.destroyed=true; }
}
const context=vm.createContext({document:{createElement:tag=>new Element(tag),createTextNode:text=>text},
  Chart,state:{charts:[]},SERIES_COLORS:{light:['blue','green','red']},isDark:()=>false,css:()=>'#000',
  staleDays:()=>null,daysSince:()=>0,rangeCutoff:()=>'0000-00-00'});
vm.runInContext(source.slice(source.indexOf('function renderCard('),source.indexOf('// ── 수주 테이블')),context);
const catalog=JSON.parse(fs.readFileSync('data/catalog.json','utf8'));
const copper=catalog.industries.find(ind=>ind.id==='commodities');
const ids=copper.sections.filter(section=>section.tab==='copper').flatMap(section=>section.indicators)
  .filter(id=>/^comm_copper_(cn_|us_)/.test(id));
assert.equal(ids.length,7);
for(const id of ids) {
  const doc=JSON.parse(fs.readFileSync(`data/commodities/${id}.json`,'utf8'));
  const root=new Element('root');root.appendChild(context.renderCard(doc,id));
  const chart=charts.at(-1);
  assert(chart.data.labels.length>60);
  assert(chart.data.datasets.every(ds=>ds.isReference||ds.spanGaps===false));
  assert(!root.children[0].children.find(c=>c.className==='card-stat').innerHTML.includes('NaN'));
  assert(doc.updated<=doc.fetched);
  for(const points of Object.values(doc.series)) {
    assert(points.every(([date,value])=>Number.isFinite(value)&&date<=doc.fetched));
    assert.equal(new Set(points.map(p=>p[0])).size,points.length);
  }
  if(doc.cumulative) {
    const january=chart.data.labels.indexOf('2026-01-31');
    assert(january>=0&&chart.data.datasets.every(ds=>ds.data[january]===null));
    assert(root.children[0].children.find(c=>c.className==='card-stat').innerHTML.includes('1~8월 누적'));
  }
  if(doc.series_views) {
    const baseline=context.state.charts.length;
    const controls=root.children[0].children.find(c=>c.className==='series-view-controls');
    controls.children[1].listeners.click();
    assert(chart.destroyed,'Switching views destroys the replaced chart');
    assert.equal(context.state.charts.length,baseline,'View switches must not leak chart instances');
    const newDoc=doc.series_views[Object.keys(doc.series_views)[1]];
    const stat=root.children[0].children.find(c=>c.className==='card-stat');
    assert(stat.innerHTML.includes(newDoc.unit));
    const foot=root.children[0].children.find(c=>c.className==='card-foot');
    foot.querySelector('.table-btn').listeners.click();
    const table=root.children[0].children.find(c=>c.className==='data-table');
    assert(table.innerHTML.includes(doc.updated.slice(0,7)));
    const label=Object.keys(newDoc.series)[0];
    assert(table.innerHTML.includes(context.fmt(newDoc.series[label].at(-1)[1])),'Table values follow selected view');
  } else {
    const reference=chart.data.datasets.find(ds=>ds.isReference);
    assert(reference&&reference.data.every(v=>v===50));
    assert.equal(root.children[0].children.find(c=>c.className==='chips').children.length,2,'Reference line is not a headline series');
    const stat=root.children[0].children.find(c=>c.className==='card-stat');
    assert(stat.innerHTML.includes('p · 전월 대비')&&!stat.innerHTML.includes('(+'),'PMI changes use points, not relative percentages');
    assert(context.buildTable(doc,doc.series).includes('NBS 2026-09'));
  }
}
console.log('PASS: seven construction cards, physical/growth views, chart cleanup, matching tables, source links, missing January and PMI reference/point changes');
