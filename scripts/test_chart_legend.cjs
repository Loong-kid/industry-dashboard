const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
let plugin;
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../assets/chart-legend.js'),'utf8'),{window:{Chart:{register:p=>{plugin=p;}}}});
const items=[{datasetIndex:0,text:'Actual',hidden:false,lineDash:[],pointStyle:'circle'},
  {datasetIndex:1,text:'Average',hidden:true,lineDash:[1,1],pointStyle:'circle'},
  {datasetIndex:2,text:'Capex',hidden:false,fillStyle:'#f90',lineDash:[5,4]},
  {datasetIndex:3,text:'Auction',pointStyle:'triangle',hidden:false}];
const original=()=>items;
const metas=[
  {type:'line',controller:{options:{showLine:true},getStyle:()=>({borderColor:'#27d',borderWidth:2,borderDash:[]})}},
  {type:'line',controller:{options:{showLine:true},getStyle:()=>({borderColor:'#186',borderWidth:2,borderDash:[5,4],borderDashOffset:1})}},
  {type:'bar',controller:{options:{}}},
  {type:'line',controller:{options:{showLine:false}}},
];
const chart={config:{type:'line'},options:{plugins:{legend:{display:true,labels:{boxWidth:10,generateLabels:original}}}},data:{datasets:[{},{},{type:'bar'},{showLine:false}]},getDatasetMeta:i=>metas[i]};
plugin.beforeUpdate(chart);
const labels=chart.options.plugins.legend.labels;
const result=labels.generateLabels(chart);
assert.equal(labels.usePointStyle,true);assert.equal(labels.pointStyleWidth,12);
assert.equal(result[0].pointStyle,'line');assert.equal(result[0].lineWidth,2);
assert.equal(result[1].pointStyle,'line');assert.deepEqual(result[1].lineDash,[5,4]);assert.equal(result[1].strokeStyle,'#186');assert.equal(result[1].hidden,true);
assert.equal(result[2].pointStyle,'rect');assert.equal(result[2].fillStyle,'#f90');assert.equal(result[2].lineDash.length,0);
assert.equal(result[3].pointStyle,'triangle');assert.equal(items[1].pointStyle,'circle');
for(let i=0;i<20;i++){plugin.beforeUpdate(chart);assert.equal(labels.generateLabels(chart).length,4);}
chart.data.datasets[3].showLine=true;plugin.beforeUpdate(chart);assert.equal(labels.pointStyleWidth,24);chart.data.datasets[3].showLine=false;
// Replacing a custom generator must be respected, while avoiding nested wrappers.
labels.generateLabels=()=>[items[1]];plugin.beforeUpdate(chart);assert.equal(labels.generateLabels(chart).length,1);
const hidden={config:{type:'line'},options:{plugins:{legend:{display:false,labels:{generateLabels:original}}}}};plugin.beforeUpdate(hidden);assert.equal(hidden.options.plugins.legend.labels.generateLabels,original);
const pie={config:{type:'pie'},options:{plugins:{legend:{labels:{generateLabels:original}}}}};plugin.beforeUpdate(pie);assert.equal(pie.options.plugins.legend.labels.generateLabels,original);
plugin.afterDestroy(chart);
const html=fs.readFileSync(path.join(__dirname,'../index.html'),'utf8');assert.ok(html.indexOf('assets/chart-legend.js')>html.indexOf('chart.umd.min.js'));
console.log('PASS common legend line/dash/bar/point samples, hidden series, updates and pie/custom-legend preservation');
