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
    const fx=read('fx');
    assert.equal(fx.base,'USD');
    assert(Array.isArray(fx.missing));
    const beforeOriginals=JSON.stringify(companies);
    assert.equal(new Set(companies.map(c=>c.id)).size,companies.length);
    for(const c of companies){
      assert(['USD','KRW','CNY','JPY','PLN'].includes(c.currency));
      assert.equal(new Set(c.rows.map(r=>r.kind+r.date)).size,c.rows.length);
      for(const r of c.rows){
        assert(r.date<=c.checked && r.start<=r.date);
        assert(r.revenue>0 && r.refs.revenue.url.startsWith('https://'));
        assert(r.refs.revenue.filed<=c.checked);
        const usd=m.usdAmount(r.revenue,c.currency,r,fx),q=m.fxQuote(fx,c.currency,r);
        if(usd==null){
          assert(fx.missing.includes(`${c.currency}|${r.start}|${r.date}`),`${c.id} ${r.date}: missing FX must be tracked`);
          continue;
        }
        assert(usd>0);
        assert(Math.abs(usd*q.local_per_usd-r.revenue)<1e-6);
        if(c.currency==='USD')assert.equal(usd,r.revenue);
        else {
          assert(q.observations>=50);
          assert(q.first>=r.start&&q.last<=r.date);
          assert(m.moneyMemo(r.revenue,c.currency,r,fx).join(' ').includes(c.currency));
        }
      }
    }
    assert.equal(JSON.stringify(companies),beforeOriginals); // conversion never rewrites original amounts/provenance
    for(const c of companies.filter(c=>c.rows.length))for(const key of ['revenue','operating_profit','net_income']){
      const doc=m.companyMetricDocument(c,key,fx);
      assert.equal(doc.unit,'백만 USD');
      assert.equal(doc.span_gaps,false);
      for(const kind of ['quarter','annual']){
        const view=doc.series_views[kind],rows=c.rows.filter(r=>r.kind===kind);
        for(const r of rows.filter(r=>Number.isFinite(r[key]))){
          const point=Object.values(view.series).flat().find(p=>p[0]===r.date);
          assert(point,`${c.id} ${key} ${kind} ${r.date}: omitted disclosure`);
          assert.equal(point[1],m.usdAmount(r[key],c.currency,r,fx));
          assert.equal(view.period_labels[r.date],r.period);
          assert(view.point_notes[r.date].join(' ').includes(c.currency));
          assert.equal(view.point_sources[r.date].url,r.refs[key].url);
        }
      }
    }
    assert.equal(m.companyMetricDocument(companies.find(c=>c.id==='netease'),'revenue',fx).default_view,'annual');
    assert.deepEqual(m.companyMetricDocument(companies.find(c=>c.id==='sony_games'),'net_income',fx).series_views.annual.series,{});
    const sparseDoc=m.companyMetricDocument({id:'sparse',name:'Sparse',currency:'USD',fiscal_start:4,rows:[{kind:'quarter',start:'2025-04-01',date:'2025-06-30',period:'FY2026 Q1',revenue:10},{kind:'quarter',start:'2025-10-01',date:'2025-12-31',period:'FY2026 Q3',revenue:20}]},'revenue',null);
    assert.deepEqual(sparseDoc.series_views.quarter.series['매출'],[['2025-06-30',10],['2025-09-30',null],['2025-12-31',20]]);
    assert.deepEqual(sparseDoc.series_views.annual.series,{}); // never fabricate annuals by summing/dividing available quarters
    assert.equal(JSON.stringify(companies),beforeOriginals);
    const interval={kind:'quarter',start:'2026-01-01',date:'2026-03-31'},prior={...interval,start:'2025-01-01',date:'2025-03-31',revenue:140000};
    const fakeFx={periods:{'KRW|2026-01-01|2026-03-31':{currency:'KRW',start:interval.start,end:interval.date,local_per_usd:1500},'KRW|2025-01-01|2025-03-31':{currency:'KRW',start:prior.start,end:prior.date,local_per_usd:1400}}};
    assert.equal(m.usdAmount(-150000,'KRW',interval,fakeFx),-100); // losses retain their sign
    assert.equal(m.usdAmount(0,'KRW',interval,fakeFx),0);
    assert.equal(m.usdAmount(null,'KRW',interval,fakeFx),null);
    assert.equal(m.usdAmount(NaN,'USD',interval,fakeFx),null);
    assert.equal(m.usdAmount(150000,'JPY',interval,fakeFx),null);
    assert.equal(m.usdAmount(150000,'KRW',{...interval,start:'2026-01-02'},fakeFx),null); // no neighboring period/spot fallback
    assert.equal(m.usdAmount(150000,'KRW',interval,null),null);
    assert.equal(m.usdAmount(123,'USD',interval,null),123); // native USD works even during FX outage
    assert.equal(m.usdGrowth({currency:'KRW',rows:[prior]},{...interval,revenue:150000},fakeFx),0); // native growth differs from USD growth
    assert(m.companyGrowth([prior],{...interval,revenue:150000})>7);
    const crossCountry=[{currency:'KRW',revenue:150000},{currency:'USD',revenue:110}];
    assert.equal(crossCountry.sort((a,b)=>m.usdAmount(b.revenue,b.currency,interval,fakeFx)-m.usdAmount(a.revenue,a.currency,interval,fakeFx))[0].currency,'USD');
    const invalidFx=structuredClone(fakeFx);invalidFx.periods['KRW|2026-01-01|2026-03-31'].local_per_usd=0;
    assert.equal(m.usdAmount(150000,'KRW',interval,invalidFx),null);
    assert.equal(m.companyGrowth([{kind:'quarter',date:'2025-06-30',revenue:-5}],{kind:'quarter',date:'2026-06-30',revenue:10}),null);
    const sparse=m.companySeries([{kind:'quarter',date:'2025-03-31',revenue:1},{kind:'quarter',date:'2026-03-31',revenue:2}],'quarter');
    assert.equal(sparse.length,5);
    assert.equal(sparse[1].row,undefined); // missing quarters must break the chart
    assert(companies.length>=25);
    assert(companies.every(c=>c.region&&c.country&&c.roles?.length&&c.scope));
    assert(m.directoryRows(companies,{region:'日本'}).length===0); // filters are explicit, not fuzzy currency inference
    assert(m.directoryRows(companies,{region:'일본'}).some(c=>c.id==='nintendo'));
    assert(m.directoryRows(companies,{query:'Steam'}).some(c=>c.id==='valve'));
    assert(m.directoryRows(companies,{query:'스팀'}).some(c=>c.id==='valve'));
    assert(m.directoryRows(companies,{query:'언리얼'}).some(c=>c.id==='epic'));
    assert(m.directoryRows(companies,{role:'engine'}).some(c=>c.id==='epic'));
    assert(!m.directoryRows(companies,{role:'engine'}).some(c=>c.id==='netmarble'));
    assert(companies.filter(c=>['epic','valve'].includes(c.id)).every(c=>c.listing==='private'&&c.rows.length===0));
    assert.equal(companies.find(c=>c.id==='ea').listing,'private');
    const platforms=read('platforms');
    for(const p of platforms.profiles)for(const r of p.metrics)if(m.monetaryMetric(r)){
      const currency=r.unit.split(' ').at(-1);
      const converted=m.usdAmount(r.value,currency,r,fx);
      assert(converted>0||fx.missing.includes(`${currency}|${r.start}|${r.date}`));
      if(currency==='USD')assert.equal(m.usdAmount(r.value,currency,r,fx),r.value);
    }
    for(const r of revenue.official_games)assert(m.usdAmount(r.revenue_millions,r.currency,r,fx)>0||fx.missing.includes(`${r.currency}|${r.start}|${r.date}`));
    assert(!m.monetaryMetric({kind:'activity',unit:'백만 계정',value:100}));
    assert.equal(m.platformMetrics(platforms,'epic').find(r=>r.id==='store_spend').kind,'spend');
    assert.equal(m.platformMetrics(platforms,'steam').filter(r=>r.id==='online_now').length,platforms.steam.observations.length);
    assert(m.platformMetrics(platforms,'steam').every(r=>r.kind==='concurrency'&&r.unit==='계정'));
    assert.equal(m.platformMetrics(platforms,'does-not-exist').length,0);
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
