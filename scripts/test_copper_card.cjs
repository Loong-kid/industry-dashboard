const fs = require('node:fs');
const assert = require('node:assert/strict');
const source = fs.readFileSync('assets/app.js', 'utf8');
const start = source.indexOf('function renderCard(');
const end = source.indexOf('  const wrap = document.createElement("div");', start);
class Element {
  constructor() { this.children = []; this.innerHTML = ''; this.textContent = ''; }
  appendChild(child) { this.children.push(child); }
}
const render = new Function('document', 'daysSince', 'staleDays', 'rangeCutoff', 'fmt',
  source.slice(start, end) + '\nreturn card; }\nreturn renderCard;')(
  {createElement: () => new Element()}, () => 300, () => null, () => '0000-00-00', String);
const doc = JSON.parse(fs.readFileSync('data/commodities/comm_copper_shfe_inventory.json', 'utf8'));
const card = render(doc, doc.id);
assert(card.children.some(e => e.textContent.includes('최신 자료 미확보')));
assert(card.children.some(e => e.textContent.includes('전주 대비')));
assert(card.children.some(e => e.textContent.includes('4주 변화')));
const sparse = {...doc, series: {stock: [['2025-09-26', 100]]}, weekly_changes: [['2025-09-26', 100]]};
const missing = render(sparse, sparse.id);
assert(missing.children.some(e => e.textContent.includes('4주 변화 자료 없음')));
assert(!missing.children.some(e => e.innerHTML.includes('Infinity') || e.innerHTML.includes('NaN')));
const regular = render({...sparse, inventory_summary: false, data_stale_days: undefined}, sparse.id);
assert(!regular.children.some(e => e.textContent.includes('최신 자료 미확보')));
console.log('PASS: stale inventory, weekly change, missing 4-week baseline, zero baseline and ordinary cards');
