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
  constructor(canvas,config) { this.data=config.data;this.options=config.options;this.type=config.type;charts.push(this); }
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
  assert(chart.data.datasets.every(ds=>ds.isReference||ds.spanGaps===(doc.bridge_missing_january ? true : false)));
  assert(!root.children[0].children.find(c=>c.className==='card-stat').innerHTML.includes('NaN'));
  assert(doc.updated<=doc.fetched);
  if(id==='comm_copper_us_construction_spending') {
    for(const points of Object.values(doc.series)) {
      assert.equal(points[0][0],'2002-01-31');
      assert(points.every(([,value])=>value>0),'Census zero placeholders must not appear as spending');
    }
  }
  for(const points of Object.values(doc.series)) {
    assert(points.every(([date,value])=>Number.isFinite(value)&&date<=doc.fetched));
    assert.equal(new Set(points.map(p=>p[0])).size,points.length);
  }
  if(doc.cumulative) {
    const january=chart.data.labels.indexOf('2026-01-31');
    assert(january>=0&&chart.data.datasets.every(ds=>ds.data[january]===null));
    assert(root.children[0].children.find(c=>c.className==='card-stat').innerHTML.includes('1~8월 누적'));
    const dataset=chart.data.datasets[0];
    const bridge={p0DataIndex:chart.data.labels.indexOf('2025-12-31'),p1DataIndex:chart.data.labels.indexOf('2026-02-28')};
    assert.equal(JSON.stringify(dataset.segment.borderDash(bridge)),JSON.stringify([5,4]));
    assert.equal(dataset.segment.borderColor(bridge),undefined);
    const skipped={p0DataIndex:bridge.p0DataIndex,p1DataIndex:january};
    assert.equal(JSON.stringify(dataset.segment.borderDash(skipped)),JSON.stringify([5,4]),'Chart.js visits skipped January points too');
    const longGap={p0DataIndex:0,p1DataIndex:6};
    assert.equal(dataset.segment.borderColor(longGap),'transparent','Other missing intervals stay disconnected');
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
    if(id==='comm_copper_us_housing') {
      for(const key of ['ytd','total']) {
        const view=doc.series_views[key];
        const controls=root.children[0].children.find(c=>c.className==='series-view-controls');
        controls.children[Object.keys(doc.series_views).indexOf(key)].listeners.click();
        const active=charts.at(-1);
        assert.equal(active.type,'line');
        assert.equal(active.data.datasets.length,3);
        assert(active.data.datasets.every(ds=>!ds.hidden));
        assert.equal(context.state.charts.length,baseline);
        const headline=root.children[0].children.find(c=>c.className==='card-stat').innerHTML;
        assert(headline.includes('천 호')&&!headline.includes('천 호/년'));
        assert(headline.includes(key==='ytd'?'1~8월 누적':'1968년부터 누적'));
        const display={...doc,...view};
        assert(context.buildTable(display,view.series).includes(context.fmt(view.series[Object.keys(view.series)[0]].at(-1)[1])));
      }
    }
    if(doc.cumulative) {
      for(const [key,view] of Object.entries(doc.series_views)) {
        const controls=root.children[0].children.find(c=>c.className==='series-view-controls');
        controls.children[Object.keys(doc.series_views).indexOf(key)].listeners.click();
        const active=charts.at(-1);
        assert.equal(context.state.charts.length,baseline);
        const headline=root.children[0].children.find(c=>c.className==='card-stat').innerHTML;
        assert(headline.includes(view.unit));
        assert.equal(view.unit,key==='yoy' ? '%' : id.endsWith('_investment') ? '십억 위안' : '백만㎡');
        if(key==='monthly'||key==='monthly_line') {
          assert.equal(active.type,key==='monthly'?'bar':'line');
          assert.deepEqual(view.series,doc.series_views.monthly.series,'Monthly line and bars display the same quantities');
          assert.deepEqual(view.point_annotations,doc.series_views.monthly.point_annotations);
          assert(!headline.includes('1~8월 누적'));
          const display={...doc,...view};
          assert(context.buildTable(display,view.series).includes('추정'));
          const text=active.options.plugins.tooltip.callbacks.label({dataset:{label:'monthly'},parsed:{y:1},label:'2026-01-31'});
          assert(text.includes('추정'));
        }
        if(key==='total') {
          assert(headline.includes(`${view.cumulative_since}년부터 누적`));
          assert.equal(active.data.datasets[0].data[active.data.labels.indexOf('2026-01-31')],null);
        }
      }
    }
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
