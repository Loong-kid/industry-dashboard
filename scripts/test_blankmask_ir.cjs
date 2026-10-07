const fs = require('node:fs');
const assert = require('node:assert/strict');
const source = fs.readFileSync('assets/app.js', 'utf8');
const start = source.indexOf('function renderCard(');
const end = source.indexOf('  const wrap = document.createElement("div");', start);
class Element {
  constructor() { this.children = []; this.innerHTML = ''; this.textContent = ''; }
  appendChild(child) { this.children.push(child); }
}
const formatting = new Function('escapeHtml', source.slice(source.indexOf('function fmt('), source.indexOf('function koreaTradeChart('))
  + '\nreturn {periodLabel, observationLabel};')(String);
const render = new Function('document', 'daysSince', 'staleDays', 'rangeCutoff', 'fmt', 'escapeHtml', 'periodLabel', 'observationLabel',
  source.slice(start, end) + '\nreturn card; }\nreturn renderCard;')(
  {createElement: () => new Element()}, () => 0, () => null, () => '0000-00-00', String, String, formatting.periodLabel, formatting.observationLabel);
const headline = doc => render(doc, doc.id).children.map(e => e.innerHTML).join('');
const fiscal=JSON.parse(fs.readFileSync('data/semicon/photronics_ic_revenue.json','utf8'));
// Keep the regression anchor stable as the automatic collector adds quarters.
for (const name of Object.keys(fiscal.series)) fiscal.series[name]=fiscal.series[name].filter(([date])=>date<='2026-08-02');
assert(headline(fiscal).includes('FY2026 Q3 · 2026-08-02'));
assert(headline(fiscal).includes('YoY +27.7% · QoQ +20.9%'));
const fiscalGap=structuredClone(fiscal);
fiscalGap.comparison_dates['2026-08-02'].quarter_ago=null;
assert(headline(fiscalGap).includes('QoQ 자료 없음'));
const sparse = {id:'quarter',name:'Segment',unit:'JPY',quarter_labels:true,quarterly_revenue_summary:true,
  series:{sales:[['2025-06-30',100],['2025-12-31',150],['2026-06-30',200]]}};
assert(headline(sparse).includes('YoY +100.0% · QoQ 자료 없음'));
assert(headline(sparse).includes('2026 Q2'));
const boundary = {...sparse,series:{sales:[['2025-03-31',100],['2025-12-31',160],['2026-03-31',200]]}};
assert(headline(boundary).includes('YoY +100.0% · QoQ +25.0%'));
for (const id of ['hoya_it_revenue','agc_materials_revenue','shinetsu_materials_revenue','hoya_blank_growth','agc_euv_annual_revenue','agc_sheet_materials_revenue','agc_euv_revenue_estimate','agc_duv_substrate_revenue_estimate','hoya_electronics_revenue_estimate','hoya_lsi_revenue_estimate','hoya_fpd_revenue_estimate','hoya_hdd_revenue_estimate']) {
  const doc=JSON.parse(fs.readFileSync(`data/semicon/${id}.json`,'utf8'));
  assert(!/NaN|Infinity/.test(headline(doc)));
  if(doc.change_mode==='none')assert(!headline(doc).includes('stat-delta'));
}
const marker=source.indexOf('function periodLabel(');
const funcs = new Function('escapeHtml','fmt','observationLabel',source.slice(marker,source.indexOf('// ── 차트',marker))+'\nreturn {buildTable};')(String,String,formatting.observationLabel);
const doc=JSON.parse(fs.readFileSync('data/semicon/hoya_it_revenue.json','utf8'));
const table=funcs.buildTable(doc,doc.series);
assert(table.includes('달력 분기'));
assert(table.includes('2021 Q2'));
assert(table.includes('#page=8'));
assert.equal((table.match(/target="_blank"/g)||[]).length,21);
const fiscalTable=funcs.buildTable(fiscal,fiscal.series);
assert(fiscalTable.includes('회계 분기 · 종료일'));
assert(fiscalTable.includes('FY2026 Q3 · 2026-08-02'));
assert.equal((fiscalTable.match(/target="_blank"/g)||[]).length,28); // 23 quarters + 5 Q4 supporting reports
console.log('PASS: quarterly YoY/QoQ calendar alignment, growth-rate headline, full history and PDF provenance links');
