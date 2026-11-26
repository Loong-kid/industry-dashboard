const assert = require('node:assert/strict');
const fs = require('node:fs');
(async()=>{
  const m = await import('data:text/javascript;base64,'+Buffer.from(fs.readFileSync('assets/steam-trends.js','utf8')).toString('base64'));
  const data = {date:'2026-11-27',
    apps:{1:{name:'New',release:'2026-11-01',type:'game'},2:{name:'Old',release:'2020-01-01',type:'game'},3:{name:'Tool',release:'2026-10-01',type:'application'},4:{name:'Undated'}},
    concurrent:{ranks:[[1,5,1000,2000],[2,1,9000,9500],[3,9,100,100],[4,10,50,60]]},
    weekly:[{week:'2026-11-23',ranks:[[1,3,40,2100],[2,1,1,9900],[3,8,null,100]]}]};
  const rows = m.newReleaseRows(data, 365);
  assert.deepEqual(rows.map(r=>r.id),[1]); // 오래된 게임·게임 아닌 앱·출시일 미상은 제외
  assert.equal(rows[0].age,26);
  assert.equal(rows[0].week[2],40);
  assert.equal(m.ageDays({release:'2026-07-09',launch:'2024-01-01'},'2024-01-31'),30);
  const movers = m.weeklyMovers(data);
  assert.deepEqual(movers.map(r=>[r.id,r.jump]),[[1,37]]);
  const fade = m.fadeRow([[0,'2025-06',100,300,50],[1,'2025-07',200,500,100],[4,'2025-10',50,90,25]]);
  assert.equal(fade.peakIndex,1);
  assert.equal(fade.after[3],25);
  assert.equal(fade.after[1],null); // 관측 없는 달은 0이 아니라 비움
  assert.equal(m.median([3,null,1,2]),2);
  assert.equal(m.median([]),null);
  assert.equal(m.shareOf([],()=>true),null);
  const catalog = JSON.parse(fs.readFileSync('data/catalog.json'));
  assert(catalog.industries.find(i=>i.id==='games').tabs.some(t=>t.id==='steamhits'));
  assert(fs.readFileSync('assets/games.js','utf8').includes('["steamhits","Steam 신작 흥행"]'));
  if(fs.existsSync('data/games/steam_trends.json')){
    const d = JSON.parse(fs.readFileSync('data/games/steam_trends.json'));
    assert(d.concurrent.ranks.length>=50);
    for(const app of Object.values(d.apps)){
      for(const r of app.daily||[]) assert(/^\d{4}-\d{2}-\d{2}$/.test(r[0]) && (r[1]==null || r[1]>=0));
      for(const r of app.lifecycle||[]) assert(r[0]>=0 && r[4]<=100);
    }
  }
  console.log('steam trends ok');
})().catch(e=>{console.error(e);process.exit(1);});
