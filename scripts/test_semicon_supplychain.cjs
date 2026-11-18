const assert=require('node:assert/strict');
const fs=require('node:fs');
(async()=>{
 const source=fs.readFileSync('assets/semicon-supplychain.js','utf8');
 const {companiesForTab}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
 const companies=Object.entries(JSON.parse(fs.readFileSync('manual/semicon-supplychain/companies.json')).companies).map(([id,c])=>({id,...c}));
 const doc={companies};
 for(const [tab,count] of Object.entries({process_chemicals:4,specialty_gases:2,test_components:3,package_substrates:2,equipment_infrastructure:2,equipment_summary:9,equipment_frontend:2,equipment_testing:3,equipment_inspection:2}))assert.equal(companiesForTab(doc,tab).length,count,tab);
 assert.deepEqual(companiesForTab(null,'anything'),[]);
 assert.equal(companiesForTab(doc,'snstech').length,0);
 assert(!source.includes('innerHTML'));
 console.log('Supplier overview filters: passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
