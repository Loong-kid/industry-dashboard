/* Treasury plans are publication vintages; auction observations are events. */
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const fmt=(v,d=2)=>v==null?'—':Number(v).toLocaleString('ko-KR',{maximumFractionDigits:d});
export const TERMS=['2-Year','3-Year','5-Year','7-Year','10-Year','20-Year','30-Year'];
const termLabel=t=>t.replace('-Year','년물');
const colors=['#2878d4','#15866e','#d18c1b','#8972ca'];
const prefs={term:'10-Year',range:'5',vintage:null,history:false,small:false};
export function trailing(rows,key,n=12){return rows.map((_,i)=>{const vs=rows.slice(Math.max(0,i-n+1),i+1).map(r=>r[key]);return vs.length===n&&vs.every(v=>v!=null)?vs.reduce((a,b)=>a+b,0)/n:null;});}
export function inRange(rows,range){if(range==='all'||!rows.length)return rows;const end=rows.at(-1).date;const cutoff=Number(end.slice(0,4))-Number(range);return rows.filter(r=>r.date>=`${cutoff}${end.slice(4)}`);}
export function borrowingSeries(vintages){
  const quarters=new Map();
  for(const v of [...vintages].sort((a,b)=>a.publication_date.localeCompare(b.publication_date)))for(const r of v.rows){
    const entry=quarters.get(r.quarter)||{quarter:r.quarter,first:null,latest:null,actual:null};
    const observation={...r,date:v.publication_date,url:v.source_url};
    if(r.status==='actual')entry.actual=observation;else{entry.first??=observation;entry.latest=observation;}
    quarters.set(r.quarter,entry);
  }
  return [...quarters.values()].sort((a,b)=>a.quarter.localeCompare(b.quarter));
}
export function monthlyActual(rows,month,term){const found=rows.filter(r=>r.completed&&!r.small_value&&r.date.slice(0,7)===month&&r.term===term);return found.length?found.reduce((sum,r)=>sum+r.amount,0):null;}

export function mount(root,{view='qra',tabsRoot}={}){
  let disposed=false,charts=[],docs={},page=0;
  if(!['qra','auctions','yields'].includes(view))view='qra';
  const box=document.createElement('div');box.className='ust-root';root.append(box);
  if(tabsRoot){tabsRoot.innerHTML='';const nav=document.createElement('nav');nav.className='commodity-tabs ust-tabs';nav.setAttribute('aria-label','미국 국채 세부탭');tabsRoot.append(nav);for(const [id,name] of [['qra','발행계획'],['auctions','입찰 수급'],['yields','시장금리']]){const a=document.createElement('a');a.href=`#/macro/us_treasury/${id}`;a.textContent=name;a.className='ust-tab'+(id===view?' active':'');if(id===view)a.setAttribute('aria-current','page');nav.append(a);}}
  box.innerHTML='<p class="page-loading">미국 재무부 공식 자료를 불러오는 중…</p>';
  const destroy=()=>{for(const c of charts)c.destroy();charts=[];};
  const source=(url,label='공식 원문')=>`<a href="${esc(url)}" target="_blank" rel="noopener">${esc(label)}</a>`;
  const stale=d=>d&&!d.ok?'<p class="ust-warning">최근 수집 실패 · 마지막 성공 자료를 표시합니다.</p>':'';
  const selectedRows=()=>docs.auctions.rows.filter(r=>r.completed&&r.term===prefs.term&&(prefs.small||!r.small_value));
  function chart(title,labels,series,unit,{type='line',stacked=false,note=''}={}){
    const card=document.createElement('section');card.className='ust-card';card.innerHTML=`<h3>${esc(title)}</h3><div class="ust-chart"><canvas role="img" aria-label="${esc(title)}"></canvas></div>${note?`<p class="ust-note">${note}</p>`:''}`;box.querySelector('.ust-grid').append(card);
    if(!window.Chart)return;
    const tickColor=getComputedStyle(box).getPropertyValue('--ink-2').trim()||'#777';
    const c=new window.Chart(card.querySelector('canvas'),{type,data:{labels,datasets:series.map((s,i)=>({label:s.label,data:s.data,borderColor:colors[i%4],backgroundColor:type==='bar'?colors[i%4]+'b3':colors[i%4],borderWidth:type==='bar'?0:2,pointRadius:labels.length>40?0:2,pointHoverRadius:4,spanGaps:false,tension:0,...s}))},options:{responsive:true,maintainAspectRatio:false,animation:false,interaction:{mode:'index',intersect:false},plugins:{legend:{position:'bottom',labels:{boxWidth:10,color:tickColor}},tooltip:{filter:item=>item.raw!=null,callbacks:{label:ctx=>`${ctx.dataset.label}: ${fmt(ctx.parsed.y)} ${unit}`}}},scales:{x:{stacked,grid:{display:false},ticks:{maxTicksLimit:6,maxRotation:0,color:tickColor}},y:{stacked,beginAtZero:type==='bar',ticks:{color:tickColor,callback:v=>fmt(v)},grid:{color:'rgba(130,130,130,.15)'}}}}});charts.push(c);
  }
  function header(title,note,doc){
    box.innerHTML=`<div class="ust-intro"><h2>${esc(title)}</h2><p>${note}</p></div>${stale(doc)}<div class="ust-controls"></div><div class="ust-summary"></div><div class="ust-grid"></div><div class="ust-detail"></div>`;
  }
  function summary(items){box.querySelector('.ust-summary').innerHTML=items.map(([label,value,note])=>`<div><span>${esc(label)}</span><strong>${esc(value)}</strong><small>${esc(note||'')}</small></div>`).join('');}
  function controls(extra=''){
    box.querySelector('.ust-controls').innerHTML=`<label>만기 <select aria-label="국채 만기" id="ust-term">${TERMS.map(t=>`<option value="${t}" ${t===prefs.term?'selected':''}>${termLabel(t)}</option>`).join('')}</select></label><label>${view==='qra'?'분기 추이 기간':'기간'} <select aria-label="국채 표시 기간" id="ust-range">${[['1','1년'],['3','3년'],['5','5년'],['all','전체 · 2014년부터']].map(([v,l])=>`<option value="${v}" ${prefs.range===v?'selected':''}>${l}</option>`).join('')}</select></label>${extra}`;
    box.querySelector('#ust-term').onchange=e=>{prefs.term=e.target.value;page=0;render();};
    const range=box.querySelector('#ust-range');if(range)range.onchange=e=>{prefs.range=e.target.value;page=0;render();};
  }
  function table(target,caption,heads,rows){target.innerHTML=`<div class="ust-table" tabindex="0" role="region" aria-label="${esc(caption)}"><table><caption>${esc(caption)}</caption><thead><tr>${heads.map(h=>`<th scope="col">${h}</th>`).join('')}</tr></thead><tbody>${rows.map(cells=>`<tr>${cells.map((c,i)=>i===0?`<th scope="row">${c}</th>`:`<td>${c}</td>`).join('')}</tr>`).join('')||`<tr><td colspan="${heads.length}">공개 자료가 없습니다.</td></tr>`}</tbody></table></div>`;}
  function renderQra(){
    const doc=docs.qra;const vintages=doc.statements;const vintage=vintages.find(v=>v.publication_date===prefs.vintage)||vintages.at(-1);prefs.vintage=vintage.publication_date;
    const borrowing=borrowingSeries(doc.borrowing);const latest=doc.borrowing.at(-1);const forecasts=latest.rows.filter(r=>r.status==='estimate');
    header('미국 국채 발행계획','QRA 분기 순차입계획과 만기별 월간 경매 규모 · 금액: 십억 달러',doc);
    controls(`<label>월간 발행계획 발표본 <select id="ust-vintage" aria-label="QRA 발표본">${[...vintages].reverse().map(v=>`<option value="${v.publication_date}" ${v===vintage?'selected':''}>${v.publication_date}</option>`).join('')}</select></label>`);
    box.querySelector('#ust-vintage').onchange=e=>{prefs.vintage=e.target.value;render();};
    summary(forecasts.slice(0,2).map(r=>[`최신 · ${r.quarter} 순차입 예상`,`${fmt(r.borrowing)} 십억 $`,`발표 ${latest.publication_date}`]).concat([[`${forecasts.at(-1)?.quarter||''} 기말 TGA 목표`,`${fmt(forecasts.at(-1)?.cash)} 십억 $`,'분기 말 목표 · 일별 실제 잔고와 구분']]));
    const recent=inRange(borrowing.map(r=>({...r,date:`${r.quarter.slice(0,4)}-${String(Number(r.quarter.at(-1))*3).padStart(2,'0')}-01`})),prefs.range);const xs=recent.map(r=>r.quarter);
    chart('분기 순차입 · 계획과 실제',xs,[{label:'최초 예상',data:recent.map(r=>r.first?.borrowing??null)},{label:'최종 예상',data:recent.map(r=>r.latest?.borrowing??null)},{label:'실제',data:recent.map(r=>r.actual?.borrowing??null)}],'십억 $',{type:'bar',note:'순차입은 차환을 포함한 총발행액과 다릅니다. 분기는 달력연도 기준입니다.'});
    chart('분기 말 현금잔고 · TGA',xs,[{label:'최종 목표',data:recent.map(r=>r.latest?.cash??null),borderDash:[5,4]},{label:'실제',data:recent.map(r=>r.actual?.cash??null)}],'십억 $');
    const monthly=vintage.monthly.filter(r=>r.term===prefs.term);const months=monthly.map(r=>r.month);
    chart(`${termLabel(prefs.term)} 월간 경매 규모`,months,[{label:'해당 발표본의 계획',data:monthly.map(r=>r.status==='plan'?r.amount:null)},{label:'QRA에 기재된 과거 실적',data:monthly.map(r=>r.status==='reported_actual'?r.amount:null)},{label:'경매 결과로 확인된 실제',data:monthly.map(r=>monthlyActual(docs.auctions.rows,r.month,prefs.term))}],'십억 $',{type:'bar',note:`${source(vintage.source_url,`${vintage.publication_date} 발표본`)} · 계획은 발표 당시 값으로 보존합니다. ${monthly.length?'':'이 발표본은 구조화된 월별 만기 표가 없습니다.'}`});
    const matrix=document.createElement('section');matrix.className='ust-card';box.querySelector('.ust-grid').append(matrix);
    const allMonths=[...new Set(vintage.monthly.map(r=>r.month))];
    table(matrix,'만기별 발행규모 · 십억 달러',['월·기준',...TERMS.map(termLabel)],allMonths.map(m=>[`${m} ${m>=vintage.publication_date.slice(0,7)?'계획':'기재 실적'}`,...TERMS.map(t=>fmt(vintage.monthly.find(r=>r.month===m&&r.term===t)?.amount,0))]));
    const detail=box.querySelector('.ust-detail');detail.innerHTML=`<p class="ust-note">${source(doc.calendar_url,'공식 향후 경매 일정')} · 월간 규모는 명목 고정금리 중장기 국채입니다. 단기물·TIPS·FRN을 합산한 전체 국채 발행액과 구분합니다.</p><section class="ust-calendar"><h3>최신 잠정 경매 일정 · ${termLabel(prefs.term)}</h3><div id="ust-calendar-table"></div></section><details ${prefs.history?'open':''}><summary>전체 분기 계획·실제 이력 · 2014년부터</summary><div id="ust-borrowing-table"></div></details><details><summary>출처와 집계 기준</summary><p>순차입: 민간보유 시장성 국채 기준. SOMA 차환 추가 배정을 제외하고 SOMA 만기상환에 필요한 자금조달은 포함합니다. 음수는 순상환입니다. 최초·최종 예상은 수집한 QRA 발표본 기준입니다.</p><p>발행규모의 실제 값은 경매일이 속한 월의 공모액입니다. TGA는 해당 분기 말 예상·실제이며 일별 현재 잔고가 아닙니다.</p><p>${source(latest.source_url,'최신 차입계획')} · ${source(vintage.source_url,'선택한 QRA 발표문')}</p><p>마지막 성공 확인 ${doc.fetched} · 최근 확인 ${doc.checked}</p></details>`;
    const upcoming=(doc.calendar||[]).filter(r=>r.date>=doc.checked&&r.term===prefs.term);
    table(box.querySelector('#ust-calendar-table'),`일정은 잠정 · ${vintages.at(-1).publication_date} QRA 기준`,['경매 예정일','공고 예정일','발행·결제 예정일','구분','예정액 · 십억 $'],upcoming.map(r=>[r.date,esc(r.announcement_date||'—'),esc(r.issue_date||'—'),r.reopening?'재발행':'신규',fmt(vintages.at(-1).monthly.find(v=>v.month===r.date.slice(0,7)&&v.term===r.term)?.amount)]));
    table(box.querySelector('#ust-borrowing-table'),'분기 순차입 이력 · 십억 달러',['분기','최초 예상','최종 예상','실제','실제−최종 예상','기말 TGA 목표','기말 TGA 실제','출처'],[...borrowing].reverse().map(r=>[r.quarter,fmt(r.first?.borrowing),fmt(r.latest?.borrowing),fmt(r.actual?.borrowing),fmt(r.actual&&r.latest?r.actual.borrowing-r.latest.borrowing:null),fmt(r.latest?.cash),fmt(r.actual?.cash),source((r.actual||r.latest).url)]));
    detail.querySelector('details').ontoggle=e=>{prefs.history=e.target.open;};
  }
  function renderAuctions(){
    const doc=docs.auctions,all=selectedRows(),rows=inRange(all,prefs.range),last=all.at(-1),roll=trailing(all,'bid_to_cover');
    header(`${termLabel(prefs.term)} 입찰 수급`,'10년물은 통상 월 1회 경매 · 신규 발행과 재발행을 함께 표시합니다.',doc);controls(`<label><input id="ust-small" type="checkbox" ${prefs.small?'checked':''}>소액 경매 포함</label>`);
    box.querySelector('#ust-small').onchange=e=>{prefs.small=e.target.checked;page=0;render();};
    const upcoming=doc.rows.filter(r=>r.term===prefs.term&&!r.completed&&r.date>=doc.checked);
    summary([[`최근 응찰배율`,`${fmt(last?.bid_to_cover)}배`,last?.date],['최근 낙찰금리',`${fmt(last?.high_yield,3)}%`,last?.reopening?'재발행':'신규 발행'],['최근 발행규모',`${fmt(last?.amount)} 십억 $`,upcoming[0]?`다음 공고 경매 ${upcoming[0].date}`:'다음 일정은 공식 경매 공고에서 확인']]);
    const labels=rows.map(r=>r.date),offset=all.length-rows.length;
    chart('응찰배율 · Bid-to-cover',labels,[{label:'응찰배율',data:rows.map(r=>r.bid_to_cover)},{label:'12회 이동평균',data:roll.slice(offset),borderDash:[5,4],pointRadius:0}],'배');
    chart('낙찰금리 · High yield',labels,[{label:'낙찰금리',data:rows.map(r=>r.high_yield)}],'%');
    chart('경쟁입찰 낙찰 비중',labels,[{label:'간접 응찰자',data:rows.map(r=>r.indirect),borderColor:'#2878d4',backgroundColor:'#2878d4'},{label:'직접 응찰자',data:rows.map(r=>r.direct),borderColor:'#e07824',backgroundColor:'#e07824'},{label:'프라이머리 딜러',data:rows.map(r=>r.dealer),borderColor:'#89929b',backgroundColor:'#89929b'}],'%',{type:'bar',stacked:true,note:'경쟁입찰 배정액 기준 · SOMA·비경쟁 배정 제외. 간접 응찰자는 외국인만을 뜻하지 않습니다.'});
    chart('경매별 발행규모',labels,[{label:'공모액',data:rows.map(r=>r.amount)}],'십억 $',{type:'bar'});
    const detail=box.querySelector('.ust-detail');detail.innerHTML=`<p class="ust-note">${source('https://www.treasurydirect.gov/auctions/auction-announcements/','향후 경매 공고·결과')} · 응찰배율 = 총 응찰액 / 총 낙찰액. 결측을 0으로 채우거나 경매 사이를 주간 값으로 보간하지 않습니다.</p><div id="ust-auction-page"></div><details><summary>출처와 금리 기준</summary><p>경매에 공시된 만기를 우선하며, 잔존만기가 줄어든 일반 재발행은 원래 만기로 연결합니다. 기존 장기물의 추가 발행으로 전환된 2년물 경매도 2년물로 분류합니다. TIPS·변동금리채는 제외합니다.</p><p>기본 화면은 공모액 10억 달러 미만의 소액 경매를 제외합니다. 체크하면 원자료의 소액 경매도 포함합니다. 낙찰금리는 쿠폰금리와 다릅니다.</p><p>낙찰금리와 경매 직전 WI 금리의 차이인 테일은 WI 호가 자료가 없어 제공하지 않습니다. 일별 시장금리를 WI 금리로 대체하지 않습니다.</p><p>${source('https://fiscaldata.treasury.gov/datasets/treasury-securities-auctions-data/','Treasury Fiscal Data · 경매 원자료')} · ${doc.fetched} 확인</p></details>`;
    function renderPage(){const sorted=[...rows].reverse(),limit=24,max=Math.max(1,Math.ceil(sorted.length/limit));page=Math.min(page,max-1);const p=box.querySelector('#ust-auction-page');p.innerHTML=`<div class="ust-pager"><span>${sorted.length}회 경매</span><button type="button" data-step="-1" ${page===0?'disabled':''}>이전</button><span>${page+1} / ${max}</span><button type="button" data-step="1" ${page+1===max?'disabled':''}>다음</button></div><div id="ust-results"></div>`;table(p.querySelector('#ust-results'),'경매 결과 · 금액 십억 달러 / 금리·비중 %',['경매일','구분','CUSIP','발행액','응찰배율','낙찰금리','간접','직접','딜러'],sorted.slice(page*limit,(page+1)*limit).map(r=>[r.date,r.reopening?'재발행':'신규',r.cusip,fmt(r.amount),fmt(r.bid_to_cover),fmt(r.high_yield,3),fmt(r.indirect),fmt(r.direct),fmt(r.dealer)]));for(const b of p.querySelectorAll('[data-step]'))b.onclick=()=>{page+=Number(b.dataset.step);renderPage();};}renderPage();
  }
  function renderYields(){
    const doc=docs.yields,rows=inRange(doc.rows,prefs.range),last=doc.rows.at(-1),labels=rows.map(r=>r.date);
    header('미국 국채 시장금리','일별 재무부 명목 파 수익률 · 영업일 기준 · 실시간 호가와 구분합니다.',doc);
    // The shared maturity selector also controls auction markers on the 10Y view.
    controls();box.querySelector('#ust-term').closest('label').hidden=true;
    summary([['10년물',`${fmt(last?.['10'])}%`,last?.date],['2년물',`${fmt(last?.['2'])}%`,last?.date],['10년−2년',`${fmt(last?.spread)} bp`,last?.date]]);
    const events=new Map(docs.auctions.rows.filter(r=>r.completed&&!r.small_value&&r.term==='10-Year').map(r=>[r.date,r.high_yield]));
    chart('10년물 시장금리와 경매 낙찰금리',labels,[{label:'10년물 일별 시장금리',data:rows.map(r=>r['10'])},{label:'10년물 경매 낙찰금리',data:rows.map(r=>events.get(r.date)??null),showLine:false,pointRadius:3,pointStyle:'triangle'}],'%',{note:'두 값의 시점·대상은 다릅니다. 경매 표식은 실제 경매일에만 표시하며 차이를 테일로 해석하지 않습니다.'});
    chart('만기별 시장금리',labels,[10,2,5,30].map(t=>({label:`${t}년물`,data:rows.map(r=>r[t])})),'%');
    chart('장단기 금리차 · 10년−2년',labels,[{label:'10년−2년',data:rows.map(r=>r.spread)}],'bp');
    const panel=document.createElement('section');panel.className='ust-card';box.querySelector('.ust-grid').append(panel);table(panel,'최근 10영업일',['기준일','2년물 %','5년물 %','10년물 %','30년물 %','10년−2년 bp'],doc.rows.slice(-10).reverse().map(r=>[r.date,...[2,5,10,30].map(t=>fmt(r[t])),fmt(r.spread)]));
    box.querySelector('.ust-detail').innerHTML=`<details><summary>출처와 갱신 기준</summary><p>미 재무부의 Daily Treasury Par Yield Curve Rates입니다. 뉴욕 영업일 오후 약 3시 30분 호가를 기반으로 만든 만기별 곡선의 금리이며 특정 CUSIP의 실시간 체결가가 아닙니다.</p><p>금리차(bp) = (10년물 금리 − 2년물 금리) × 100. 휴일·결측은 임의 보간하지 않습니다.</p><p>${source(doc.source_url,'재무부 일별 금리')} · ${source('https://fred.stlouisfed.org/series/DGS10','FRED DGS10 교차확인')} · 마지막 성공 확인 ${doc.fetched}</p></details>`;
  }
  function render(){destroy();if(view==='qra')renderQra();else if(view==='auctions')renderAuctions();else renderYields();if(view!=='auctions'&&!docs.auctions.ok){const p=document.createElement('p');p.className='ust-warning';p.textContent='경매 결과는 마지막 성공 수집 자료입니다. 최신 결과와 차이가 있을 수 있습니다.';box.prepend(p);}const foot=document.getElementById('last-updated');if(foot)foot.textContent=`미국 국채 · 확인 ${docs[view].checked}`;}
  const needed=view==='qra'?['qra','auctions']:view==='yields'?['yields','auctions']:['auctions'];
  Promise.all(needed.map(async id=>{const r=await fetch(`data/us-treasury/${id}.json`);if(!r.ok)throw Error('HTTP '+r.status);return [id,await r.json()];})).then(entries=>{if(disposed)return;docs=Object.fromEntries(entries);render();}).catch(e=>{if(!disposed)box.innerHTML=`<p class="page-loading">미국 국채 자료를 불러오지 못했습니다. <button type="button">다시 불러오기</button></p>`;const b=box.querySelector('button');if(b)b.onclick=()=>window.location.reload();});
  return ()=>{disposed=true;destroy();box.remove();};
}
