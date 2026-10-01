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
const daily = render({...sparse, inventory_summary: false, stock_summary: true, daily_changes: [['2025-09-26', -10]]}, sparse.id);
assert(daily.children.some(e => e.textContent.includes('전 거래일 대비 -10')));
const snapshot = render({...sparse, inventory_summary: false, snapshot_history: true}, sparse.id);
assert(snapshot.children.some(e => e.textContent.includes('최신값 1개')));
const history = render({...sparse, inventory_summary: false, snapshot_history: true,
  series: {stock: [['2025-09-25', 90], ['2025-09-26', 100]]},
  history_note: '공개 과거 자료 포함', history_source: 'Westmetall',
  history_source_url: 'https://www.westmetall.com/', history_csv: 'data/history.csv'}, sparse.id);
assert(history.children.some(e => e.textContent.includes('공개 과거 자료 포함')));
assert(history.children.some(e => e.innerHTML.includes('원단위 CSV')));
console.log('PASS: stale inventory, weekly change, missing 4-week baseline, zero baseline and ordinary cards');
