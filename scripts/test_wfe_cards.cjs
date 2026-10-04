const fs = require('node:fs');
const assert = require('node:assert/strict');
const {context, charts} = require('./test_mineral_cards.cjs');
context.rangeCutoff = () => '0000-00-00';
const docs = {};
for (const suffix of ['global','regions','us','cn','jp','hk','europe']) {
  const id = `market_equity_${suffix}_wfe_m`;
  const doc = docs[suffix] = JSON.parse(fs.readFileSync(`data/macro/${id}.json`, 'utf8'));
  context.renderCard(doc,id);
  const chart = charts.at(-1);
  assert.equal(chart.data.labels.length,104, 'Complete monthly axis retains the two missing source months');
  for (const gap of ['2020-11-30','2020-12-31']) {
    assert(chart.data.datasets.every(d=>d.data[chart.data.labels.indexOf(gap)]===null));
  }
  assert(chart.data.datasets.every(d=>d.spanGaps===false));
  for (const [name, points] of Object.entries(doc.series)) {
    assert(points.every(([date, value])=>value>0 && Number.isFinite(value)));
    assert(points.every(([date])=>new Date(Date.parse(`${date}T00:00:00Z`)+86400000).getUTCDate()===1));
    assert(points.every(([date])=>doc.series_sources[name][date].url.startsWith('https://focus.world-exchanges.org/issue/')));
  }
  assert.equal(doc.period_sources['2026-03-31'].issue,'2026-09','Ambiguous October March headers must not overwrite valid September source');
  assert.equal(doc.period_sources['2026-05-31'].issue,'2026-09','Never relabel the erroneous March column as May');
  assert.equal(doc.period_sources['2026-08-31'].issue,'2026-10');
  const table = context.buildTable(doc,doc.series);
  assert(table.includes('2018-01') && table.includes('2026-08') && table.includes('공식 원문'));
  if (suffix==='europe') {
    assert.equal(chart.data.datasets.length,6);
    assert.equal(chart.data.datasets.filter(d=>!d.hidden).length,3);
    const london=chart.data.datasets.find(d=>d.label==='런던 LSE');
    assert.equal(doc.series['런던 LSE'].at(-1)[0],'2023-09-30');
    assert.equal(london.data.at(-1),null,'Unpublished London history must not appear as current');
    const chips = context.renderCard(doc,id).children.find(c=>c.className==='chips');
    const checkbox=chips.children.at(-1).children[0];
    checkbox.checked=true;checkbox.listeners.change();
    assert.equal(charts.at(-1).data.datasets.at(-1).hidden,false);
  }
}
const values = series => new Map(series);
const close = (a,b) => assert(Math.abs(a-b)<.0002, `${a} != ${b}`);
for (const [date,world] of docs.global.series['세계 합계']) {
  close(world,Object.values(docs.regions.series).reduce((total,series)=>total+values(series).get(date),0));
}
for (const [doc,sum,left,right] of [[docs.us,'NYSE + Nasdaq','NYSE','Nasdaq 미국'],[docs.cn,'상하이 + 선전','상하이','선전']]) {
  for (const [date,total] of doc.series[sum]) close(total,values(doc.series[left]).get(date)+values(doc.series[right]).get(date));
}
console.log('PASS: seven WFE cards, full monthly axes and real gaps, regional/exchange sums, per-month source vintages, European toggles and unpublished London months');
