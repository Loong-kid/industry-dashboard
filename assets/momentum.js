const PERIODS=[['ret_1d','1일'],['ret_1w','1주'],['ret_1m','1개월'],['ret_3m','3개월'],['ret_6m','6개월'],['ret_12m','1년']];
const SORTS=[...PERIODS,['relative_3m','시장 대비 3개월'],['sma200_gap','200일선 대비']];
const QUADRANTS={leading:'지속 우위',improving:'단기 개선',weakening:'단기 둔화',lagging:'지속 열위'};
const STATUS={ok:'정상',stale:'기준일 지연',fetch_error:'수집 확인 필요',benchmark_error:'기준시장 확인 필요'};
const TREND={up:'상승 정렬',down:'하락 정렬',mixed:'혼조',unavailable:'이력 부족'};
const number=(value,d=2)=>Number.isFinite(value)?new Intl.NumberFormat('ko-KR',{maximumFractionDigits:d,minimumFractionDigits:d}).format(value):'—';
export const percent=(value,unit='%')=>Number.isFinite(value)?(value>0?'+':'')+number(value)+unit:'—';
const css=name=>getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const el=(tag,cls,text)=>{const node=document.createElement(tag);if(cls)node.className=cls;if(text!==undefined)node.textContent=text;return node;};
const button=(text,fn,cls='')=>{const node=el('button',cls,text);node.type='button';node.onclick=fn;return node;};

export function quadrant(row){
  const x=row.metrics?.relative_3m,y=row.metrics?.relative_1m;
  return !row.eligible||!Number.isFinite(x)||!Number.isFinite(y)?null:x>=0?(y>=0?'leading':'weakening'):(y>=0?'improving':'lagging');
}

export function filterRows(rows,{query='',group='all',kind='all',status='all',quad='all',sort='ret_3m',ascending=false}={}){
  const words=query.toLowerCase().trim().split(/\s+/).filter(Boolean);
  return rows.filter(row=>(group==='all'||row.group===group)&&(kind==='all'||row.kind===kind)&&(status==='all'||(status==='ok'?row.status==='ok':row.status!=='ok'))&&(quad==='all'||quadrant(row)===quad)&&words.every(word=>[row.name,row.scope,...row.instruments.flatMap(i=>[i.symbol,i.name])].join(' ').toLowerCase().includes(word))).slice().sort((a,b)=>{
    const av=a.metrics?.[sort],bv=b.metrics?.[sort];
    const aok=a.status==='ok'&&Number.isFinite(av),bok=b.status==='ok'&&Number.isFinite(bv);
    return aok!==bok?(aok?-1:1):!aok?a.name.localeCompare(b.name,'ko'):(av-bv)*(ascending?1:-1)||a.name.localeCompare(b.name,'ko');
  });
}

export function comparisonData(doc,ids,{range='1y',rangeFrom='',rangeTo='',from,to}={},mode='price'){
  const selected=ids.map(id=>doc.rows.find(r=>r.id===id)).filter(Boolean);
  if(!selected.length||!doc.calendar.length)return {dates:[],series:[],base:null};
  let start=range==='custom'?rangeFrom:'';
  let end=range==='custom'?rangeTo:'';
  if(!['all','custom'].includes(range)){
    const date=new Date(doc.updated+'T00:00:00Z');
    if(range==='3m')date.setUTCMonth(date.getUTCMonth()-3);else date.setUTCFullYear(date.getUTCFullYear()-(range==='3y'?3:range==='5y'?5:1));
    start=date.toISOString().slice(0,10);
  }
  if(from!==undefined)start=from||'';
  if(to!==undefined)end=to||'';
  const calendar=doc.calendar.filter(d=>(!start||d>=start)&&(!end||d<=end));
  const maps=selected.map(r=>new Map(r.history));
  const benchmark=new Map(doc.benchmark.history);
  const base=calendar.find(d=>benchmark.get(d)>0&&maps.every(m=>m.get(d)>0));
  if(!base)return {dates:[],series:[],base:null};
  const dates=calendar.filter(d=>d>=base);
  const series=selected.map((row,index)=>({id:row.id,label:row.name,values:dates.map(d=>{
    const value=maps[index].get(d),market=benchmark.get(d);
    if(!(value>0)||!(market>0))return null;
    return 100*(value/maps[index].get(base))/(mode==='relative'?market/benchmark.get(base):1);
  })}));
  series.push({id:'benchmark',label:mode==='relative'?'기준시장 = 100':doc.benchmark.name,values:dates.map(d=>mode==='relative'?100:benchmark.get(d)/benchmark.get(base)*100)});
  return {dates,series,base};
}

function sourceLink(url,text){
  if(!/^https:\/\//.test(url||''))return el('span','',text);
  const a=el('a','',text);a.href=url;a.target='_blank';a.rel='noopener noreferrer';return a;
}

export function renderMomentum(doc,{market,state,colors,rangeBounds={}}={}){
  const root=el('section','momentum');root.setAttribute('aria-label',doc.name+' 산업 가격 모멘텀');
  const storageKey='industry-momentum-v1:'+market;
  let saved={};try{saved=JSON.parse(localStorage.getItem(storageKey)||'{}')||{};}catch{}
  const defaults=filterRows(doc.rows).filter(r=>r.eligible).slice(0,3).map(r=>r.id);
  let selected=Array.isArray(saved.selected)?[...new Set(saved.selected)].filter(id=>doc.rows.some(r=>r.id===id)).slice(0,5):defaults;
  if(!selected.length)selected=defaults;
  const prefs={query:'',group:['sector','industry'].includes(saved.group)?saved.group:'all',kind:['etf','basket'].includes(saved.kind)?saved.kind:'all',status:'all',quad:'all',sort:SORTS.some(([key])=>key===saved.sort)?saved.sort:'ret_3m',ascending:!!saved.ascending};
  let mode=saved.mode==='relative'?'relative':'price',comparison=null,scatter=null,openDetail=null;
  const save=()=>{try{localStorage.setItem(storageKey,JSON.stringify({selected,mode,group:prefs.group,kind:prefs.kind,sort:prefs.sort,ascending:prefs.ascending}));}catch{}};
  const destroy=chart=>{if(!chart)return;if(chart.canvas)chart.destroy();if(state)state.charts=state.charts.filter(c=>c!==chart);};
  const register=chart=>{if(state)state.charts.push(chart);return chart;};
  const top=el('div','mm-heading');
  top.append(el('p','mm-asof','확정 종가 '+(doc.updated||'미확보')+' · '+doc.benchmark.name),el('p','mm-caption','미국·한국은 각 시장의 거래일을 사용합니다. 장중 가격·배당 재투자는 반영하지 않습니다.'));
  root.append(top);
  if(!doc.collection_status.ok){const warning=el('p','mm-warning',`자료 확인 필요: ${doc.rows.filter(r=>r.status!=='ok').length}개 산업. 지연·수집 실패 항목은 순위와 시장 요약에서 제외합니다.`);warning.setAttribute('role','status');root.append(warning);}
  const fresh=doc.rows.filter(r=>r.status==='ok');
  const oneMonth=fresh.filter(r=>Number.isFinite(r.metrics.ret_1m)),ma=fresh.filter(r=>Number.isFinite(r.metrics.sma200_gap));
  const stats=el('div','mm-stats');
  for(const [label,value,note] of [
    ['1개월 상승 산업',`${oneMonth.filter(r=>r.metrics.ret_1m>0).length} / ${oneMonth.length}`,'현재 추적 대상 중'],
    ['200일선 위',`${ma.filter(r=>r.metrics.sma200_gap>0).length} / ${ma.length}`,'200일 이력 확보 산업'],
    ['기준시장 3개월',percent(doc.benchmark.metrics.ret_3m),doc.benchmark.name],
    ['순위 산출 가능',`${doc.rows.filter(r=>r.eligible).length} / ${doc.rows.length}`,'정상 자료·3개월 이력'],
  ]){const item=el('div','mm-stat');item.append(el('span','mm-caption',label),el('strong','',value),el('small','mm-caption',note));stats.append(item);}root.append(stats);

  const ranking=el('section','mm-panel mm-ranking');ranking.setAttribute('aria-label','산업 모멘텀 비교표');
  const tools=el('div','mm-filters');
  const input=el('input');input.type='search';input.placeholder='산업·ETF·구성 종목 검색';input.setAttribute('aria-label','산업·ETF·구성 종목 검색');
  const searchLabel=el('label','mm-search','검색');searchLabel.append(input);tools.append(searchLabel);
  function select(label,options,value,change){const wrap=el('label','',label),node=el('select');node.setAttribute('aria-label',label);for(const [id,text] of options){const option=el('option','',text);option.value=id;node.append(option);}node.value=value;node.onchange=()=>change(node.value);wrap.append(node);tools.append(wrap);return node;}
  const groupSelect=select('분류',[['all','전체 산업'],['sector','기본 섹터'],['industry','세부 산업·테마']],prefs.group,v=>{prefs.group=v;refresh();});
  const kindSelect=select('구성 방식',[['all','전체 방식'],['etf','ETF'],['basket','대표 종목 묶음']],prefs.kind,v=>{prefs.kind=v;refresh();});
  const statusSelect=select('자료 상태',[['all','전체 상태'],['ok','정상'],['warning','확인 필요']],prefs.status,v=>{prefs.status=v;refresh();});
  const sortSelect=select('정렬 기준',SORTS,prefs.sort,v=>{prefs.sort=v;prefs.ascending=false;refresh();});
  input.oninput=()=>{prefs.query=input.value;refresh();};
  ranking.append(tools);
  const toolbar=el('div','mm-resultbar'),result=el('p','mm-caption'),reset=button('필터 초기화',()=>{Object.assign(prefs,{query:'',group:'all',kind:'all',status:'all',quad:'all',sort:'ret_3m',ascending:false});input.value='';groupSelect.value=kindSelect.value=statusSelect.value='all';sortSelect.value='ret_3m';refresh();});
  toolbar.append(result,reset);ranking.append(toolbar);
  const scroll=el('div','mm-table-scroll');scroll.tabIndex=0;scroll.setAttribute('role','region');scroll.setAttribute('aria-label','산업별 기간 수익률');
  const table=el('table','mm-table'),thead=el('thead'),tbody=el('tbody');table.append(thead,tbody);scroll.append(table);ranking.append(scroll);
  const foot=el('p','mm-caption','수익률은 1·5·21·63·126·252거래일 기준입니다. 시장 대비는 산업 수익률 − 기준시장 수익률(%p)입니다. 순위는 현재 필터와 정렬 기준 안에서 표시합니다.');ranking.append(foot);root.append(ranking);

  const chartGrid=el('div','mm-chart-grid'),comparePanel=el('section','mm-panel'),scatterPanel=el('section','mm-panel');
  comparePanel.append(el('h3','','선택 산업 가격 흐름'));
  const compareTools=el('div','mm-chart-tools'),selectedList=el('div','mm-selected'),chartNote=el('p','mm-caption');
  const priceButton=button('가격 지수',()=>{mode='price';renderComparison();save();});
  const relativeButton=button('시장 대비',()=>{mode='relative';renderComparison();save();});
  compareTools.append(priceButton,relativeButton,button('3개월 상위 3개',()=>{selected=defaults.slice();syncCheckboxes();renderResult();renderComparison();save();}));
  const comparisonWrap=el('div','mm-chart');comparisonWrap.append(el('canvas'));comparePanel.append(compareTools,selectedList,chartNote,comparisonWrap);
  const selectionStatus=el('p','mm-caption');selectionStatus.setAttribute('role','status');selectionStatus.setAttribute('aria-live','polite');ranking.insertBefore(selectionStatus,scroll);
  scatterPanel.append(el('h3','','시장 대비 강도'),el('p','mm-caption','가로: 3개월 · 세로: 1개월 · 기준시장 대비 %p'));
  const quadButtons=el('div','mm-quadrants'),scatterWrap=el('div','mm-chart');scatterWrap.append(el('canvas'));scatterPanel.append(quadButtons,scatterWrap,el('p','mm-caption','점을 누르면 비교 대상에 추가·제거합니다. 단기 개선은 3개월 열위·1개월 우위이며 매수 신호를 뜻하지 않습니다.'));
  chartGrid.append(comparePanel,scatterPanel);root.append(chartGrid);

  function changeSelection(id,checked){
    if(checked&&!selected.includes(id)&&selected.length>=5){selectionStatus.textContent='최대 5개 산업까지 비교할 수 있습니다. 먼저 선택을 하나 해제해 주세요.';syncCheckboxes();return;}
    selected=checked?[...new Set([...selected,id])]:selected.filter(v=>v!==id);selectionStatus.textContent='';syncCheckboxes();renderResult();renderComparison();save();
  }
  function syncCheckboxes(){for(const node of tbody.querySelectorAll('input[type="checkbox"]')){node.checked=selected.includes(node.dataset.id);node.closest('tr').classList.toggle('mm-selected-row',node.checked);}}
  function metricCell(value,key){const td=el('td','mm-number',percent(value,key.startsWith('relative')?'%p':'%'));if(Number.isFinite(value))td.classList.add(value>0?'mm-up':value<0?'mm-down':'mm-flat');return td;}
  function renderDetail(row){
    const cell=el('td');cell.colSpan=12;
    cell.append(el('p','',row.note||''),el('p','mm-caption',`범위: ${row.scope} · 최초 확보 ${row.first_date||'—'} · 최근 가격 ${row.price_date||'—'} · 성공 수집 ${row.fetched||'—'}`));
    cell.append(el('p','mm-caption',row.kind==='basket'?`고정 ${row.member_count}사 · 공통 관측일마다 동일가중 재조정 · 현재 기준일 ${row.member_coverage}/${row.member_count}사 가격 확보. ${row.membership_asof} 선정 명단을 과거에 소급한 참고 지수로 생존편향이 있습니다.`:'ETF의 일별 거래가격을 사용합니다. 아래 상품은 추적 수단이며 ETF 내부 편입 종목 목록이 아닙니다.'));
    const list=el('ul','mm-sources');for(const i of row.instruments){const item=el('li');item.append(el('span','',`${i.name} · ${i.symbol} `),sourceLink(i.source_url,'기업·상품 원문'),el('span','',' · '),sourceLink(i.price_source,'가격 자료'));list.append(item);}cell.append(list);
    if(row.errors.length)cell.append(el('p','mm-warning',row.errors.join(' / ')));
    const tr=el('tr','mm-detail');tr.dataset.detailFor=row.id;tr.append(cell);return tr;
  }
  function renderTable(){
    const y=scroll.scrollTop,x=scroll.scrollLeft;thead.replaceChildren();tbody.replaceChildren();
    const header=el('tr');
    for(const [label,key] of [['비교',null],['순서',null],['산업 · 추적 수단',null],...PERIODS.map(([key,label])=>[label,key]),['시장 대비 3개월','relative_3m'],['200일선 대비','sma200_gap'],['추세 · 자료',null]]){
      const th=el('th');th.scope='col';if(key){const b=button(label,()=>{prefs.ascending=prefs.sort===key?!prefs.ascending:false;prefs.sort=key;sortSelect.value=key;refresh();[...thead.querySelectorAll('button')].find(node=>node.getAttribute('aria-label')===label+' 기준 정렬')?.focus({preventScroll:true});});b.setAttribute('aria-label',label+' 기준 정렬');th.append(b);th.setAttribute('aria-sort',prefs.sort===key?(prefs.ascending?'ascending':'descending'):'none');if(doc.anchors[key])th.title=`${doc.anchors[key]} → ${doc.updated}`;}else th.textContent=label;header.append(th);
    }thead.append(header);
    const rows=filterRows(doc.rows,prefs);renderResult(rows);
    rows.forEach((row,index)=>{
      const tr=el('tr',row.status==='ok'?'':'mm-row-warning');tr.dataset.industryId=row.id;tr.classList.toggle('mm-selected-row',selected.includes(row.id));
      const check=el('input');check.type='checkbox';check.checked=selected.includes(row.id);check.dataset.id=row.id;check.setAttribute('aria-label',row.name+' 비교 선택');check.onchange=()=>changeSelection(row.id,check.checked);const checkTd=el('td');checkTd.append(check);tr.append(checkTd,el('td','mm-number',row.status==='ok'&&Number.isFinite(row.metrics[prefs.sort])?String(index+1):'—'));
      const name=el('td','mm-industry'),toggle=button(row.name,()=>{openDetail=openDetail===row.id?null:row.id;renderTable();[...tbody.querySelectorAll('[data-industry-id]')].find(node=>node.dataset.industryId===row.id)?.querySelector('.mm-industry-button')?.focus({preventScroll:true});},'mm-industry-button');toggle.setAttribute('aria-expanded',String(openDetail===row.id));const instrument=row.instruments[0];const proxy=instrument.name.includes(instrument.symbol)?instrument.name:instrument.name+' · '+instrument.symbol;name.append(toggle,el('small','mm-caption',row.kind==='basket'?`대표 ${row.member_count}사 · 고정 구성`:proxy+(!['미국','한국'].includes(row.scope)?' · '+row.scope:'')));tr.append(name);
      for(const [key] of PERIODS)tr.append(metricCell(row.metrics[key],key));
      tr.append(metricCell(row.metrics.relative_3m,'relative_3m'),metricCell(row.metrics.sma200_gap,'sma200_gap'));
      const info=el('td','mm-row-info');info.append(el('span','mm-trend mm-trend-'+row.metrics.trend,TREND[row.metrics.trend]),el('small','mm-caption',STATUS[row.status]),el('small','mm-caption',row.price_date||'가격 미확보'));tr.append(info);tbody.append(tr);if(openDetail===row.id)tbody.append(renderDetail(row));
    });
    if(!rows.length){const tr=el('tr'),td=el('td','mm-empty','조건에 맞는 산업이 없습니다. 필터를 초기화해 주세요.');td.colSpan=12;tr.append(td);tbody.append(tr);}scroll.scrollTop=y;scroll.scrollLeft=x;
  }
  function renderResult(rows=filterRows(doc.rows,prefs)){result.textContent=`${rows.length} / ${doc.rows.length}개 산업 · ${SORTS.find(([key])=>key===prefs.sort)?.[1]} ${prefs.ascending?'오름차순':'내림차순'} · 비교 ${selected.length}/5`;}
  function commonOptions(){return {responsive:true,maintainAspectRatio:false,animation:false,normalized:true,plugins:{legend:{labels:{color:css('--ink-2'),boxWidth:12,font:{size:11}}},tooltip:{callbacks:{label:ctx=>ctx.dataset.label+': '+number(ctx.parsed.y)}}},scales:{x:{grid:{display:false},ticks:{color:css('--muted'),maxTicksLimit:window.innerWidth<600?3:6,maxRotation:0}},y:{grid:{color:ctx=>ctx.tick.value===100?css('--baseline'):css('--grid')},ticks:{color:css('--muted'),maxTicksLimit:6}}}};}
  function renderComparison(){
    destroy(comparison);comparison=null;selectedList.replaceChildren();for(const id of selected){const row=doc.rows.find(r=>r.id===id);selectedList.append(button(row.name+' ×',()=>changeSelection(id,false),'mm-selection'));}
    priceButton.setAttribute('aria-pressed',String(mode==='price'));relativeButton.setAttribute('aria-pressed',String(mode==='relative'));
    const data=comparisonData(doc,selected,{...state,...rangeBounds},mode);comparisonWrap.replaceChildren();
    if(!data.dates.length){comparisonWrap.append(el('p','mm-empty',selected.length?'선택 기간에 공통 가격이 없습니다. 기간을 늘리거나 비교 대상을 줄여주세요.':'표에서 비교할 산업을 선택해 주세요.'));chartNote.textContent='최대 5개 산업 · 위쪽 기간 버튼은 이 차트의 조회 범위를 바꿉니다.';return;}
    chartNote.textContent=`${data.base} = 100 · ${data.dates.at(-1)}까지 · ${mode==='relative'?'산업 가격비율 ÷ 기준시장 가격비율':'공통 시작일의 가격을 100으로 환산'}. 상단 기간 버튼은 차트만 바꾸며 표의 고정 모멘텀 기간에는 영향을 주지 않습니다.`;
    const canvas=el('canvas');canvas.setAttribute('role','img');canvas.setAttribute('aria-label',doc.name+' 선택 산업 '+(mode==='relative'?'시장 대비':'가격 지수')+' 비교 차트');comparisonWrap.append(canvas);
    comparison=register(new Chart(canvas,{type:'line',data:{labels:data.dates,datasets:data.series.map((series,i)=>({label:series.label,data:series.values,borderColor:series.id==='benchmark'?css('--muted'):colors[i%colors.length],borderDash:series.id==='benchmark'?[5,4]:[],borderWidth:series.id==='benchmark'?1.4:1.8,pointRadius:0,pointHitRadius:8,spanGaps:false,tension:0}))},options:commonOptions()}));
  }
  function renderScatter(){
    destroy(scatter);scatter=null;quadButtons.replaceChildren();
    const baseRows=filterRows(doc.rows,{...prefs,quad:'all'});
    const keys=Object.keys(QUADRANTS);
    for(const key of keys){const count=baseRows.filter(r=>quadrant(r)===key).length;const b=button(`${QUADRANTS[key]} ${count}`,()=>{prefs.quad=prefs.quad===key?'all':key;refresh();});b.setAttribute('aria-pressed',String(prefs.quad===key));quadButtons.append(b);}
    const rows=filterRows(doc.rows,prefs).filter(r=>quadrant(r));scatterWrap.replaceChildren();
    if(!rows.length){scatterWrap.append(el('p','mm-empty','정상 자료와 1·3개월 이력이 있는 산업만 표시합니다.'));return;}
    const canvas=el('canvas');canvas.setAttribute('role','img');canvas.setAttribute('aria-label',doc.name+' 산업별 1개월·3개월 시장 대비 강도');scatterWrap.append(canvas);
    const options=commonOptions();options.normalized=false;options.plugins.legend.display=false;
    options.plugins.tooltip.callbacks.label=ctx=>`${ctx.raw.name}: 3개월 ${percent(ctx.raw.x,'%p')} · 1개월 ${percent(ctx.raw.y,'%p')}`;
    options.onClick=(event,elements)=>{if(elements.length){const point=scatter.data.datasets[elements[0].datasetIndex].data[elements[0].index];changeSelection(point.id,!selected.includes(point.id));}};
    for(const [axis,key,title] of [['x','relative_3m','3개월 시장 대비 (%p)'],['y','relative_1m','1개월 시장 대비 (%p)']])options.scales[axis]={type:'linear',min:Math.min(-1,...rows.map(r=>r.metrics[key]))*1.1,max:Math.max(1,...rows.map(r=>r.metrics[key]))*1.1,title:{display:true,text:title,color:css('--muted'),font:{size:10}},ticks:{color:css('--muted'),maxTicksLimit:5},grid:{color:ctx=>ctx.tick.value===0?css('--baseline'):css('--grid')}};
    scatter=register(new Chart(canvas,{type:'scatter',data:{datasets:keys.map((key,i)=>({label:QUADRANTS[key],data:rows.filter(r=>quadrant(r)===key).map(r=>({x:r.metrics.relative_3m,y:r.metrics.relative_1m,name:r.name,id:r.id})),backgroundColor:colors[i%colors.length],pointRadius:5,pointHoverRadius:7}))},options}));
  }
  function refresh(){save();renderTable();renderScatter();}

  const methodology=el('details','mm-panel mm-methodology');methodology.append(el('summary','','계산 기준·구성 범위·출처'));
  const list=el('ul');
  for(const text of [
    `기준일 ${doc.updated||'미확보'} · 수집 ${doc.collected_at} · 자동 갱신 ${doc.auto_collect_time}. 장중 일봉은 제외합니다. 한국은 마감 자료 확인을 위해 18시 이후 당일 값을 사용합니다.`,
    `기준시장: ${doc.benchmark.name}. 한국 코스닥 기업도 같은 KOSPI 200 ETF와 비교합니다. 미국은 USD, 한국은 KRW 기준이며 원화 환산 수익률이 아닙니다. 미국 상장 ETF 중 글로벌 노출 상품은 산업명을 눌러 확인할 수 있습니다.`,
    '미국은 Yahoo Finance의 분할 반영 종가, 한국은 NAVER 일봉의 수정종가를 사용합니다. 서로 다른 공급자의 종가를 이어 붙이지 않습니다. 현금배당·ETF 분배금을 별도로 더하거나 재투자하지 않아 총수익률과 다릅니다.',
    '1주·1개월·3개월·6개월·1년은 각각 5·21·63·126·252거래일입니다. 수익률=(현재 가격/해당 기준일 가격−1)×100. 자료가 없으면 —이며 다른 날의 가격이나 0으로 대체하지 않습니다.',
    '시장 대비 표·산점도는 같은 기간 산업 수익률에서 기준시장 수익률을 뺀 %p입니다. 시장 대비 비교 차트는 산업 가격비율을 기준시장 가격비율로 나눈 값의 100배이므로 단위와 산식이 다릅니다.',
    '상승 정렬: 가격 > 50일 평균 > 200일 평균. 하락 정렬은 반대이며 나머지는 혼조입니다. 평균선 계산에는 해당 기간의 모든 기준시장 거래일 가격이 필요합니다.',
    '대표 종목 묶음은 모든 구성 종목의 가격이 함께 있는 관측일에 동일가중으로 재조정하는 비용 미반영 참고 지수입니다. 구성 종목 하나가 빠져도 나머지 종목만으로 계산하지 않습니다. 공통 이력 이전이나 누락 날짜는 채우지 않습니다.',
    '대표 종목은 현재 선정한 고정 명단이며 과거 이력은 현재 명단을 소급한 참고치입니다. 생존편향·구성 선택 편향이 있고 과거에 투자 가능했던 성과를 뜻하지 않습니다. ETF 자체의 편입 변화는 거래가격에 반영됩니다.',
    '섹터와 세부 산업의 구성 종목은 서로 겹칠 수 있습니다. 한국과 미국의 산업 분류·기업 노출은 동일하지 않습니다. 유동성·밸류에이션·실적·수급은 이번 가격 모멘텀에 포함하지 않습니다.',
  ])list.append(el('li','',text));methodology.append(list);
  const anchors=el('p','mm-caption','기간별 시작일: '+PERIODS.map(([key,label])=>`${label} ${doc.anchors[key]||'미확보'}`).join(' · '));methodology.append(anchors);root.append(methodology);
  renderTable();renderComparison();renderScatter();save();return root;
}
