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
