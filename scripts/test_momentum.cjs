const assert=require('node:assert/strict');
const fs=require('node:fs');
(async()=>{
  const code=fs.readFileSync('assets/momentum.js','utf8');
  const {percent,quadrant,filterRows,comparisonData}=await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'));
  assert.equal(percent(null),'—');assert.equal(percent(-1.25),'-1.25%');assert.equal(percent(2,'%p'),'+2.00%p');
  const row=(id,x,y,extra={})=>({id,name:id,scope:'test',kind:'etf',group:'sector',status:'ok',eligible:true,instruments:[{symbol:id,name:id}],metrics:{ret_3m:x,relative_3m:x,relative_1m:y},...extra});
  assert.equal(quadrant(row('a',1,1)),'leading');assert.equal(quadrant(row('a',-1,1)),'improving');assert.equal(quadrant(row('a',1,-1)),'weakening');assert.equal(quadrant(row('a',-1,-1)),'lagging');assert.equal(quadrant(row('a',1,1,{eligible:false})),null);
  const rows=[row('a',3,2),row('b',-2,-1),row('c',null,null),row('d',99,3,{status:'stale',eligible:false})];
  assert.deepEqual(filterRows(rows).map(r=>r.id),['a','b','c','d']);
  assert.deepEqual(filterRows(rows,{ascending:true}).map(r=>r.id),['b','a','c','d']);
  assert.deepEqual(filterRows(rows,{query:'b test'}).map(r=>r.id),['b']);
  assert.deepEqual(filterRows(rows,{quad:'lagging'}).map(r=>r.id),['b']);
  assert.equal(filterRows(rows,{query:'missing'}).length,0);
  const doc={updated:'2026-01-04',calendar:['2026-01-01','2026-01-02','2026-01-03','2026-01-04'],benchmark:{name:'market',history:[['2026-01-01',100],['2026-01-02',100],['2026-01-03',110],['2026-01-04',110]]},rows:[{id:'a',name:'a',history:[['2026-01-01',100],['2026-01-02',100],['2026-01-04',120]]},{id:'b',name:'b',history:[['2026-01-02',50],['2026-01-03',55],['2026-01-04',60]]}]};
  const result=comparisonData(doc,['a','b'],{range:'all'});
  assert.equal(result.base,'2026-01-02');assert.deepEqual(result.series[0].values,[100,null,120]);
  const relative=comparisonData(doc,['a','b'],{range:'all'},'relative');
  assert(Math.abs(relative.series[0].values.at(-1)-120/1.1)<1e-8);assert.deepEqual(relative.series.at(-1).values,[100,100,100]);
  assert.equal(comparisonData(doc,['missing'],{range:'all'}).dates.length,0);
  assert.equal(comparisonData(doc,['a'],{range:'custom',rangeFrom:'2027-01-01'}).dates.length,0);
  for(const market of ['us','kr']){
    const published=JSON.parse(fs.readFileSync('data/momentum/momentum_'+market+'.json','utf8'));
    const ids=published.rows.filter(r=>r.eligible).slice(0,5).map(r=>r.id);
    const chart=comparisonData(published,ids,{range:'1y'});
    assert(chart.dates.length>100);assert(chart.series.every(s=>s.values[0]===100));
    assert(chart.series.every(s=>s.values.every(v=>v===null||Number.isFinite(v))));
  }
  const catalog=JSON.parse(fs.readFileSync('data/catalog.json','utf8'));
  const industry=catalog.industries.find(i=>i.id==='momentum');assert(industry);assert.deepEqual(industry.tabs.map(t=>t.id),['us','kr']);
  const app=fs.readFileSync('assets/app.js','utf8');assert(app.includes('ids: ["momentum", "commodities", "macro", "ppi"]'));
  const state={catalog,industry:null,subtab:null},location={hash:''};
  const document={querySelectorAll:()=>[],getElementById:()=>({querySelector:()=>null})};
  const route=new Function('state','location','history','document','setRange','renderIndustry',app.slice(app.indexOf('function route()'),app.indexOf('\nfunction setRange'))+'\nreturn route;')(state,location,{},document,()=>{},()=>{});
  for(const market of ['us','kr']){location.hash='#/momentum/'+market;route();assert.equal(state.industry.id,'momentum');assert.equal(state.subtab,market);}
  location.hash='#/momentum/unknown';route();assert.equal(state.subtab,'us');
  console.log('PASS momentum ranking, missing data, relative chart rebasing, market scopes and routes');
})().catch(error=>{console.error(error);process.exit(1);});
