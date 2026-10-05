const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
class Element {
  constructor(tag) { this.tag=tag; this.children=[]; this.style={}; this.listeners={}; this.classList={add(){},remove(){},toggle(){}}; }
  set innerHTML(value) { this.html=value; this.children=[]; }
  get innerHTML() { return this.html || ''; }
  append(...children) { this.children.push(...children); }
  appendChild(child) { this.append(child); return child; }
  addEventListener(event, fn) { this.listeners[event]=fn; }
  querySelector(selector) { this.selectors ??= {}; return this.selectors[selector] ??= new Element(selector); }
}
const source=fs.readFileSync('assets/app.js','utf8');
const catalog=JSON.parse(fs.readFileSync('data/catalog.json','utf8'));
assert.equal(catalog.industries.find(i=>i.id==='institution').name,'기관');
assert.deepEqual(catalog.industries.find(i=>i.id==='gifts').sections.map(s=>s.indicators),[['gift_plans'],['gifts']]);
const context=vm.createContext({
  document:{createElement:tag=>new Element(tag),createTextNode:t=>t},
  state:{tableRange:{}},TABLE_RANGE_DEFAULT:'all',cutoffFor:()=>'',
  buildTableRangePicker:()=>new Element('picker'),cycleSortState(){},
  escapeHtml:s=>String(s??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;'),
  Date:class extends Date { constructor(...args){super(...(args.length?args:['2026-10-05T04:00:00+09:00']));} }
});
vm.runInContext(source.slice(source.indexOf('function giftPlanStatus('),source.indexOf('// ── 전력: 현재 가동중 발전설비 구성')),context);
const base={rcept_dt:'2026-10-01',corp_name:'GS',stock_code:'078930',market:'코스피',reporter:'홍길동<img src=x>',position:'회장',holder_type:'대주주',direction:'증여(줌)',gift_shares:500000,before_rate:2.15,after_rate:1.62,rcept_no:'20261001000100',latest_rcept_no:'20261001000100',record_status:'active',plan_start:'2026-11-01',plan_end:'2026-11-30',counterparty:'김길동',security:'보통주',purpose:'소유주식 증여'};
const plan={id:'gift_plans',name:'주식 증여 / 수증 계획',is_plan:true,source:'DART',source_url:'https://dart.fss.or.kr',note:'기간 종료는 이행 완료가 아닙니다',legal_summary:'법적 설명',legal_sources:[{label:'법령',url:'https://law.go.kr'}],markets:['코스피'],holder_types:['대주주','소액임원'],directions:['증여(줌)','수증(받음)'],plan_statuses:['계획 공시','거래기간 중','기간 경과 / 이행 미확인','철회','정정 전','최신 보고서 확인 필요'],orders:[base,{...base,record_status:'withdrawn',latest_rcept_no:'20261002000100'},{...base,record_status:'superseded'},{...base,record_status:'latest_unverified'},{...base,holder_type:'소액임원'}]};
const walk=(node,tag)=>[...(node.tag===tag?[node]:[]),...node.children.filter(c=>c instanceof Element).flatMap(c=>walk(c,tag))];
const card=context.renderGifts(plan);
const body=walk(card,'tbody')[0];
assert.equal(body.children.length,1,'Hide archive/unverified/small-holder by default');
const headers=walk(card,'th').map(e=>e.textContent);
assert(headers.includes('거래 예정기간')&&headers.includes('예정 수량')&&headers.includes('지분율(현재→계획 후 예상)'));
assert(walk(card,'details')[0].innerHTML.includes('https://law.go.kr'));
assert(body.children[0].children.some(c=>c.innerHTML.includes('&lt;img')),'Escape reporter names');
const statusChips=walk(card,'div').find(e=>e.className==='chips gift-status-filters');
const cancelled=statusChips.children[3].children[0];
cancelled.checked=true;cancelled.listeners.change();
assert.equal(body.children.length,2);
assert(body.children[1].children.some(c=>c.innerHTML.includes('최신 보고')));
const search=walk(card,'div').find(e=>e.className==='order-search').querySelector('input');
search.listeners.input({target:{value:'존재하지 않는 이름'}});assert.equal(body.children.length,0);
search.listeners.input({target:{value:'김길동'}});assert.equal(body.children.length,2);
assert.equal(context.giftPlanStatus(base),'계획 공시');
assert.equal(context.giftPlanStatus({...base,plan_start:'2026-10-05',plan_end:'2026-11-03'}),'거래기간 중');
assert.equal(context.giftPlanStatus({...base,plan_start:'2026-09-01',plan_end:'2026-09-30'}),'기간 경과 / 이행 미확인');
const actual=context.renderGifts({...plan,id:'gifts',is_plan:false,orders:[base]});
assert.equal(walk(actual,'tbody')[0].children.length,1);
assert(!walk(actual,'th').some(e=>e.textContent==='예정 수량'),'Actual gifts keep existing columns');
assert.equal(walk(actual,'details').length,0);
const empty=context.renderGifts({...plan,orders:[]});
assert.equal(walk(empty,'tbody')[0].children.length,0);
assert.equal(walk(empty,'details').length,1,'Zero rows still show legal/coverage information');
console.log('PASS: institution rename, separate plan/actual cards, KST plan status, archives, search, legal sources and escaping');
