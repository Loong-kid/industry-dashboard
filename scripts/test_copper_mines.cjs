'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const mines = require('../assets/copper-mines.js');
const doc = JSON.parse(fs.readFileSync('data/commodities/comm_copper_mines.json', 'utf8'));
const f = {year:'latest',sort:'production',dir:-1};
const byId = id => doc.rows.find(r => r.id === id);
assert.deepEqual(mines.filter(doc.rows,{...f,search:'CHILE nonexistent'}), []);
assert.deepEqual(mines.filter(doc.rows,{...f,search:'escondida bhp'}).map(r=>r.id), ['escondida']);
assert(mines.filter(doc.rows,{...f,country:'칠레',owner:'BHP'}).every(r => r.country === '칠레' && r.owners.some(o=>o.name==='BHP')));
assert.deepEqual(mines.filter(doc.rows,{...f,coverage:'cumulative'}).map(r=>r.id).sort(), ['kamoa_kakula','panguna']);
assert.equal(mines.annual(byId('spence'), '2025'), undefined);
assert.equal(mines.annual(byId('spence'), 'latest').year, 2026);
assert.equal(mines.annual(byId('escondida'), '2025').period, 'fiscal');
const rows = mines.sort(doc.rows, f);
assert.equal(rows[0].id,'escondida');
const missing = rows.findIndex(r => !mines.annual(r, f.year));
assert(rows.slice(missing).every(r => !mines.annual(r, f.year)));
const ascending = mines.sort(doc.rows, {...f,dir:1});
assert(ascending.slice(-1)[0].production.length === 0);
const reserves = mines.sort(doc.rows, {...f,sort:'reserves'});
assert(reserves.findIndex(r => r.reserves?.cu_tonnes != null) < reserves.findIndex(r => r.reserves?.unit==='Mt ore'));

// Parse quoted CSV fields (including embedded commas, quotes and multiline text).
function parse(csv) {
  const lines=[]; let row=[], value='', quoted=false;
  for(let i=0;i<csv.length;i++) {
    const c=csv[i];
    if(c==='"') {if(quoted && csv[i+1]==='"') {value+='"';i++;} else quoted=!quoted;}
    else if(c===','&&!quoted) {row.push(value);value='';}
    else if(c==='\n'&&!quoted) {row.push(value.replace(/\r$/,''));lines.push(row);row=[];value='';}
    else value+=c;
  }
  if(value||row.length) {row.push(value);lines.push(row);}
  return lines;
}
const hostile = {...byId('morenci'), name:'=HYPERLINK("bad", "test")', note:'comma, quote " and\nnew line'};
const csv = mines.csv(doc,[hostile,byId('kamoa_kakula'),byId('los_pelambres')],f.year);
assert(csv.startsWith('\uFEFF'));
const parsed = parse(csv.slice(1));
assert.equal(parsed.length,4);
assert(parsed.every(row=>row.length===parsed[0].length));
assert(parsed[1][1].startsWith("'=HYPERLINK"));
const col=name=>parsed[0].indexOf(name);
assert.equal(parsed[2][col('전생애누적_t_Cu')],'1658834');
assert.equal(parsed[3][col('매장량_t_Cu')],'');
assert.equal(parsed[3][col('매장량원문단위')],'Mt ore');
assert.equal(JSON.parse(parsed[2][col('연간생산이력_JSON')]).length,5);
assert(parsed[2][col('출처')].includes('31_december_2022'));
console.log('PASS: mine search, filters, FY/CY, missing-last sorting, complete lifetime and safe CSV round-trip');
