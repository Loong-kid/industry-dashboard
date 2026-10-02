const fs = require('node:fs');
const assert = require('node:assert/strict');
const source = fs.readFileSync('assets/app.js', 'utf8');
const start = source.indexOf('function renderCard(');
const end = source.indexOf('  const wrap = document.createElement("div");', start);
class Element {
  constructor() { this.children = []; this.innerHTML = ''; this.textContent = ''; }
  appendChild(child) { this.children.push(child); }
}
const render = new Function('document', 'daysSince', 'staleDays', 'rangeCutoff', 'fmt', 'escapeHtml',
  source.slice(start, end) + '\nreturn card; }\nreturn renderCard;')(
  {createElement: () => new Element()}, () => 0, () => null, () => '0000-00-00', String, String);
const headline = doc => render(doc, doc.id).children.map(e => e.innerHTML).join('');
const sparse = {id: 'monthly', name: 'Monthly exports', unit: 'JPY', monthly_trade_summary: true,
  series: {exports: [['2025-01-01', 100], ['2025-11-01', 150], ['2026-01-01', 200]]}};
assert(headline(sparse).includes('YoY +100.0%'));
assert(headline(sparse).includes('MoM 자료 없음')); // Do not compare January with November.
const regular = {...sparse, series: {exports: [['2025-01-01', 100], ['2025-12-01', 160], ['2026-01-01', 200]]}};
assert(headline(regular).includes('MoM +25.0%'));
const missing = {...sparse, series: {exports: [['2025-01-01', 100], ['2025-12-01', 0], ['2026-01-01', null]]}};
assert(headline(missing).includes('stat-value">—'));
assert(!/NaN|Infinity/.test(headline(missing)));

const catalog = JSON.parse(fs.readFileSync('data/catalog.json', 'utf8'));
const semicon = catalog.industries.find(i => i.id === 'semicon');
const sections = semicon.sections.filter(s => s.indicators.some(id => id.startsWith('jp_')));
assert.equal(sections.length, 2);
assert(sections.every(s => s.tab === 'snstech'));
for (const id of sections.flatMap(s => s.indicators)) {
  const doc = JSON.parse(fs.readFileSync(`data/semicon/${id}.json`, 'utf8'));
  assert.equal(doc.id, id);
  for (const points of Object.values(doc.series)) {
    assert.equal(points.length, 68);
    assert.equal(new Set(points.map(p => p[0])).size, points.length);
    assert.equal(points[0][0], '2021-01-01');
    assert.equal(points.at(-1)[0], '2026-08-01');
  }
  assert(!/NaN|Infinity/.test(headline(doc)));
}
const country = JSON.parse(fs.readFileSync('data/semicon/jp_blank_country.json', 'utf8'));
const amount = JSON.parse(fs.readFileSync('data/semicon/jp_blank_amount.json', 'utf8'));
const world = Object.values(amount.series)[0];
for (let i = 0; i < world.length; i++) {
  assert(Math.abs(Object.values(country.series).reduce((v, s) => v + s[i][1], 0) - world[i][1]) < 0.000001);
}
assert.equal(Math.round(world.filter(p => p[0].startsWith('2021')).reduce((v, p) => v + p[1], 0) * 1000), 41228338);
console.log('PASS: YoY/MoM calendar dates, missing/zero baselines, 68-month coverage, country totals and KOTRA benchmark');
