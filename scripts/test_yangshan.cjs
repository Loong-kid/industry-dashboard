const fs = require('node:fs');
const assert = require('node:assert/strict');
const source = fs.readFileSync('assets/app.js', 'utf8');
const code = source.slice(source.indexOf('function drawChart('), source.indexOf('\n// ── 수주 테이블'));
const state = {charts: []};
class Chart { constructor(canvas, config) { this.config = config; } }
const draw = new Function('Chart', 'SERIES_COLORS', 'isDark', 'css', 'fmt', 'state', 'crosshair',
  code + '\nreturn drawChart;')(Chart, {light:['blue']}, () => false, () => '', String, state, {});
const rows = [['2026-07-23',100],['2026-09-28',121],['2026-09-29',123]];
const chart = draw({}, {highlight_gaps:true}, {premium:rows});
const segment = chart.config.data.datasets[0].segment;
assert.deepEqual(segment.borderDash({p0DataIndex:0,p1DataIndex:1}), [5,5]);
assert.equal(segment.borderDash({p0DataIndex:1,p1DataIndex:2}), undefined);
assert.equal(draw({}, {}, {premium:rows}).config.data.datasets[0].segment, undefined);
assert.deepEqual(chart.config.data.datasets[0].data, [100,121,123]);
console.log('PASS: long gaps dashed, normal dates solid, no generated data, other charts unchanged');
