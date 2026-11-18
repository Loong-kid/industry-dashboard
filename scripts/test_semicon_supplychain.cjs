const assert=require('node:assert/strict');
const fs=require('node:fs');
(async()=>{
 const source=fs.readFileSync('assets/semicon-supplychain.js','utf8');
 const {companiesForTab}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
 const companies=Object.entries(JSON.parse(fs.readFileSync('manual/semicon-supplychain/companies.json')).companies).map(([id,c])=>({id,...c}));
 const doc={companies};
 for(const [tab,count] of Object.entries({process_chemicals:5,specialty_gases:2,test_components:5,package_substrates:2,equipment_infrastructure:4,equipment_summary:12,equipment_frontend:2,equipment_testing:3,equipment_inspection:3,plasma_components:1,pcb_boards:1}))assert.equal(companiesForTab(doc,tab).length,count,tab);
 assert.deepEqual(companiesForTab(null,'anything'),[]);
 assert.equal(companiesForTab(doc,'snstech').length,0);
 assert(!source.includes('innerHTML'));
 console.log('Supplier overview filters: passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
