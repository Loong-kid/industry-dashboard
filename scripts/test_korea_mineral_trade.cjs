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
  assert.equal(data.default_view,'month');
  assert.equal(data.series_views.month.monthly_axis,true);
  assert.equal(data.series_views.month.monthly_trade_summary,true);
  assert.equal(data.series_views.month.full_range,false);
  assert.equal(data.series_views.month.series['수입'].length,Object.keys(m.monthly).length);
  for (const [date,value] of Object.entries(m.monthly)) {
   const end=new Date(Date.UTC(Number(date.slice(0,4)),Number(date.slice(5,7)),0)).toISOString().slice(0,10);
   assert.equal(data.series_views.month.series['수입'].find(p=>p[0]===end)[1],value==null?null:value[field]/divisor);
   const exportField=kind==='amount'?'expAmt':'expWeig';
   assert.equal(data.series_views.month.series['수출'].find(p=>p[0]===end)[1],value==null?null:value[exportField]/divisor);
  }
  assert.equal(data.series_views.ytd.cumulative,true);assert.equal(data.full_range,true);assert.deepEqual(Array.from(data.default_series),['수입']);
  const annual={...data,...data.series_views.annual};delete annual.series_views;
  const card=context.renderCard(annual,data.id);
  const chart=charts.at(-1);assert(chart.data.labels.every(date=>Number(date.slice(0,4))<=doc.last_full_year));
  const foot=card.children.find(child=>child.className==='card-foot');foot.querySelector('.table-btn').listeners.click();
  assert(card.children.find(child=>child.className==='data-table').innerHTML.includes(latest));
  const monthly={...data,...data.series_views.month,full_range:true};delete monthly.series_views;
  const monthCard=context.renderCard(monthly,data.id);
  const monthChart=charts.at(-1);
  assert.equal(monthChart.data.labels.length,Object.keys(m.monthly).length);
  assert.equal(monthChart.data.labels[0].slice(0,7),doc.monthly_start.slice(0,7));
  assert.equal(monthChart.data.labels.at(-1).slice(0,7),doc.updated.slice(0,7));
  assert.equal(monthChart.data.datasets[0].data.at(-1),m.snapshots.month.totals==null?null:m.snapshots.month.totals[field]/divisor);
  monthCard.children.find(child=>child.className==='card-foot').querySelector('.table-btn').listeners.click();
  const table=monthCard.children.find(child=>child.className==='data-table').innerHTML;
  assert(table.includes(doc.monthly_start.slice(0,7))&&table.includes(doc.updated.slice(0,7)));
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
// Month-start and month-end dating must both match the same calendar periods,
// including leap-year February, rather than look up a fixed day of the month.
for(const day of ['01','end']) {
 const date=(year,month)=>day==='end'?new Date(Date.UTC(year,month,0)).toISOString().slice(0,10):`${year}-${String(month).padStart(2,'0')}-01`;
 const fixture={id:'month_test',name:'monthly comparison',source:'fixture',unit:'USD',full_range:true,monthly_trade_summary:true,month_labels:true,
  series:{'수입':[[date(2023,2),100],[date(2024,1),150],[date(2024,2),200]]}};
 const card=context.renderCard(fixture,fixture.id);
 const stat=card.children.find(child=>child.className==='card-stat').innerHTML;
 assert(stat.includes('YoY +100.0%')&&stat.includes('MoM +33.3%'),day);
 assert(stat.includes('2024-02'));
}
console.log('PASS: all 73 complete monthly calendars and units, 146 monthly/annual cards/tables, gaps, period comparisons, latest snapshots and source-total denominators');
