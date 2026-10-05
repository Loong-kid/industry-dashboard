const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');

class Element {
  constructor(tag) { this.tagName = tag; this.children = []; this.listeners = {}; this.textContent = ''; this.innerHTML = ''; }
  appendChild(el) { this.children.push(el); return el; }
  append(...els) { els.forEach(el => this.appendChild(el)); }
  replaceChildren(...els) { this.children = els; }
  setAttribute(key, value) { this[key] = value; }
  addEventListener(key, callback) { this.listeners[key] = callback; }
}
const context = vm.createContext({document: {createElement: tag => new Element(tag)}, state: {}, URL, console});
vm.runInContext(fs.readFileSync('assets/korea-datacenter.js', 'utf8'), context);
const doc = JSON.parse(fs.readFileSync('data/datacenter/dc_facilities.json', 'utf8'));
const baseline = JSON.parse(fs.readFileSync('manual/korea_datacenter_baseline.json', 'utf8'));
assert.equal(baseline.facilities.length, doc.summary.baseline_rows);
assert(baseline.facilities.length > 0);
assert.equal(new Set(baseline.facilities.map(r => r.id)).size, baseline.facilities.length);
for (const original of baseline.facilities) {
  const row = doc.records.find(r => r.id === original.id);
  assert(row);
  for (const field of ['capacity','capacity_text','it_load','owner','tenant','contractor','notes','url','cell_notes']) {
    assert.deepEqual(row[field], original[field], `Preserve manual ${field}`);
  }
  if (original.area != null) assert.equal(row.area, original.area);
}
const card = context.renderKoreaDataCenters(doc);
const filters = card.children.find(c => c.className.includes('dc-toolbar'));
const selects = filters.children.filter(c => c.className === 'ti-filter').map(c => c.children[0]);
const wrap = card.children.find(c => c.className === 'order-table-wrap dc-table');
const body = () => wrap.children[0].children.at(-1);
assert.equal(body().children.length, doc.summary.tracked_rows);
selects[0].value = 'candidate'; selects[0].listeners.change();
assert.equal(body().children.length, doc.summary.candidate_rows);
selects[0].value = 'confirmed'; selects[0].listeners.change();
selects[1].value = '경기도'; selects[1].listeners.change();
assert(body().children.every(tr => tr.children[1].children[1].textContent.startsWith('경기도')));
selects[1].value = ''; selects[1].listeners.change();
const search = filters.children.at(-1).children[0];
search.value = 'no-centre-matches-this-query'; search.listeners.input();
assert.equal(body().children.length, 1);
assert(body().children[0].children[0].textContent.includes('없습니다'));
search.value = ''; search.listeners.input();
const head = () => wrap.children[0].children.find(c => c.tagName === 'thead').children[0];
head().children[6].children[0].listeners.click();
const maximum = Math.max(...doc.records.filter(r => r.classification === 'confirmed').map(r => r.capacity ?? -1));
assert.equal(body().children[0].children[6].textContent, maximum.toLocaleString('ko-KR', {maximumFractionDigits: 2}));
selects[4].value = 'schedule'; selects[4].listeners.change();
assert.equal(head().children.length, 10);
selects[4].value = 'parties'; selects[4].listeners.change();
assert.equal(head().children.length, 7);
const quick = card.children.find(c => c.className === 'dc-quick');
quick.children[2].listeners.click();
assert(body().children.every(tr => !context.dcOwnerKnown(doc.records.find(r => r.id === tr['data-id']))));
assert.equal(context.dcOwnerKnown({owner: '?'}), false);
assert.equal(context.dcOwnerKnown({owner: ' '}), false);
assert.equal(context.dcOwnerKnown({owner: '', research: {stakeholders: [{role:'operator',name:'Some operator'}]}}), false);
quick.children[0].listeners.click();
const watch = body().children[0].children[0].children[0];
watch.listeners.click();
assert.equal(watch['aria-pressed'], 'true');
quick.children[4].listeners.click();
assert.equal(body().children.length, 1);
assert(body().children[0]['data-id']);
quick.children[0].listeners.click();
assert.equal(context.dcProvenance({id:'baseline-starts'}), '사용자 엑셀 · Raw 탭');
assert.equal(context.dcProvenance({id:'1897'}), '국토부 · 신규 다운로드');
assert.equal(context.dcProvenance({provenance:'research'}), '기업·공공기관 조사');
for (const row of doc.records) if (row.research) {
  assert(row.research.checked <= '2026-10-05');
  if (row.research.stakeholders.length || row.research.update) assert(row.research.sources.length);
  for (const source of row.research.sources) assert(['https:', 'http:'].includes(new URL(source.url).protocol));
}
const stt = doc.records.find(r => r.id === 'dc-7db78ab95b975d84');
assert.equal(context.dcDisplayStage(stt), '운영');
assert.equal(context.dcIsActive(stt), false);
assert.equal(context.dcIsActive(doc.records.find(r => r.id === 'dc-fba02649999065fb')), true);
assert.equal(context.dcIsActive({...stt, research: null, dates: {...stt.dates, completion: {kind: 'missing'}, start: {kind: 'missing'}, alteration: {kind: 'missing'}, permit: {kind: 'missing'}}}), false);
assert.equal(stt.dates.completion.date, '2025-06-26');
assert.equal(context.dcParty(stt).role, '시행사');
assert.equal(context.dcDate({text: '2027.4Q', date: null, kind: 'planned'}), '2027.4Q · 예정');
assert.equal(context.dcDate({text: '2022?', date: null, kind: 'uncertain'}), '2022? · 날짜 미확정');
const review = context.renderKoreaDataCenterChanges(doc);
const reviewWrap = review.children.find(c => c.className === 'order-table-wrap');
assert.equal(reviewWrap.children[0].children[1].children.length, doc.summary.review || 1);
const select = review.children.find(c => c.className === 'order-filters').children[0].children[0];
select.value = 'applied'; select.listeners.change();
assert.equal(reviewWrap.children[0].children[1].children.length, doc.summary.applied || 1);
const unsafe = structuredClone(doc);
unsafe.records = [{...unsafe.records[0], name: '<img src=x onerror=alert(1)>', url: 'javascript:alert(1)', classification: 'confirmed'}];
context.state.dcFilters = undefined;
const unsafeCard = context.renderKoreaDataCenters(unsafe);
const nameCell = unsafeCard.children.find(c => c.className === 'order-table-wrap dc-table').children[0].children.at(-1).children[0].children[1];
assert.equal(nameCell.children[0].textContent, unsafe.records[0].name);
assert.equal(nameCell.children[0].innerHTML, '');
assert.equal(context.dcLink('javascript:alert(1)', 'unsafe').tagName, 'span');
const catalog = JSON.parse(fs.readFileSync('data/catalog.json', 'utf8'));
const industry = catalog.industries.find(i => i.id === 'datacenter');
assert(industry.sections.some(s => s.table_kind === 'dc_facilities'));
for (const section of industry.sections) for (const id of section.indicators) assert(fs.existsSync(`data/datacenter/${id}.json`));
console.log('PASS: manual preservation, table views, filters, favorites, sorting, source provenance, researched roles, administrative dates and safe text/links');
