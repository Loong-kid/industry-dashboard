const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const overlay=require('../assets/mocvd-capex-overlay.js'),root=path.join(__dirname,'..');
const read=file=>JSON.parse(fs.readFileSync(path.join(root,file),'utf8'));
const guidance=read('data/semicon/mocvd_capex_guidance.json');
const cohr=overlay.attach(read('data/semicon/mocvd_coherent_capex.json'),guidance);
const lite=overlay.attach(read('data/semicon/mocvd_lumentum_capex.json'),guidance);
const view=(doc,key)=>({...doc,...doc.series_views[key],series_views:undefined});
const q=view(cohr,'quarter'),annual=view(cohr,'annual'),lq=view(lite,'quarter');
const before=JSON.stringify(q.series),model=overlay.plan(q,q.series);
assert.equal(model.events.length,9);assert.equal(model.events[0].row.id,'coherent-fy2027-q1');
assert(model.dates.includes('2026-12-31'));assert.equal(model.labels['2026-12-31'],'FY2027 Q2');
assert.equal(overlay.datasets(model,model.dates,['actual','guidance']).length,0);
assert.equal(JSON.stringify(q.series),before);assert.equal(q.series['유형자산 취득 현금지출'].at(-1)[0],'2026-09-30');
assert(model.groups.get('2026-03-31').some(e=>e.row.id==='coherent-fy2026-q2'));
assert(model.groups.get('2026-06-30').some(e=>e.row.id==='coherent-fy2026-q2'));
assert(overlay.plan(q,q.series,{from:'2026-01-01',to:'2026-03-31'}).events.some(e=>e.row.id==='coherent-fy2026-q2'));
const orders=overlay.plan(lq,lq.series).events.find(e=>e.row.id==='lumentum-fy2025-q2');
assert.equal(orders.date,'2025-06-28');assert.equal(orders.quant,false);assert.equal(orders.row.amount_low,null);
const bounded=overlay.plan(q,q.series,{from:'2026-04-01',to:'2026-09-30'});
assert(bounded.events.every(e=>e.date>='2026-04-01'&&e.date<='2026-09-30'&&e.row.announced_at<='2026-09-30'));
assert(!bounded.events.some(e=>e.row.id==='coherent-fy2027-q1'));
assert.equal(overlay.plan(q,q.series,{from:'2000-01-01',to:'2001-01-01'}).events.length,0);
assert.equal(overlay.plan({series:q.series},q.series),null);
assert.equal(overlay.attach({id:'company_asml_capex'},guidance).mocvd_guidance,undefined);
const am=overlay.plan(annual,annual.series);assert.equal(am.events[0].label,'FY2027');
assert(am.dates.every(d=>d.slice(5,7)==='06'));assert.equal(am.ranges.length,0);
const la=view(lite,'annual'),lm=overlay.plan(la,la.series);assert.equal(lm.events.find(e=>e.row.id==='lumentum-fy2025-q2').date,'2025-06-28');
// Synthetic, explicitly reviewed USD cash guidance tests the numeric path.
const source=guidance.rows.find(r=>r.id==='coherent-fy2027-q1');
const budget={...source,guidance_kind:'range',amount_low:800,amount_high:900,basis:'전사 현금 CAPEX'};
const withRow=row=>({...q,mocvd_guidance:{rows:[row]}});
for(const [capex_direction,label] of [['increase_qoq','증가'],['decrease_qoq','감소'],['flat_qoq','유지'],['unknown','방향']]){
 assert(overlay.plan(withRow({...source,capex_direction}),q.series).events[0].short.endsWith(label));
}
const bm=overlay.plan(withRow(budget),q.series),sets=overlay.datasets(bm,['2026-09-30','2026-12-31'],['actual','guidance']);
assert.equal(bm.ranges.length,1);assert.deepEqual(sets.map(s=>s.data),[[null,800],[null,900]]);
assert(sets.every(s=>s.isCapexGuidance&&s.showLine===false&&s.spanGaps===false));assert.deepEqual(sets[0].borderDash,[5,4]);
for(const changes of [{basis:'프로젝트 총투자'},{basis:'InP 전용 CAPEX'},{currency:'CNY'},{amount_unit:'billion'},
 {review_status:'pending'},{amount_low:null},{amount_high:NaN},{amount_low:-1},{amount_high:700},
 {target_start:'2026-07-01'},{target_start:'2026-01-01'}, {target_start:'2026-10-15'}, {target_start:'2026-10-15',target_end:'2027-01-17'}]){
 const m=overlay.plan(withRow({...budget,...changes}),q.series);assert.equal(m.ranges.length,0,JSON.stringify(changes));
}
const fyBudget={...budget,target_start:'2026-07-01',target_end:'2027-06-30',amount_low:3000,amount_high:4000};
assert.equal(overlay.plan(withRow(fyBudget),q.series).ranges.length,0);
assert.equal(overlay.plan({...annual,mocvd_guidance:{rows:[fyBudget]}},annual.series).ranges.length,1);
const unavailable=overlay.attach(read('data/semicon/mocvd_coherent_capex.json'),null);assert(unavailable.mocvd_guidance.unavailable);assert.deepEqual(unavailable.series,cohr.series);

// Exercise the actual app's loader and Chart.js configuration, without a browser dependency.
const app=fs.readFileSync(path.join(root,'assets/app.js'),'utf8');
const loadSource=app.slice(app.indexOf('async function loadDoc('),app.indexOf('// refresh.js가'));
const state={docs:new Map(),docErrors:new Map(),charts:[]};let requests=[];
const fetch=async url=>{requests.push(url);return {ok:true,json:async()=>read(url)};};
const load=new Function('state','fetch','MOCVDCapexOverlay',loadSource+'return loadDoc;')(state,fetch,overlay);
const drawSource=app.slice(app.indexOf('function drawChart('),app.indexOf('// ── 수주 테이블'));
class FakeChart{constructor(canvas,config){this.canvas=canvas;this.config=config;this.data=config.data;this.options=config.options;}isDatasetVisible(){return true;}}
const draw=new Function('SERIES_COLORS','isDark','css','Chart','crosshair','barValueLabels','state','periodLabel','fmt','observationLabel','MOCVDCapexOverlay',drawSource+'return drawChart;')({light:['actual','guidance']},()=>false,t=>t,FakeChart,{}, {},state,(_,date)=>date,String,(_,d,v)=>v,overlay);
const chart=draw({},q,q.series,{from:'2025-01-01',to:'9999-12-31'});
assert(chart.$mocvdModel);assert.equal(chart.data.labels.at(-1),'2026-12-31');
assert.equal(chart.data.datasets[0].data.at(-1),null);assert.equal(chart.options.layout.padding.top,30);
assert(chart.config.plugins.some(p=>p.id==='mocvdCapexGuidance'));
const regular=draw({}, {series:{Actual:[['2026-09-30',10]]}}, {Actual:[['2026-09-30',10]]});
assert.equal(regular.$mocvdModel,undefined);assert.equal(regular.config.plugins.length,1);
const numericChart=draw({},withRow(budget),q.series);assert.equal(numericChart.data.datasets.filter(s=>s.isCapexGuidance).length,2);
// The non-numeric rail uses fixed canvas coordinates, never a fabricated Y value.
global.getComputedStyle=()=>({fontFamily:'inherit'});
for(const width of [280,1100])for(const theme of ['light','dark']){
 const calls=[];const ctx=new Proxy({}, {get:(_,key)=>key==='measureText'?text=>({width:text.length*7}):(...args)=>calls.push([key,...args]),set:()=>true});
 const labels=chart.data.labels,positions=new Map(labels.map((d,i)=>[d,20+i*(width-40)/(labels.length-1)]));
 const fake={ctx,canvas:{},chartArea:{left:20,right:width-20,top:40,bottom:240},data:chart.data,
   scales:{x:{getPixelForValue:i=>positions.get(labels[i])},y:{getPixelForValue:()=>{throw new Error('Qualitative guidance must not resolve a dollar coordinate');}}},isDatasetVisible:()=>true};
 const plugin=overlay.plugin(chart.$mocvdModel,token=>theme+token);plugin.beforeDraw(fake);plugin.afterDraw(fake);
 assert(calls.some(c=>c[0]==='fillRect'));assert(calls.some(c=>c[0]==='fillText'&&c[1].includes('CAPEX')));
 let selected;fake.$mocvdOpen=id=>{selected=id;};plugin.afterEvent(fake,{event:{type:'click',x:positions.get('2026-12-31'),y:25}});
 assert.equal(selected,'coherent-fy2027-q1');
}
delete global.getComputedStyle;

(async()=>{
 const loaded=await load('semicon','mocvd_coherent_capex');assert.equal(loaded.mocvd_guidance.rows.length,9);
 await load('semicon','mocvd_lumentum_capex');await load('semicon','mocvd_coherent_capex');
 assert.equal(requests.filter(s=>s.includes('mocvd_capex_guidance')).length,1);
 const failState={docs:new Map(),docErrors:new Map()};const failFetch=async url=>url.includes('mocvd_capex_guidance')?{ok:false,status:503}:{ok:true,json:async()=>read(url)};
 const failLoad=new Function('state','fetch','MOCVDCapexOverlay',loadSource+'return loadDoc;')(failState,failFetch,overlay);
 const fallback=await failLoad('semicon','mocvd_coherent_capex');assert(fallback.mocvd_guidance.unavailable);assert.deepEqual(fallback.series,cohr.series);
 const html=fs.readFileSync(path.join(root,'index.html'),'utf8');assert(html.indexOf('assets/mocvd-capex-overlay.js')<html.indexOf('assets/app.js'));
 assert(html.indexOf('assets/mocvd-capex-overlay.css')<html.indexOf('assets/theme-mercury.css'));
 console.log('PASS MOCVD CAPEX chart guidance: future axis, fiscal periods, bounded ranges, no invented amounts, annual scope, actual preservation, loader caching and source failure');
})().catch(e=>{console.error(e);process.exit(1)});
