const assert=require('node:assert/strict'),fs=require('node:fs');
(async()=>{
 const source=fs.readFileSync('assets/semicon-valuation.js','utf8');
 const {sampleRows,valueAt,basisValue}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
 const rows=Array.from({length:4000},(_,i)=>[String(i).padStart(5,'0'),i===1234?999999:i===2456?-99999:i%50]);
 const sampled=sampleRows(rows);
 assert(sampled.length<=644);assert.equal(sampled[0],rows[0]);assert.equal(sampled.at(-1),rows.at(-1));
 assert(sampled.includes(rows[1234]));assert(sampled.includes(rows[2456]));
 assert.deepEqual(valueAt([['2026-01-01',2],['2026-04-01',3]],'2026-03-31'),['2026-01-01',2]);
 assert.equal(valueAt([['2026-01-01',2]],'2025-12-31'),null);
 const doc={currency:'HKD',fundamentals:{eps:[['2026-01-01',2,'CNY']]},fx:{CNYHKD:[['2026-01-05',1.1]]}};
 assert.equal(basisValue(doc,'eps','2026-01-05'),2.2);assert.equal(basisValue(doc,'eps','2026-01-20'),null);
 console.log('Valuation extrema-preserving sampling, date lookup and FX scopes passed.');
})().catch(e=>{console.error(e);process.exit(1);});
