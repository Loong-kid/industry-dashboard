// 그래프 카드 너비 조절: 배치 계산과 전 탭 연결 시험.
const fs = require('node:fs');
const assert = require('node:assert/strict');
const {MIN_WIDTH, clampWidth, columnSpan, spanBasis} = require('../assets/card-resize.js');

assert.equal(clampWidth(100, MIN_WIDTH, 1000), MIN_WIDTH, '너무 좁게 끌면 최소 너비');
assert.equal(clampWidth(5000, MIN_WIDTH, 1000), 1000, '격자보다 넓어지지 않음');
assert.equal(clampWidth(640.4, MIN_WIDTH, 1000), 640);
assert.equal(clampWidth(500, MIN_WIDTH, 280), 280, '격자가 최소 너비보다 좁으면 격자 너비');

assert.equal(columnSpan('auto', 'auto', 3), 1);
assert.equal(columnSpan('span 2', 'auto', 3), 2, '.card-wide');
assert.equal(columnSpan('auto', 'span 2', 3), 2);
assert.equal(columnSpan('span 2', 'auto', 1), 1, '칸 수를 넘지 않음');
assert.equal(columnSpan('1', '-1', 3), 'full', '.order-table-card');

assert.equal(spanBasis(1, 541, 14), 541);
assert.equal(spanBasis(2, 541, 14), 1096);

const html = fs.readFileSync('index.html', 'utf8');
assert.ok(html.includes('src="assets/card-resize.js"'), 'index.html이 모듈을 불러옴');
const css = fs.readFileSync('assets/style.css', 'utf8');
for (const name of ['.card-resize-handle', '.card-resize-free', '.card-resizable']) {
  assert.ok(css.includes(name), `style.css에 ${name}`);
}
assert.ok(fs.readFileSync('assets/darpa.js', 'utf8').includes('dp-card-wrap'), 'DARPA 카드 감싸기');
console.log('card resize OK');
