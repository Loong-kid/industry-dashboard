const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
class Element {
 constructor(tag){this.tagName=tag;this.children=[];this.listeners={};this.style={};this.dataset={};this.classList={toggle(){}};}
 appendChild(el){this.children.push(el);return el;}
 append(...els){this.children.push(...els);}
 setAttribute(k,v){this[k]=v;}
 addEventListener(k,v){this.listeners[k]=v;}
 replaceChildren(...els){this.children=els;}
}
const context=vm.createContext({document:{createElement:t=>new Element(t)},URL,console});
vm.runInContext(fs.readFileSync('assets/offshore-drilling.js','utf8'),context);
const doc=JSON.parse(fs.readFileSync('data/offshore/offshore_fleet.json','utf8'));
const base={company:'',type:'',location:'',status:'',search:'',favorites:false,showRetired:false};
const rows=context.ofFiltered(doc.rows,base,new Set());
assert(rows.length<doc.rows.length);assert(rows.every(r=>!r.retired && r.status!=='매각 대기'));
const q=context.ofFiltered(doc.rows,{...base,search:'Deepwater Atlas'},new Set());assert.equal(q.length,1);
assert.equal(context.ofFiltered(doc.rows,{...base,company:'borr'},new Set()).filter(r=>r.ownership_kind==='joint_venture').length,5);
assert.equal(context.ofFiltered(doc.rows,{...base,favorites:true},new Set([q[0].id])).length,1);
assert.equal(context.ofNum(null),'—');assert.equal(context.ofNum(0),'0');
assert.equal(context.ofDate({min:'2029-07-01',precision:'quarter',text:'Q3-29'}),'2029 Q3');
assert.equal(context.ofLocation('USGOM'),context.ofLocation('Gulf of America'));
assert.equal(context.ofLink('javascript:alert(1)','bad').tagName,'span');
assert.equal(context.ofLink('https://example.com/','source').rel,'noopener noreferrer');
const market=JSON.parse(fs.readFileSync('data/offshore/offshore_market.json','utf8'));
assert(context.renderOffshoreMarket(market).children.length>5);
assert(context.renderOffshoreOverview(doc).children.length>3);
const source=fs.readFileSync('assets/app.js','utf8'),index=fs.readFileSync('index.html','utf8');
assert(source.includes('"natgas", "offshore", "shipbuilding"'));
for(const renderer of ['renderOffshoreOverview','renderOffshoreMarket','renderOffshoreFleet','renderOffshoreFinancials'])assert(source.includes(renderer));
assert(index.indexOf('assets/offshore-drilling.js')<index.indexOf('assets/app.js'));
assert(index.includes('assets/offshore-drilling.css'));
console.log('PASS: offshore routes, source text/links, date precision, unknown/zero, ownership/JV, filters and favorites');
