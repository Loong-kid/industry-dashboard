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
  assert.deepEqual(catalog.industries.find(i=>i.id==='us_treasury').tabs.map(t=>t.id),['qra','auctions','yields']);
  console.log('PASS Treasury vintage comparison, moving averages, range and unpublished auction handling');
})().catch(e=>{console.error(e);process.exit(1);});
