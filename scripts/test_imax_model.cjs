const fs=require('node:fs'),assert=require('node:assert/strict');
(async()=>{
 const source=fs.readFileSync('assets/imax-model.js','utf8');
 const {numeric,filmEstimate,annualEstimate,odysseyEstimate}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
 const near=(a,b)=>assert.ok(Math.abs(a-b)<1e-6,`${a} != ${b}`);
 assert.equal(numeric(''),null);assert.equal(numeric(' '),null);assert.equal(numeric('Infinity'),null);assert.equal(numeric('0'),0);
 const film={include:true,title:'Example',worldwide:1000,imax_pct:10,in_year_pct:35,direct_imax:null};
 near(filmEstimate(film).gbo,35); // calendar-year fraction is not lifetime gross
 near(filmEstimate({...film,direct_imax:200}).gbo,70); // override replaces, never adds
 near(filmEstimate({...film,worldwide:0}).gbo,0);
 assert.equal(filmEstimate({...film,worldwide:null}).gbo,null);
 assert.equal(filmEstimate({...film,imax_pct:101}).gbo,null);
 assert.equal(filmEstimate({...film,in_year_pct:-1}).gbo,null);
 assert.equal(filmEstimate({...film,direct_imax:'bad'}).gbo,null);
 assert.equal(filmEstimate({...film,regional_only:true}).gbo,null);
 near(filmEstimate({...film,regional_only:true,direct_imax:50}).gbo,17.5);
 near(filmEstimate({...film,include:false,worldwide:null}).gbo,0);
 const doc=JSON.parse(fs.readFileSync('data/movies/imax_model.json','utf8')),p=doc.periods['2027'],a=doc.facts.annual_2025;
 // Reproduce an independently reported full year from component disclosures.
 const base={...p.params,residual:a.gbo};
 const backtest=annualEstimate(p,[],base);assert.equal(backtest.complete,true);
 near(backtest.dmr,a.dmr);near(backtest.rentals,a.rentals);near(backtest.total.revenue,a.revenue);
 near(backtest.total.gross,a.gross);near(backtest.total.profit,a.profit);
 assert.equal(backtest.equity,null);assert.equal(backtest.value,null); // NCI cannot be silently omitted
 const v=annualEstimate(p,[],{...base,nci:100,debt:250,cash:200,shares:50,multiple:10,price:20});
 near(v.ev,a.profit*10);near(v.equity,a.profit*10-150);near(v.value,v.equity/50);near(v.upside,v.value/20-1);
 const negative=annualEstimate(p,[],{...base,nci:10000});assert.ok(negative.equity<0);assert.equal(negative.value,null);assert.equal(negative.upside,null);
 assert.equal(annualEstimate(p,[],{...base,shares:0}).complete,false);
 assert.equal(annualEstimate(p,[],{...base,opex:null}).complete,false);
 assert.equal(annualEstimate(p,[{...film,worldwide:null}],base).complete,false);
 const loss=annualEstimate(p,[],{...base,opex:1000,nci:100});assert.equal(loss.ev,null);assert.equal(loss.value,null);
 const current=doc.periods['2026'],rows=current.films.map(f=>({...f,...f.defaults}));
 const low=annualEstimate(current,rows,current.params,.8),mid=annualEstimate(current,rows,current.params),high=annualEstimate(current,rows,current.params,1.2);
 near(low.actual.profit,105.601);near(high.actual.revenue,358.773);
 near(low.total.gbo-current.actual.gbo,(mid.total.gbo-current.actual.gbo)*.8);
 near(high.total.revenue-current.actual.revenue-high.dmr-high.rentals,low.total.revenue-current.actual.revenue-low.dmr-low.rentals);
 assert.ok(!current.films.some(f=>f.id==='/movie/Odyssey-The-(2026)')); // later reissue cannot reimport its lifetime
 assert.ok(!current.films.some(f=>f.id==='/movie/Avengers-Doomsday-(2026)'));
 assert.ok(p.films.some(f=>f.regional_only&&f.date===null));
 const o=odysseyEstimate(doc.facts,p.params);near(o.typicalDmr,67.25);
 near(o.revenue,538*(90.389+41.436)/712.1);
 assert.equal(odysseyEstimate(doc.facts,{...p.params,odyssey_extra_cost:null}),null);
 assert.equal(annualEstimate(p,[],{...base,odyssey_extra_cost:null}).complete,true);
 near(o.revenue,o.dmr+o.rentals);near(o.profit,o.gross);
 near(odysseyEstimate(doc.facts,{...p.params,odyssey_extra_cost:5}).profit,o.profit-5);
 assert.equal(doc.facts.odyssey.movie_revenue_disclosed,false);assert.equal(doc.facts.odyssey.movie_profit_disclosed,false);
 assert.ok(!source.includes('innerHTML'));
 assert.ok(fs.readFileSync('assets/app.js','utf8').includes('section.table_kind === "imax_model"'));
 console.log('IMAX annual reconciliation, year cutoff, missing inputs, direct override, China scope, NCI bridge and Odyssey attribution passed');
})().catch(e=>{console.error(e);process.exit(1)});
