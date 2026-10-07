const fs = require('node:fs');
const assert = require('node:assert/strict');
const vm = require('node:vm');
class Element {
  constructor() { this.children=[]; this.style={}; this.classList={toggle(){}}; }
  appendChild(child) { this.children.push(child); return child; }
  append(...children) { this.children.push(...children); }
  setAttribute() {}
  insertBefore(child) { this.children.unshift(child); }
  addEventListener() {}
  querySelector(selector) { this.selectors??={}; return this.selectors[selector]??=new Element(); }
}
const charts=[];
class Chart {
  constructor(canvas, config) { this.data=config.data; this.options=config.options; charts.push(this); }
  setDatasetVisibility() {} isDatasetVisible() { return true; } update() {} destroy() {}
}
const context=vm.createContext({document:{createElement:()=>new Element(),createTextNode:text=>text}, Chart,
  state:{charts:[]}, SERIES_COLORS:{light:['blue','green']}, isDark:()=>false, css:()=>'#000',
  staleDays:()=>null, daysSince:()=>0, rangeCutoff:()=>'0000-00-00'});
const source=fs.readFileSync('assets/app.js','utf8');
vm.runInContext(source.slice(source.indexOf('function renderCard('),source.indexOf('// ── 수주 테이블')), context);
const catalog=JSON.parse(fs.readFileSync('data/catalog.json','utf8'));
const ess=catalog.industries.find(i=>i.id==='ess');
const companies=ess.sections.flatMap(s=>s.companies||[]);
assert(ess.sections.every(s=>Array.isArray(s.indicators)));
assert.equal(companies.length,3);
assert.equal(ess.sections.flatMap(s=>s.indicators||[]).length,5);
assert.equal(companies.flatMap(c=>c.indicators).length,18);
let unavailable=0;
for (const company of companies) {
  for (const id of company.indicators) {
    const doc=JSON.parse(fs.readFileSync(`data/ess/${id}.json`,'utf8'));
    assert.equal(doc.id,id);
    assert(!doc.name.includes('??'));
    assert(doc.source_url.startsWith('https://'));
    if (doc.disclosure_status) {
      unavailable++;
      assert(context.renderCard(doc,id).innerHTML.includes('미공개'));
      continue;
    }
    for (const variant of [doc,...Object.values(doc.series_views||{}).map(v=>({...doc,...v,series_views:undefined}))]) {
      variant.series_views=undefined;
      const card=context.renderCard(variant,id);
      const stat=card.children.find(c=>c.className==='card-stat');
      assert(stat.innerHTML.includes(variant.unit));
      assert(!stat.innerHTML.includes('NaN'));
      for (const points of Object.values(variant.series)) {
        assert.deepEqual(points.map(p=>p[0]),[...new Set(points.map(p=>p[0]))].sort());
        assert(points.every(p=>p[1]==null||Number.isFinite(p[1])));
      }
      assert.equal(charts.at(-1).data.datasets[0].spanGaps,false);
      if (variant.fiscal_year_end_month===9) assert(stat.innerHTML.includes('FY'));
    }
  }
}
assert.equal(unavailable,4);
for (const [date,label] of [['2025-12-31','FY2026 Q1'],['2026-03-31','FY2026 Q2'],['2026-06-30','FY2026 Q3'],['2026-09-30','FY2026 Q4']]) {
  assert.equal(context.periodLabel({quarter_labels:true,fiscal_year_end_month:9},date),label);
}
assert.equal(context.periodLabel({year_labels:true,fiscal_year_end_month:9},'2025-09-30'),'FY2025');
assert.equal(context.periodLabel({frequency:'semiannual'},'2026-06-30'),'2026 상반기');
const bound={name:'test',frequency:'quarterly',quarter_labels:true,company_kpi:true,change_mode:'none',unit:'GWh',source:'test',
  series:{test:[['2026-06-30',2]]},value_qualifiers:{'2026-06-30':'lower_bound'}};
assert(context.renderCard(bound,'test').children.find(c=>c.className==='card-stat').innerHTML.includes('> 2'));
assert(context.buildTable(bound,bound.series).includes('> 2'));
assert.equal(charts.at(-1).options.plugins.tooltip.callbacks.label({dataset:{label:'test'},label:'2026-06-30',parsed:{y:2}}),' test: > 2 GWh');
console.log('PASS: 18 ESS company cards, 4 explicit disclosure gaps, fiscal/half-year labels, views, units and bound formatting');
