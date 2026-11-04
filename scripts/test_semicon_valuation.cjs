const assert=require('node:assert/strict'),fs=require('node:fs');
(async()=>{
 const source=fs.readFileSync('assets/semicon-valuation.js','utf8');
 const {sampleRows,valueAt,basisValue,basisState,valuationChartData}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
 const rows=Array.from({length:4000},(_,i)=>[String(i).padStart(5,'0'),i===1234?999999:i===2456?-99999:i%50]);
 const sampled=sampleRows(rows);
 assert(sampled.length<=644);assert.equal(sampled[0],rows[0]);assert.equal(sampled.at(-1),rows.at(-1));
 assert(sampled.includes(rows[1234]));assert(sampled.includes(rows[2456]));
 assert.deepEqual(valueAt([['2026-01-01',2],['2026-04-01',3]],'2026-03-31'),['2026-01-01',2]);
 assert.equal(valueAt([['2026-01-01',2]],'2025-12-31'),null);
 const doc={currency:'HKD',fundamentals:{eps:[['2026-01-01',2,'CNY']]},fx:{CNYHKD:[['2026-01-05',1.1]]}};
 assert.equal(basisValue(doc,'eps','2026-01-05'),2.2);assert.equal(basisValue(doc,'eps','2026-01-20'),null);
 const prices=Array.from({length:3000},(_,i)=>[new Date(Date.UTC(2018,0,1+i)).toISOString().slice(0,10),100+i%7]);
 const history={currency:'USD',fundamentals:{eps:[
  [prices[0][0],2,'USD'],[prices[800][0],-3,'USD'],[prices[801][0],4,'USD'],
  [prices[1300][0],-2,'USD'],[prices[1500][0],0,'USD'],[prices[1550][0],1,'USD']
 ],bps:[[prices[0][0],5,'USD']]},bands:{per:[10,20],pbr:[2,3]},fx:{}};
 const before=JSON.stringify(history);
 for(const large of [false,true]){
  const result=valuationChartData(history,'per',prices,large);
  for(const index of [799,800,801,1299,1300,1499,1500,1549,1550,2010,2011])assert(result.points.some(r=>r[0]===prices[index][0]),'loss, zero and stale boundaries retained: '+index);
  assert.equal(result.losses.length,2);
  assert.deepEqual(result.losses.map(r=>[result.points[r.start][0],result.points[r.end][0]]),[[prices[800][0],prices[801][0]],[prices[1300][0],prices[1500][0]]]);
  for(const band of result.bands)for(const [i,r] of result.points.entries()){
   const eps=basisValue(history,'eps',r[0]);
   assert.equal(band.values[i],Number.isFinite(eps)&&eps>0?eps*band.multiple:null);
  }
  const lossesOnly=valuationChartData(history,'per',prices.slice(1300,1500),large);
  assert.deepEqual(lossesOnly.bands,[]);assert.deepEqual(lossesOnly.losses,[{start:0,end:lossesOnly.points.length}]);
  const zeroOnly=valuationChartData(history,'per',prices.slice(1500,1550),large);
  assert.deepEqual(zeroOnly.bands,[]);assert.deepEqual(zeroOnly.losses,[]);
  const stale=valuationChartData(history,'per',prices.slice(2011),large);
  assert.deepEqual(stale.bands,[]);assert.deepEqual(stale.losses,[]);
 }
 assert.equal(JSON.stringify(history),before);
 assert.deepEqual(valuationChartData(history,'price',prices).losses,[]);
 assert.deepEqual(valuationChartData(history,'pbr',prices).losses,[]);
 assert.equal(basisState(-2),'loss');assert.equal(basisState(0),'zero');assert.equal(basisState(null),'missing');assert.equal(basisState(NaN),'missing');
 assert.deepEqual(valuationChartData(history,'per',[]).losses,[]);
 const fxLoss={currency:'HKD',fundamentals:{eps:[['2026-01-01',-2,'CNY']]},bands:{per:[10]},fx:{CNYHKD:[['2026-01-05',1.1]]}};
 const converted=valuationChartData(fxLoss,'per',[['2026-01-05',20],['2026-01-20',20]]);
 assert.deepEqual(converted.losses,[{start:0,end:2}]);assert.deepEqual(converted.bands,[]); // known negative EPS remains a loss even when FX is unavailable
 // Exercise the same renderer against every registered issuer's real history.
 const index=JSON.parse(fs.readFileSync('data/semicon/valuation/valuation_index.json','utf8'));
 for(const company of index.companies.filter(c=>c.status==='listed')){
  const d=JSON.parse(fs.readFileSync(`data/semicon/valuation/${company.id}.json`,'utf8'));
  const result=valuationChartData(d,'per',d.prices);
  for(const band of result.bands)for(const [i,r] of result.points.entries()){
   const eps=basisValue(d,'eps',r[0]);
   assert.equal(band.values[i],Number.isFinite(eps)&&eps>0?eps*band.multiple:null,company.id+' '+r[0]);
  }
  for(const period of result.losses)assert(result.points.slice(period.start,period.end).every(r=>valueAt(d.fundamentals.eps,r[0])?.[1]<0));
 }
 console.log('Valuation extrema-preserving sampling, date lookup and FX scopes passed.');
})().catch(e=>{console.error(e);process.exit(1);});
