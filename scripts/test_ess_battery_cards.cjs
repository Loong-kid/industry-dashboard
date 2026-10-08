const fs=require('node:fs'), assert=require('node:assert/strict'), vm=require('node:vm');
class Element {
  constructor(){this.children=[];this.style={};this.classList={toggle(){}};}
  appendChild(c){this.children.push(c);return c;} append(...c){this.children.push(...c);}
  setAttribute(){} insertBefore(c){this.children.unshift(c);} addEventListener(){}
  querySelector(s){this.selectors??={};return this.selectors[s]??=new Element();}
}
const charts=[];
class Chart {constructor(canvas,config){this.canvas=canvas;this.data=config.data;this.options=config.options;this.config=config;charts.push(this);}
  setDatasetVisibility(){} isDatasetVisible(){return true;} update(){} destroy(){}
}
const ctx=vm.createContext({document:{createElement:()=>new Element(),createTextNode:t=>t},Chart,
  state:{charts:[]},SERIES_COLORS:{light:['blue','green']},isDark:()=>false,css:()=>'#000',
  staleDays:()=>null,daysSince:()=>0,rangeCutoff:()=>'0000-00-00'});
const app=fs.readFileSync('assets/app.js','utf8');
vm.runInContext(app.slice(app.indexOf('function renderCard('),app.indexOf('// ── 수주 테이블')),ctx);
const doc=JSON.parse(fs.readFileSync('data/ess/ess_batteries.json','utf8'));
let views=0;
for(const c of doc.cards) for(const v of Object.values(c.series_views)){
  views++;
  const variant={...c,...v,series_views:undefined,scope_summary:{label:doc.statuses[c.status],text:c.scope,detail:c.note}};
  const el=ctx.renderCard(variant,c.id);
  const stat=el.children.find(x=>x.className==='card-stat');
  assert(stat.innerHTML.includes(c.unit),c.id);
  assert(!stat.innerHTML.includes('NaN'));
  const scope=el.children.find(x=>x.className==='ess-battery-scope');
  assert(scope.innerHTML.includes(c.scope));
  assert.equal(charts.at(-1).data.datasets[0].spanGaps,false);
  assert.equal(charts.at(-1).config.type,v.chart_type);
  const table=ctx.buildTable(variant,variant.series);
  assert(table.includes('https://'),c.id);
  if(Object.keys(v.value_qualifiers).length){assert(stat.innerHTML.includes('> '));assert(table.includes('> '));}
}
assert.equal(doc.cards.length,30);
assert.equal(doc.companies.length,10);
const cat=JSON.parse(fs.readFileSync('data/catalog.json','utf8'));
assert(cat.industries.find(i=>i.id==='ess').sections.some(s=>s.table_kind==='ess_batteries'&&s.indicators.includes(doc.id)));
console.log(`PASS: ${doc.cards.length} battery metrics, ${views} independent period views, scope labels, source tables, bounds and chart types`);
