const fs = require('node:fs');
const assert = require('node:assert/strict');
const {context, charts} = require('./test_mineral_cards.cjs');
const catalog = JSON.parse(fs.readFileSync('data/catalog.json', 'utf8'));
const industry = catalog.industries.find(i => i.id === 'institution');
assert.deepEqual(industry.tabs.map(t=>t.id), ['domestic','us_managers','hedge_funds']);
assert(industry.sections.slice(0,3).every(s=>s.tab==='domestic' && s.type==='table'));
for (const section of industry.sections.filter(s=>s.tab!=='domestic')) {
  for (const id of section.indicators) {
    const doc = JSON.parse(fs.readFileSync(`data/institution/${id}.json`, 'utf8'));
    if (id === 'us_managers') {
      assert.equal(doc.managers.length,6);
      assert(doc.managers.every(m=>m.latest.valuation_date===null && m.latest.source.startsWith('https://reports.adviserinfo.sec.gov/')));
      continue;
    }
    assert(doc.strict_range);
    const card = context.renderCard(doc,id);
    const chart = charts.at(-1);
    assert(card.children.some(c=>c.innerHTML?.includes(doc.source_url)));
    assert.equal(chart.data.datasets.length,Object.keys(doc.series).length);
    if (id.startsWith('hf_returns') || id==='hf_growth') {
      assert(card.children.some(c=>c.children.some(n=>n.href==='https://creativecommons.org/licenses/by/4.0/')));
    }
    if (id==='hf_returns_annual') {
      assert.equal(doc.frequency,'yearly');
      assert(Object.values(doc.series).every(points=>points.every(p=>p[0].endsWith('-12-31'))));
      const [year,month] = doc.source_as_of.split('-').map(Number);
      const completeYear = year - (month===12 ? 0 : 1);
      assert(Object.values(doc.series).every(points=>points.every(p=>Number(p[0].slice(0,4))<=completeYear)));
    }
    if (id==='psh_returns_annual') {
      assert(doc.manual);
      assert(doc.series['PSH NAV / 보수 차감 후'].length>=13);
      assert.equal(doc.series['PSH NAV / 보수 차감 후'][0][1],9.6,'PSH, not PSLP 9.7%');
    }
  }
}
const oldQuarter = JSON.parse(fs.readFileSync('data/institution/hf_assets.json','utf8'));
const nextDay = new Date(oldQuarter.updated + 'T00:00:00Z');
nextDay.setUTCDate(nextDay.getUTCDate()+1);
const cutoff = nextDay.toISOString().slice(0,10);
context.rangeCutoff = ()=>cutoff;
const card = context.renderCard(oldQuarter,oldQuarter.id);
assert.equal(charts.at(-1).data.labels.length,0,'No silent full-history fallback for new cards');
assert(card.children.some(c=>c.textContent.includes('선택한 기간에 공표 자료가 없습니다')));
const monthly = JSON.parse(fs.readFileSync('data/institution/hf_returns_composite.json','utf8'));
context.renderCard(monthly,monthly.id);
assert(charts.at(-1).data.labels.every(d=>d>=cutoff));
console.log('PASS: institutional placement, licensing, PSH identity, complete years and strict date ranges');
