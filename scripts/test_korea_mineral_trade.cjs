const fs=require('node:fs');const assert=require('node:assert/strict');
const {context,charts}=require('./test_mineral_cards.cjs');
const doc=JSON.parse(fs.readFileSync('data/commodities/comm_korea_mineral_trade.json','utf8'));
const registry=JSON.parse(fs.readFileSync('scripts/korea_mineral_trade_registry.json','utf8'));
assert.equal(doc.minerals.length,Object.keys(registry.minerals).length);
assert.equal(doc.minerals.length,73);assert.deepEqual(doc.raw_units,{amount:'USD',weight:'kg'});
for(const m of doc.minerals){
 assert.equal(registry.minerals[m.id],m.komis_name);
 for(const year of Object.keys(m.annual)) assert(Number(year)<=doc.last_full_year);
 for(const kind of ['amount','weight']){
  const data=context.koreaTradeChart(doc,m,kind),field=kind==='amount'?'incmAmt':'incmWeig',divisor=kind==='amount'?1e6:1000;
  const latest=Object.keys(m.annual).at(-1);
  assert.equal(data.series_views.annual.series['수입'].at(-1)[1],m.annual[latest][field]/divisor);
  assert.equal(data.series_views.ytd.series['수입'].at(-1)[1],m.snapshots.ytd.totals==null?null:m.snapshots.ytd.totals[field]/divisor);
  assert.equal(data.series_views.month.series['수입'].at(-1)[1],m.snapshots.month.totals==null?null:m.snapshots.month.totals[field]/divisor);
  assert.equal(data.series_views.ytd.cumulative,true);assert.equal(data.full_range,true);assert.deepEqual(Array.from(data.default_series),['수입']);
  const annual={...data,...data.series_views.annual};delete annual.series_views;
  const card=context.renderCard(annual,data.id);
  const chart=charts.at(-1);assert(chart.data.labels.every(date=>Number(date.slice(0,4))<=doc.last_full_year));
  const foot=card.children.find(child=>child.className==='card-foot');foot.querySelector('.table-btn').listeners.click();
  assert(card.children.find(child=>child.className==='data-table').innerHTML.includes(latest));
 }
 for(const snapshot of Object.values(m.snapshots)){
  if(!snapshot.totals)continue;
  for(const field of ['incmAmt','incmWeig','expAmt','expWeig']){
   assert(snapshot.totals[field]>=0&&Number.isFinite(snapshot.totals[field]));
   assert(snapshot.countries.reduce((sum,r)=>sum+r[field],0)<=snapshot.totals[field]+1e-6);
  }
 }
}
const copper=doc.minerals.find(m=>m.id==='MNRL0008');
assert.equal(copper.annual['2025'].incmWeig,2575234253);
assert.equal(context.koreaTradeChart(doc,copper,'weight').series_views.annual.series['수입'].at(-1)[1],2575234.253);
assert.equal(copper.hs_codes.length,69);
console.log('PASS: all 73 identities, raw USD/kg, 146 annual cards/tables, incomplete-year exclusion, matched YTD/month and source-total denominators');
