const assert = require('node:assert/strict');
const fs = require('node:fs');
(async()=>{
  const source = fs.readFileSync('assets/games.js','utf8');
  const m = await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
  const games=[{id:'one',genre:'Puzzle',points:[['2024-01',100,200],['2024-02',200,300],['2024-03',null,0]]}];
  assert.equal(m.daysInMonth('2024-02'),29);
  assert.equal(m.daysInMonth('2025-02'),28);
  const monthly=m.aggregateSteam(games);
  assert.equal(monthly.length,2);
  const annual=m.aggregateSteam(games,'year')[0];
  assert.equal(annual.months,2);
  assert.equal(annual.total,(100*31+200*29)/60);
  assert.equal(annual.first,'2024-01');
  assert.equal(annual.last,'2024-02');
  assert.equal(m.aggregateSteam(games,'month','2024-02','2024-02')[0].total,200);
  assert.equal(m.percent(null,100),null);
  assert.equal(m.percent(0,100),0);
  assert.equal(m.percent(10,0),null);
  const periods=m.snapshotPeriods([{id:'a',date:'2026-10-01',installs_lower:100},{id:'a',date:'2026-10-20',installs_lower:500},{id:'a',date:'2026-11-01',installs_lower:500}], 'a');
  assert.deepEqual(periods.map(p=>p.installs_lower),[500,500]); // no sum/difference of cumulative bands
  assert(m.csvText(['x'],[['=HYPERLINK("url")']]).includes("'=HYPERLINK"));
  assert(m.csvText(['x'],[['a,"b']]).startsWith('\uFEFF"x"\r\n"a,""b"'));
  const catalog=JSON.parse(fs.readFileSync('data/catalog.json'));
  assert.equal(catalog.industries.filter(i=>i.id==='games').length,1);
  const read=name=>JSON.parse(fs.readFileSync(`data/games/${name}.json`));
  assert.equal(catalog.industries.find(i=>i.id==='games').tabs.find(t=>t.id==='mobile').name,'Google Play');
  assert(catalog.industries.find(i=>i.id==='games').tabs.some(t=>t.id==='revenue'));
  if(fs.existsSync('data/games/revenue.json')){
    const revenue=read('revenue');
    for(const report of revenue.reports){
      assert(report.month<report.published && report.published<=report.reviewed);
      for(const store of ['combined','ios','google_play']){
        const rows=m.revenueRows(revenue,report.month,store);
        assert.equal(rows.length,10);
        assert.equal(new Set(rows.map(r=>r.id)).size,rows.length);
        assert(rows.every(r=>r.name&&r.publisher&&r.usd_millions>0));
        assert.deepEqual(rows.map(r=>r.rank),rows.map((_,i)=>i+1));
        assert(Math.abs(m.publisherRevenue(rows).reduce((a,r)=>a+r.value,0)-rows.reduce((a,r)=>a+r.usd_millions,0))<1e-8);
      }
    }
    assert.equal(m.revenueRows(revenue,'2026-07','google_play').length,0);
    assert.equal(m.revenueChange(revenue,'roblox','2026-08','google_play',1),null);
    assert.equal(m.revenueChange(revenue,'roblox','2026-08','combined',12),null); // unranked is not zero
    assert(Math.abs(m.revenueChange(revenue,'roblox','2026-08','google_play',12)-(44/52-1)*100)<1e-8);
    const mixed=[...m.revenueRows(revenue,'2026-08','ios'),...m.revenueRows(revenue,'2026-08','combined')];
    const tencent=m.publisherRevenue(mixed).filter(r=>r.publisher==='Tencent');
    assert.equal(tencent.length,2); // never sum overlapping store scopes
    const companies=read('companies').companies;
    assert.equal(new Set(companies.map(c=>c.id)).size,companies.length);
    for(const c of companies){
      assert(['USD','KRW','CNY','JPY'].includes(c.currency));
      assert.equal(new Set(c.rows.map(r=>r.kind+r.date)).size,c.rows.length);
      for(const r of c.rows){
        assert(r.date<=c.checked && r.start<=r.date);
        assert(r.revenue>0 && r.refs.revenue.url.startsWith('https://'));
        assert(r.refs.revenue.filed<=c.checked);
      }
    }
    assert.equal(m.companyGrowth([{kind:'quarter',date:'2025-06-30',revenue:-5}],{kind:'quarter',date:'2026-06-30',revenue:10}),null);
    const sparse=m.companySeries([{kind:'quarter',date:'2025-03-31',revenue:1},{kind:'quarter',date:'2026-03-31',revenue:2}],'quarter');
    assert.equal(sparse.length,5);
    assert.equal(sparse[1].row,undefined); // missing quarters must break the chart
  }
  if(fs.existsSync('data/games/steam.json')){
    const steam=read('steam');
    assert(steam.games.length>=40);
    assert.equal(new Set(steam.games.map(g=>g.id)).size,steam.games.length);
    for(const game of steam.games){
      assert(game.genre && !game.genre.includes('?'));
      assert(game.points.every(p=>p[0]<steam.fetched.slice(0,7) && p[1]>=0 && p[2]>=0));
      assert.equal(new Set(game.points.map(p=>p[0])).size,game.points.length);
    }
    const mobile=read('mobile'),estimates=read('download-estimates');
    assert(estimates.observations.every(g=>g.source_updated<=g.observed_at && g.downloads_30d<=g.total_estimate && !g.genre.includes('?')));
    const rows=m.mobileRows(mobile,estimates);
    const candy=rows.find(g=>g.id==='com.king.candycrushsaga');
    assert.equal(candy.source_updated,estimates.observations.find(g=>g.id===candy.id).source_updated);
    assert.equal(candy.fetched,mobile.games.find(g=>g.id===candy.id).fetched);
    assert.notEqual(candy.estimate_url,candy.url);
    for(const chart of read('apple').charts){
      assert(chart.games.length>=50);
      assert.equal(new Set(chart.games.map(g=>g.id)).size,chart.games.length);
      assert.deepEqual(chart.games.map(g=>g.rank),chart.games.map((_,i)=>i+1));
      assert(chart.games.some(g=>g.genre!=='미분류'));
    }
    assert.equal(read('market').latest.total,201.6);
    assert(read('market').latest.platforms.some(p=>p.name==='모바일'));
  }
  console.log('PASS: weighted annual CCU, partial periods, missing observations, cumulative snapshots, safe CSV, source dates, chart coverage');
})().catch(e=>{console.error(e);process.exitCode=1;});
