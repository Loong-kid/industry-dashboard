const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
(async()=>{
  const root=path.join(__dirname,'..');
  const code=fs.readFileSync(path.join(root,'assets/us-treasury.js'),'utf8');
  const {fmt,trailing,inRange,borrowingSeries,monthlyActual}=await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'));
  assert.equal(fmt(null),'—');assert.equal(fmt(0),'0');
  assert.deepEqual(trailing([{v:1},{v:2},{v:3}],'v',2),[null,1.5,2.5]);
  assert.deepEqual(trailing([{v:1},{v:null}],'v',2),[null,null]);
  assert.equal(inRange([{date:'2014-01-01'},{date:'2025-11-13'},{date:'2026-11-13'}],'1').length,2);
  const vintages=[{publication_date:'2026-02-01',source_url:'a',rows:[{quarter:'2026 Q1',status:'estimate',borrowing:100,cash:50}]},{publication_date:'2026-05-01',source_url:'b',rows:[{quarter:'2026 Q1',status:'actual',borrowing:80,cash:40}]}];
  const s=borrowingSeries(vintages);assert.equal(s[0].first.borrowing,100);assert.equal(s[0].actual.borrowing,80);assert.equal(s[0].latest.cash,50);
  assert.equal(monthlyActual([{date:'2026-11-10',term:'10-Year',amount:42,completed:true},{date:'2026-11-11',term:'10-Year',amount:99,completed:false}],'2026-11','10-Year'),42);
  assert.equal(monthlyActual([],'2026-12','10-Year'),null);
  const catalog=JSON.parse(fs.readFileSync(path.join(root,'data/catalog.json')));
  assert.equal(catalog.industries.some(i=>i.id==='us_treasury'),false);
  assert.deepEqual(catalog.industries.find(i=>i.id==='macro').tabs.find(t=>t.id==='us_treasury').views.map(t=>t.id),['qra','auctions','yields']);
  const app=fs.readFileSync(path.join(root,'assets/app.js'),'utf8');
  const state={catalog,industry:null,subtab:null};const location={hash:''};
  const history={replaceState(_,__,hash){location.hash=hash;}};
  const document={querySelectorAll:()=>[],getElementById:()=>({querySelector:()=>null})};
  const route=new Function('state','location','history','document','setRange','renderIndustry',app.slice(app.indexOf('function route()'),app.indexOf('\nfunction setRange'))+'\nreturn route;')(state,location,history,document,()=>{},()=>{});
  for(const view of ['qra','auctions','yields']){
    location.hash=`#/macro/us_treasury/${view}`;route();assert.equal(state.industry.id,'macro');assert.equal(state.subtab,'us_treasury');assert.equal(state.treasuryView,view);
    location.hash=`#/us_treasury/${view}`;route();assert.equal(location.hash,`#/macro/us_treasury/${view}`);assert.equal(state.treasuryView,view);
  }
  for(const hash of ['#/us_treasury','#/us_treasury/invalid','#/macro/us_treasury/invalid']){location.hash=hash;route();assert.equal(state.treasuryView,'qra');}
  for(const tab of ['rates','liquidity','sovereign','market_size']){location.hash=`#/macro/${tab}`;route();assert.equal(state.subtab,tab);}
  console.log('PASS Treasury vintage comparison, moving averages, range and unpublished auction handling');
})().catch(e=>{console.error(e);process.exit(1);});
