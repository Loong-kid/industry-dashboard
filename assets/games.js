/* Public game market observatory. All metrics keep their source and denominator. */
const palette = ["#2a78d6","#1baf7a","#eda100","#4a3aa7","#e34948","#008300","#e87ba4","#eb6834","#5597a5","#8b764e","#7c8a24","#795cb5"];
const prefs = {grain:"month",metric:"share",from:"2020-01",to:"",steamGenre:"all",mobileGenre:"all",query:"",sort:"downloads_30d",country:"kr",kind:"topfreeapplications",appleDate:"",selected:"",paid:"all",page:0};
const financePrefs = {month:"",store:"google_play",game:"",kind:"quarter",date:"",company:"",metric:"revenue",region:"all",role:"all",query:"",platform:"unity",platformMetric:"",complex:"exclude"};
const roleNames={game:"개발·퍼블리싱",engine:"엔진·개발 도구",store:"유통·스토어",ads:"광고·수익화",console:"콘솔",platform:"UGC 플랫폼"};
const listingName=type=>({listed:"상장·공시 기업",private:"비상장",segment:"상장사 내 사업부"}[type]||"공개 자료 확인");
const esc = v => String(v ?? "").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const num = (v,d=0) => v == null || !Number.isFinite(v) ? "—" : v.toLocaleString("ko-KR",{maximumFractionDigits:d});
const compact = v => v == null ? "—" : Math.abs(v)>=1e8 ? `${num(v/1e8,2)}억` : Math.abs(v)>=1e4 ? `${num(v/1e4,1)}만` : num(v);
const delta = v => v == null ? "—" : `${v>0?"+":""}${num(v,1)}`;
const link = (url,label) => `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(label)}</a>`;
const note = text => `<p class="gm-note">${text}</p>`;
const options = (items,value) => items.map(([id,name])=>`<option value="${esc(id)}" ${id===value?"selected":""}>${esc(name)}</option>`).join("");
const genreNames = {GAME_ACTION:"액션·아케이드",GAME_ADVENTURE:"어드벤처",GAME_ARCADE:"액션·아케이드",GAME_BOARD:"카드·보드",GAME_CARD:"카드·보드",GAME_CASINO:"소셜·캐주얼",GAME_CASUAL:"소셜·캐주얼",GAME_EDUCATIONAL:"교육",GAME_MUSIC:"음악",GAME_PUZZLE:"퍼즐",GAME_RACING:"스포츠·레이싱",GAME_ROLE_PLAYING:"RPG",GAME_SIMULATION:"시뮬레이션",GAME_SPORTS:"스포츠·레이싱",GAME_STRATEGY:"전략",GAME_TRIVIA:"퀴즈·단어",GAME_WORD:"퀴즈·단어"};
const appleGenres = {Action:"액션·아케이드",Adventure:"어드벤처",Arcade:"액션·아케이드",Board:"카드·보드",Card:"카드·보드",Casino:"소셜·캐주얼",Casual:"소셜·캐주얼",Family:"파티·캐주얼",Music:"음악",Puzzle:"퍼즐",Racing:"스포츠·레이싱","Role Playing":"RPG",Simulation:"시뮬레이션",Sports:"스포츠·레이싱",Strategy:"전략",Trivia:"퀴즈·단어",Word:"퀴즈·단어"};
export const daysInMonth = date => new Date(Date.UTC(Number(date.slice(0,4)),Number(date.slice(5,7)),0)).getUTCDate();
export const percent = (a,b) => a != null && b>0 ? a/b*100 : null;

// Annual values are day-weighted means of observed calendar months, never a sum
// of concurrent-player counts. Partial years retain their observed month count.
export function aggregateSteam(games, grain="month", from="0000-01", to="9999-12") {
  const months = new Map();
  for (const game of games) for (const [date,average] of game.points) {
    if (date<from || date>to || average==null) continue;
    if (!months.has(date)) months.set(date,{date,genres:{},counts:{},total:0});
    const month=months.get(date);
    month.genres[game.genre]=(month.genres[game.genre]||0)+average;
    month.counts[game.genre]=(month.counts[game.genre]||0)+1;
    month.total+=average;
  }
  const ordered=[...months.values()].sort((a,b)=>a.date.localeCompare(b.date));
  if(grain==="month") return ordered.map(m=>({...m,months:1,first:m.date,last:m.date}));
  const years=new Map();
  for(const month of ordered){
    const year=month.date.slice(0,4),days=daysInMonth(month.date);
    if(!years.has(year)) years.set(year,{date:year,genres:{},counts:{},total:0,days:0,months:0,first:month.date,last:month.date});
    const row=years.get(year);row.days+=days;row.months++;row.last=month.date;row.total+=month.total*days;
    for(const [genre,value] of Object.entries(month.genres)) row.genres[genre]=(row.genres[genre]||0)+value*days;
    for(const [genre,value] of Object.entries(month.counts)) row.counts[genre]=(row.counts[genre]||0)+value*days;
  }
  return [...years.values()].map(y=>({...y,total:y.total/y.days,genres:Object.fromEntries(Object.entries(y.genres).map(([g,v])=>[g,v/y.days])),counts:Object.fromEntries(Object.entries(y.counts).map(([g,v])=>[g,v/y.days]))}));
}

export function snapshotPeriods(observations, id, grain="month") {
  const map=new Map();
  for(const point of observations.filter(p=>p.id===id).sort((a,b)=>a.date.localeCompare(b.date))) map.set(point.date.slice(0,grain==="year"?4:7),point);
  return [...map.entries()].map(([period,p])=>({period,...p}));
}
export function csvText(headers,rows){
  const cell=v=>{let s=String(v??"");if(typeof v!=="number"&&/^[=+@\-]/.test(s))s="'"+s;return `"${s.replaceAll('"','""')}"`;};
  return "\uFEFF"+[headers,...rows].map(r=>r.map(cell).join(",")).join("\r\n");
}
export function mobileRows(mobile, estimates){
  const catalog=new Map(mobile.games.map(g=>[g.id,{...g,genre:genreNames[g.genre]||g.genre}]));
  // Keep public estimate observations even when the US store listing is absent.
  for(const e of estimates.observations){
    const prior=catalog.get(e.id)||{id:e.id,name:e.name,url:`https://play.google.com/store/apps/details?id=${e.id}`};
    catalog.set(e.id,{...prior,...e,estimate_url:e.url,url:prior.url});
  }
  return [...catalog.values()];
}

export function revenueRows(revenue,month,store){
  const report=revenue.reports.find(r=>r.month===month);
  const games=new Map(revenue.games.map(g=>[g.id,g]));
  return (report?.stores[store]||[]).map(r=>({...games.get(r.id),...r,month,store,url:report.url}));
}
export function publisherRevenue(rows){
  const groups=new Map();
  for(const row of rows){
    // A subtotal is only meaningful within one report month and store scope.
    const key=[row.month,row.store,row.publisher].join("|");
    if(!groups.has(key))groups.set(key,{publisher:row.publisher,month:row.month,store:row.store,value:0,games:[]});
    const group=groups.get(key);group.value+=row.usd_millions;group.games.push(row.name);
  }
  return [...groups.values()].sort((a,b)=>b.value-a.value);
}
export function revenueChange(revenue,id,month,store,monthsBack){
  const d=new Date(`${month}-01T00:00:00Z`);d.setUTCMonth(d.getUTCMonth()-monthsBack);
  const prevMonth=d.toISOString().slice(0,7);
  const now=revenueRows(revenue,month,store).find(r=>r.id===id)?.usd_millions;
  const prev=revenueRows(revenue,prevMonth,store).find(r=>r.id===id)?.usd_millions;
  return now!=null&&prev>0?(now/prev-1)*100:null;
}
export function companyGrowth(rows,row,metric="revenue"){
  const prior=rows.find(r=>r.kind===row.kind&&r.date===`${Number(row.date.slice(0,4))-1}${row.date.slice(4)}`);
  return row[metric]!=null&&prior?.[metric]>0?(row[metric]/prior[metric]-1)*100:null;
}
// All original accounts remain untouched; only an exact, completed fiscal-period
// quote can be used. Missing FX is never zero or today's spot rate.
export function fxQuote(fx,currency,row){
  if(currency==="USD")return {local_per_usd:1,method:"original USD",start:row?.start,end:row?.date};
  const q=fx?.periods?.[`${currency}|${row?.start}|${row?.date}`];
  return q&&q.currency===currency&&q.start===row?.start&&q.end===row?.date&&Number.isFinite(q.local_per_usd)&&q.local_per_usd>0?q:null;
}
export function usdAmount(value,currency,row,fx){
  const q=fxQuote(fx,currency,row);
  return Number.isFinite(value)&&q?value/q.local_per_usd:null;
}
export function usdGrowth(company,row,fx,metric="revenue"){
  const prior=company.rows.find(r=>r.kind===row.kind&&r.date===`${Number(row.date.slice(0,4))-1}${row.date.slice(4)}`);
  const now=usdAmount(row[metric],company.currency,row,fx),before=usdAmount(prior?.[metric],company.currency,prior,fx);
  return now!=null&&before>0?(now/before-1)*100:null;
}
export function monetaryMetric(row){
  return ["revenue","spend","creator_income"].includes(row?.kind)&&/^백만 [A-Z]{3}$/.test(row?.unit||"");
}
const metricCurrency=row=>monetaryMetric(row)?row.unit.split(" ").at(-1):null;
export function moneyMemo(value,currency,row,fx){
  if(!Number.isFinite(value))return ["원자료 금액 미공개·미확보"];
  const lines=[`원통화: ${num(value,6)} 백만 ${currency}`];
  if(currency==="KRW")lines.push(`원화: ${num(value/100,4)}억원`);
  if(row?.start&&row?.date)lines.push(`실적 기간: ${row.start} ~ ${row.date}`);
  const q=fxQuote(fx,currency,row);
  if(currency==="USD")lines.push("원자료 USD 그대로 · 환산 없음");
  else if(q)lines.push(`기간 평균: 1 USD = ${num(q.local_per_usd,6)} ${currency}`,`원통화 금액 ÷ 평균환율 = 백만 USD`,`ECB 일별 기준환율 ${q.observations}개 관측 평균`,`${q.first} ~ ${q.last} · 조회 ${q.fetched?.slice(0,10)||"—"}`);
  else lines.push("해당 실적 기간 평균환율 미확보 · USD 값 미표시");
  return lines;
}
const memoValue=(text,lines)=>`<button type="button" class="gm-money" data-money-note="${esc(lines.join("\n"))}" aria-label="${esc(`${text}. ${lines.join(". ")}`)}">${esc(text)}</button>`;
const usdMoney=(value,currency,row,fx,suffix="")=>!Number.isFinite(value)?"—":memoValue(`${usdAmount(value,currency,row,fx)==null?"환산 미확보":num(usdAmount(value,currency,row,fx),1)}${suffix}`,moneyMemo(value,currency,row,fx));
export function companySeries(rows,kind){
  const points=rows.filter(r=>r.kind===kind).sort((a,b)=>a.date.localeCompare(b.date));
  if(!points.length)return [];
  const index=r=>kind==="annual"?Number(r.date.slice(0,4)):Number(r.date.slice(0,4))*4+Math.ceil(Number(r.date.slice(5,7))/3)-1;
  const map=new Map(points.map(r=>[index(r),r])),series=[];
  for(let i=index(points[0]);i<=index(points.at(-1));i++)series.push({row:map.get(i),label:map.has(i)?`${map.get(i).period} (${map.get(i).date})`:kind==="annual"?`${i} (미확보)`:`${Math.floor(i/4)} Q${i%4+1} (미확보)`});
  return series;
}
export function directoryRows(companies,{region="all",role="all",query=""}={}){
  const text=query.trim().toLowerCase();
  return companies.filter(c=>(region==="all"||c.region===region)&&(role==="all"||c.roles?.includes(role))&&`${c.name} ${c.brands} ${(c.aliases||[]).join(" ")} ${c.country} ${c.scope}`.toLowerCase().includes(text));
}
export function platformMetrics(platforms,id){
  const profile=platforms.profiles.find(p=>p.id===id);
  if(!profile)return [];
  if(id!=="steam")return profile.metrics;
  return (platforms.steam?.observations||[]).flatMap(r=>[
    {id:"online_now",label:"Steam 동시 온라인",value:r.online_now,unit:"계정",period:r.date,observed_at:r.observed_at,url:r.url,kind:"concurrency",scope:"조회 시 온라인 계정 · 게임 미실행 계정 포함 · MAU 아님"},
    {id:"peak_displayed",label:"공식 화면 표시 최고 동접",value:r.peak_displayed,unit:"계정",period:r.date,observed_at:r.observed_at,url:r.url,kind:"concurrency",scope:"조회 시 PEAK ONLINE 표시값 · 월간 최고치나 역대 최고치로 재해석하지 않음"}
  ]);
}
const financialStatus = c => c.status==="ok"?"자동 수집 정상":c.status?.startsWith("reviewed public IR")?"공개 IR 원문 대조 · 수기 갱신":c.status?.includes("OpenDART key/index unavailable")?"자동 수집 미완료 · 기존 자료 유지":"일부 요청 실패 · 기존 성공 자료 유지";
const calculationName = text => ({"reported annual":"연간 공시","reported quarter":"분기 공시","YTD minus previous YTD":"누적 차감","annual minus nine months":"연간−9개월","reported quarter · rounded official IR":"공식 발표 반올림"}[text]||text||"");

export function mount(root,{view="overview",tabsRoot}={}){
  const abort=new AbortController();let renderEvents=new AbortController(),alive=true, charts=[],data=null;
  const destroy=()=>{charts.forEach(c=>c.destroy());charts=[];};
  const on=(selector,event,fn)=>root.querySelector(selector)?.addEventListener(event,fn,{signal:renderEvents.signal});
  const select=(selector,key)=>on(selector,"change",e=>{prefs[key]=e.target.value;prefs.page=0;render();});
  const status=document.createElement("p");status.className="page-loading";status.textContent="게임 시장 공개 데이터 불러오는 중…";root.append(status);
  if(tabsRoot){tabsRoot.innerHTML=`<nav class="commodity-tabs gm-tabs" aria-label="게임 시장 화면">${[["overview","시장 규모"],["steam","Steam 장르"],["mobile","Google Play"],["apple","App Store 차트"],["revenue","게임별 매출"],["companies","게임사 실적"],["platforms","게임 플랫폼"],["sources","출처·범위"]].map(([id,name])=>`<a href="#/games/${id}" class="${view===id?"active":""}" ${view===id?'aria-current="page"':""}>${name}</a>`).join("")}</nav>`;}
  const names=({overview:["market"],steam:["steam"],mobile:["mobile","download-estimates"],apple:["apple"],revenue:["revenue","fx"],companies:["companies","fx"],platforms:["companies","platforms","fx"]})[view]||["market","steam","mobile","apple","download-estimates","revenue","companies","platforms","fx"];
  Promise.all(names.map(async name=>{try{const r=await fetch(`data/games/${name}.json`,{signal:abort.signal});if(!r.ok)throw Error(`HTTP ${r.status}`);return [name,await r.json()];}catch(e){if(e.name==="AbortError")throw e;return[name,null];}})).then(entries=>{
    if(!alive)return;data=Object.fromEntries(entries);render();
    const dates=[data.steam?.fetched,data.mobile?.fetched,data.apple?.fetched,data.companies?.checked,data.platforms?.steam?.fetched?.slice(0,10)].filter(Boolean);
    document.getElementById("last-updated").textContent=dates.length?`게임 자료 조회 ${dates.sort().at(-1)} · 실적 기간은 각 행 표시`:data.revenue?`매출 표 원문 대조 ${data.revenue.reviewed} · 실적 기간은 각 행 표시`:data.market?`시장 규모 발표 ${data.market.latest.published} · 추정 범위는 본문 표시`:"게임 자료 기준일은 각 표·출처에 표시";
  }).catch(e=>{if(alive)status.textContent=`데이터를 불러오지 못했습니다: ${e.message}`;});
  function chart(id,type,labels,datasets,{percentAxis=false,stacked=false,horizontal=false,signed=false,decimals=0}={}){
    const canvas=root.querySelector(`#${id}`);if(!canvas)return;
    if(!window.Chart){canvas.replaceWith(Object.assign(document.createElement("p"),{textContent:"차트 라이브러리를 불러오지 못했습니다. 아래 표에서 값을 확인할 수 있습니다."}));return;}
    const ink=getComputedStyle(document.documentElement).getPropertyValue("--ink-2").trim();
    const grid=getComputedStyle(document.documentElement).getPropertyValue("--grid").trim();
    charts.push(new window.Chart(canvas,{type,data:{labels,datasets},options:{responsive:true,maintainAspectRatio:false,animation:false,indexAxis:horizontal?"y":"x",interaction:{mode:"index",intersect:false},plugins:{legend:{position:"bottom",display:datasets.length>1,labels:{color:ink,boxWidth:12}},tooltip:{callbacks:{label:c=>`${c.dataset.label}: ${num(horizontal?c.parsed.x:c.parsed.y,percentAxis?1:decimals)}${percentAxis?"%":""}`,afterLabel:c=>c.dataset.moneyNotes?.[c.dataIndex]||[]}}},scales:{x:{stacked,ticks:{color:ink,maxTicksLimit:12},grid:{display:false}},y:{stacked,min:signed||horizontal?undefined:0,max:percentAxis?100:undefined,ticks:horizontal?{color:ink,autoSkip:false}:{color:ink,callback:v=>percentAxis?`${v}%`:compact(v)},grid:{color:grid}}}}}));
  }
  function header(title,description){return `<div class="gm-intro"><h2>${title}</h2><p>${description}</p></div>`;}
  function panel(title,body,extra=""){return `<section class="gm-panel ${extra}"><h3>${title}</h3>${body}</section>`;}
  function table(headers,rows){return `<div class="gm-table-wrap"><table class="gm-table"><thead><tr>${headers.map(h=>`<th scope="col">${h}</th>`).join("")}</tr></thead><tbody>${rows.length?rows.map(r=>`<tr>${r.map(c=>`<td>${c}</td>`).join("")}</tr>`).join(""):`<tr><td colspan="${headers.length}">조건에 맞는 관측값이 없습니다.</td></tr>`}</tbody></table></div>`;}
  function stats(items){return `<dl class="gm-stats">${items.map(([label,value,detail])=>`<div><dt>${label}</dt><dd>${value}</dd><small>${detail}</small></div>`).join("")}</dl>`;}
  function download(name,headers,rows){const blob=new Blob([csvText(headers,rows)],{type:"text/csv;charset=utf-8"});const url=URL.createObjectURL(blob);const a=document.createElement("a");a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
  function missing(name){return header("데이터 확인 필요",`${name} 자료를 불러오지 못했습니다. 새로고침 후 출처·범위에서 수집 상태를 확인해 주세요.`);}
  function render(){
    if(!alive)return;renderEvents.abort();renderEvents=new AbortController();destroy();root.classList.add("gm-root");
    if(view==="overview")renderMarket();else if(view==="steam")renderSteam();else if(view==="mobile")renderMobile();else if(view==="apple")renderApple();else if(view==="revenue")renderRevenue();else if(view==="companies")renderCompanies();else if(view==="platforms")renderPlatforms();else renderSources();
    bindMoneyMemos();
  }
  function bindMoneyMemos(){
    if(!root.querySelector(".gm-money"))return;
    const tip=document.createElement("div");tip.id="gm-money-tooltip";tip.className="gm-money-tooltip";tip.setAttribute("role","tooltip");tip.hidden=true;root.append(tip);
    let active=null;
    const hide=()=>{active?.removeAttribute("aria-describedby");active=null;tip.hidden=true;};
    const show=button=>{hide();active=button;tip.textContent=button.dataset.moneyNote;tip.hidden=false;button.setAttribute("aria-describedby",tip.id);const r=button.getBoundingClientRect();tip.style.left=`${Math.max(12,Math.min(r.left,innerWidth-tip.offsetWidth-12))}px`;tip.style.top=`${Math.max(12,r.bottom+tip.offsetHeight+12>innerHeight?r.top-tip.offsetHeight-8:r.bottom+8)}px`;};
    root.querySelectorAll(".gm-money").forEach(button=>{
      const opts={signal:renderEvents.signal};
      button.addEventListener("mouseenter",()=>show(button),opts);
      button.addEventListener("mouseleave",()=>{if(document.activeElement!==button)hide();},opts);
      button.addEventListener("focus",()=>show(button),opts);
      button.addEventListener("blur",hide,opts);
      button.addEventListener("click",()=>show(button),opts);
    });
    root.addEventListener("keydown",e=>{if(e.key==="Escape")hide();},{signal:renderEvents.signal});
    document.addEventListener("pointerdown",e=>{if(!e.target.closest(".gm-money"))hide();},{signal:renderEvents.signal});
    window.addEventListener("scroll",()=>{if(!active)return;const r=active.getBoundingClientRect();if(r.bottom<0||r.top>innerHeight||r.right<0||r.left>innerWidth)hide();else show(active);},{signal:renderEvents.signal,passive:true,capture:true});
    window.addEventListener("resize",hide,{signal:renderEvents.signal,passive:true});
  }
  function renderMarket(){
    const market=data.market;if(!market){root.innerHTML=missing("시장 규모");return;}
    const latest=market.latest,history=market.history;
    root.innerHTML=header("게임 시장은 얼마나 커지고 있을까?","시장 전체의 지출 규모와, 사람들이 선택하는 장르의 변화를 나눠 봅니다. 공개 자료만 사용하며 플랫폼·표본마다 관측 범위가 다릅니다.")+
      stats([[`${latest.year} 세계 시장 추정`,`${num(latest.total,1)} 십억 달러`,`${link(latest.url,"Newzoo")} · ${latest.published} 발표`],["전년 대비",`${delta(latest.yoy)}%`,"해당 보고서가 발표한 성장률"],["모바일 비중",`${num(latest.platforms[0].value/latest.total*100,1)}%`,"모바일·PC·콘솔 콘텐츠 시장"]])+
      `<div class="gm-grid">${panel(`${latest.year} 플랫폼별 시장 규모`,note("단위: 십억 달러 · 시장 추정치")+`<div class="gm-chart"><canvas id="gm-platform" role="img" aria-label="플랫폼별 시장 매출 추정치"></canvas></div>`+table(["플랫폼","시장 규모","발표 YoY"],latest.platforms.map(p=>[esc(p.name),num(p.value,1),`${delta(p.yoy)}%`])))}${panel("데이터로 읽는 시장의 변화",`<ul class="gm-reading"><li><b>수요의 유입</b><p>Google Play에서 최근 30일 추정치와 누적 보급 규모를 비교합니다.</p><a href="#/games/mobile">Google Play 보기</a></li><li><b>계속 즐기는 장르</b><p>Steam 월평균 동시접속자와 장르별 표본 비중의 과거·현재를 비교합니다.</p><a href="#/games/steam">Steam 장르 변화 보기</a></li><li><b>매출로 이어진 인기</b><p>게임별 스토어 매출 추정치와 게임사의 공시 실적을 확인합니다.</p><a href="#/games/revenue">게임별 매출 보기</a> · <a href="#/games/companies">게임사 실적 보기</a></li><li><b>국가별 선택</b><p>한국·미국·일본·중국 App Store 게임 차트를 관측합니다.</p><a href="#/games/apple">국가별 차트 보기</a></li></ul>`)}</div>`+
      panel("연도별 플랫폼 구성 · 동일 보고서 기준",note(`${esc(history.edition)}. 최신 ${latest.published} 개정 수치와는 판본이 다릅니다. 두 시계열을 연결해 성장률을 계산하지 않습니다.`)+`<div class="gm-chart"><canvas id="gm-market-history" role="img" aria-label="과거 보고서 기준 연도별 게임 시장 규모"></canvas></div>`+table(["연도","모바일","PC","콘솔","전체"],history.points.map(p=>[p.year,num(p.mobile,1),num(p.pc,1),num(p.console,1),num(p.total,1)]))+note(`${link(history.url,"공개 공시의 원본 표")} · 반올림으로 플랫폼 합계와 전체에 차이가 있습니다.`))+
      note("전체 시장은 연간 공개 자료로 확인합니다. Steam 표본이나 Google Play 다운로드 합계를 세계 시장 전체 또는 잠재 시장(TAM)으로 환산하지 않습니다. 원스토어·콘솔 개별 게임의 무료 연속 실적은 현재 포함하지 않습니다.");
    chart("gm-platform","bar",latest.platforms.map(p=>p.name),[{label:"시장 규모 (십억 달러)",data:latest.platforms.map(p=>p.value),backgroundColor:palette.slice(0,3)}]);
    chart("gm-market-history","bar",history.points.map(p=>String(p.year)),[...[ ["mobile","모바일"],["pc","PC"],["console","콘솔"] ].map(([key,label],i)=>({label,data:history.points.map(p=>p[key]),backgroundColor:palette[i]}))],{stacked:true});
  }
  function renderSteam(){
    const steam=data.steam;if(!steam){root.innerHTML=missing("Steam");return;}
    const allDates=steam.games.flatMap(g=>g.points.map(p=>p[0])).sort();
    const latest=allDates.at(-1);if(!prefs.to)prefs.to=latest;
    const periods=aggregateSteam(steam.games,prefs.grain,prefs.from,prefs.to);
    const genres=[...new Set(steam.games.map(g=>g.genre))];
    const first=periods[0],last=periods.at(-1);
    const order=[...genres].sort((a,b)=>(last?.genres[b]||0)-(last?.genres[a]||0));
    const yearLabel=p=>prefs.grain==="year"?`${p.date}${p.months<12?` (${p.first.slice(5)}–${p.last.slice(5)}월)`:""}`:p.date;
    const rows=order.map(g=>({genre:g,value:last?.genres[g]??null,share:percent(last?.genres[g],last?.total),before:percent(first?.genres[g],first?.total)}));
    root.innerHTML=header("어떤 장르를 계속 플레이했을까?",`${steam.games.length}개 고정 표본의 월평균 동시접속자. 각 게임의 실제 과거 기록을 합산하며, 전체 Steam 점유율·다운로드·월간 이용자 수를 뜻하지 않습니다.`)+
      `<div class="gm-toolbar"><label>집계<select id="gm-grain">${options([["month","월별"],["year","연도별"]],prefs.grain)}</select></label><label>시작<input id="gm-from" type="month" min="${allDates[0]}" max="${latest}" value="${esc(prefs.from)}"></label><label>끝<input id="gm-to" type="month" min="${allDates[0]}" max="${latest}" value="${esc(prefs.to)}"></label><label>표시<select id="gm-metric">${options([["share","장르 비중 (%)"],["average","평균 동시접속자 합계"]],prefs.metric)}</select></label><button id="gm-export">CSV 내려받기</button></div>`+
      note(`수집 ${esc(steam.fetched)} · 완료된 달만 포함 · 연간은 관측 월의 일수 가중평균. 현재 연도는 관측된 월까지만 집계합니다. 표본은 대표 게임을 직접 선정했으므로 장르 간 시장 점유율로 일반화할 수 없습니다.${steam.errors.length?` ${steam.errors.length}개 요청 실패: 유지된 기록의 수집일은 게임 표에서 확인하세요.`:""}`)+
      panel(`${first?yearLabel(first):"—"} → ${last?yearLabel(last):"—"} · 장르 변화`,`<div class="gm-chart gm-chart-tall"><canvas id="gm-steam-trend" role="img" aria-label="Steam 장르별 이용량 추이"></canvas></div>`)+
      panel("과거와 현재 · 표본 안에서 달라진 비중",table(["장르",first?esc(yearLabel(first)):"시작 비중",last?esc(yearLabel(last)):"끝 비중","변화 (%p)","끝 기간 평균 동접 합계"],rows.map(r=>[esc(r.genre),r.before==null?"—":`${num(r.before,1)}%`,r.share==null?"—":`${num(r.share,1)}%`,r.share!=null&&r.before!=null?`${delta(r.share-r.before)}%p`:"—",compact(r.value)]))+note("연간 시작·끝에 포함된 월이 다르면 계절 효과가 섞일 수 있습니다. 출시 전·수집 누락은 관측값이 없으며 0으로 채우지 않습니다."))+
      panel("최근 12개 기간 · 장르 비중 지도",`<div class="gm-table-wrap"><table class="gm-table gm-heat"><thead><tr><th>장르</th>${periods.slice(-12).map(p=>`<th>${esc(yearLabel(p))}</th>`).join("")}</tr></thead><tbody>${order.map(g=>`<tr><th scope="row">${esc(g)}</th>${periods.slice(-12).map(p=>{const v=percent(p.genres[g],p.total);return `<td style="background:rgba(42,120,214,${v==null?0:Math.min(.65,v/65)})">${v==null?"—":num(v,1)+"%"}</td>`;}).join("")}</tr>`).join("")}</tbody></table></div>`)+
      panel("장르를 이끈 게임",`<div class="gm-toolbar"><label>장르<select id="gm-steam-genre">${options([["all","전체 장르"],...genres.map(g=>[g,g])],prefs.steamGenre)}</select></label></div>`+table(["게임","대표 장르","마지막 월","월평균 동접","월 최고 동접","수집일"],steam.games.filter(g=>prefs.steamGenre==="all"||g.genre===prefs.steamGenre).map(g=>({...g,p:g.points.filter(p=>p[0]>=prefs.from&&p[0]<=prefs.to).at(-1)})).sort((a,b)=>(b.p?.[1]||0)-(a.p?.[1]||0)).map(g=>[link(g.url,g.name),esc(g.genre),g.p?.[0]||"—",compact(g.p?.[1]),compact(g.p?.[2]),esc(g.fetched)])));
    select("#gm-grain","grain");select("#gm-from","from");select("#gm-to","to");select("#gm-metric","metric");select("#gm-steam-genre","steamGenre");
    on("#gm-export","click",()=>download("steam-genre-trends.csv",["period","genre","average_ccu_sum","sample_share_pct","observed_months","first_month","last_month"],periods.flatMap(p=>genres.map(g=>[p.date,g,p.genres[g],percent(p.genres[g],p.total),p.months,p.first,p.last]))));
    chart("gm-steam-trend","line",periods.map(yearLabel),order.map((g,i)=>({label:g,data:periods.map(p=>prefs.metric==="share"?percent(p.genres[g],p.total):p.genres[g]??null),borderColor:palette[i%palette.length],backgroundColor:palette[i%palette.length]+"66",fill:prefs.metric==="share"?(i?"-1":"origin"):false,pointRadius:0,borderWidth:1.5,spanGaps:false})),{percentAxis:prefs.metric==="share",stacked:prefs.metric==="share"});
  }
  function renderMobile(){
    if(!data.mobile||!data["download-estimates"]){root.innerHTML=missing("Google Play");return;}
    const estimates=data["download-estimates"],all=mobileRows(data.mobile,estimates);
    const genres=[...new Set(all.map(g=>g.genre))].sort();
    const records=all.filter(g=>(prefs.mobileGenre==="all"||g.genre===prefs.mobileGenre)&&(prefs.paid==="all"||(prefs.paid==="free"?g.price===0:g.price>0))&&`${g.name} ${g.developer||""} ${g.id} ${g.subgenre||""}`.toLowerCase().includes(prefs.query.toLowerCase())).sort((a,b)=>(b[prefs.sort]??-1)-(a[prefs.sort]??-1));
    const measured=records.filter(g=>g.downloads_30d!=null);
    const sums=new Map();for(const g of measured)sums.set(g.genre,(sums.get(g.genre)||0)+g.downloads_30d);
    const ranked=[...sums.entries()].sort((a,b)=>b[1]-a[1]);
    const pages=Math.max(1,Math.ceil(records.length/30));prefs.page=Math.min(prefs.page,pages-1);
    const tableRows=records.slice(prefs.page*30,prefs.page*30+30).map(g=>[link(g.url,g.name),esc(g.genre)+(g.subgenre?`<small>${esc(g.subgenre)}</small>`:""),g.downloads_30d!=null?`약 ${compact(g.downloads_30d)}`:"미확보",g.total_estimate!=null?`약 ${compact(g.total_estimate)}`:"미확보",g.installs_lower!=null?`${compact(g.installs_lower)}+`:"미확보",g.source_updated?`${esc(g.source_updated)}<small>${link(g.estimate_url,"AppBrain 추정")}</small>`:"—",g.rating!=null?num(g.rating,2):"—"]);
    root.innerHTML=header("새로 선택하는 게임과, 오래 보급된 게임",`Google Play 공개 목록 ${all.length}개 표본. 최근 30일·누적 추정치가 있는 게임은 ${all.filter(g=>g.downloads_30d!=null).length}개이며, 나머지는 공식 누적 다운로드 하한만 제공합니다. 다운로드는 전 세계 기준이며 국가별 수치가 아닙니다.`)+
      note(`AppBrain 추정치는 ${esc(estimates.observed_at)}에 공개 화면에서 확인한 반올림 값입니다. 각 행의 기준일 직전 30일이며, 달력 기준 월별 다운로드가 아닙니다. 자동 갱신 대상은 Google Play 공개 정보(${esc(data.mobile.fetched)})이고, 추정치는 별도 확인 전까지 날짜와 값을 유지합니다.`)+
      `<div class="gm-toolbar"><label>검색<input id="gm-query" type="search" value="${esc(prefs.query)}" placeholder="게임·개발사·세부 장르"></label><label>장르<select id="gm-mobile-genre">${options([["all","전체 장르"],...genres.map(g=>[g,g])],prefs.mobileGenre)}</select></label><label>가격<select id="gm-paid">${options([["all","무료·유료 전체"],["free","무료 게임"],["paid","유료 게임"]],prefs.paid)}</select></label><label>정렬<select id="gm-sort">${options([["downloads_30d","최근 30일 추정"],["total_estimate","누적 추정"],["installs_lower","공식 누적 하한"],["ratings","평가 수"]],prefs.sort)}</select></label><button id="gm-export">CSV 내려받기</button></div>`+
      panel("장르별 최근 30일 다운로드 · 확보된 표본의 참고 합계",note(`${measured.length}개 게임만 포함. 출처 기준일이 서로 다르고 표본 수도 다르므로 시장 점유율 또는 정확한 동일 기간 합계로 해석하지 않습니다.`)+`<div class="gm-chart"><canvas id="gm-download-genres" role="img" aria-label="확보한 표본의 장르별 최근 30일 다운로드 추정 합계"></canvas></div>`)+
      panel(`게임별 다운로드 · ${records.length}개`,table(["게임","대표 장르","최근 30일 추정","누적 추정","공식 누적 하한","추정 기준일·출처","평점"],tableRows)+`<div class="gm-pagination"><button id="gm-prev" ${prefs.page===0?"disabled":""}>이전</button><span>${prefs.page+1} / ${pages} · 페이지당 30개</span><button id="gm-next" ${prefs.page>=pages-1?"disabled":""}>다음</button></div>`)+
      panel("누적 보급의 관측 이력",`<div class="gm-toolbar"><label>게임<select id="gm-selected">${options(all.map(g=>[g.id,g.name]),prefs.selected||all[0]?.id)}</select></label></div><div id="gm-observation"></div>`)+
      note("공식 누적 하한이 1억에서 5억으로 바뀌어도 그 달에 4억 번 다운로드됐다는 뜻은 아닙니다. 누적 다운로드를 사람 수로 해석하거나 최근 30일 값을 매달 더해 연간 다운로드를 만들지 않습니다.");
    select("#gm-mobile-genre","mobileGenre");select("#gm-sort","sort");select("#gm-paid","paid");select("#gm-selected","selected");
    on("#gm-prev","click",()=>{prefs.page--;render();});
    on("#gm-next","click",()=>{prefs.page++;render();});
    on("#gm-query","input",e=>{const pos=e.target.selectionStart;prefs.page=0;prefs.query=e.target.value;render();const input=root.querySelector("#gm-query");input.focus();input.setSelectionRange(pos,pos);});
    on("#gm-export","click",()=>download("google-play-observations.csv",["id","game","genre","subgenre","rolling_30d_estimate","lifetime_estimate","official_cumulative_lower_bound","estimate_date","listing_fetched","estimate_source","store_source"],records.map(g=>[g.id,g.name,g.genre,g.subgenre,g.downloads_30d,g.total_estimate,g.installs_lower,g.source_updated,g.fetched,g.estimate_url,g.url])));
    chart("gm-download-genres","bar",ranked.map(p=>p[0]),[{label:"최근 30일 추정 다운로드 참고 합계",data:ranked.map(p=>p[1]),backgroundColor:ranked.map((_,i)=>palette[i%palette.length])}]);
    const selected=prefs.selected||all[0]?.id;const history=snapshotPeriods(data.mobile.observations,selected);
    root.querySelector("#gm-observation").innerHTML=note("월별 마지막 관측일의 공식 누적 하한입니다. 실제 월말 값이나 월간 신규 다운로드가 아닙니다. 수집 시작 전 이력은 소급 생성하지 않습니다.")+table(["관측 월","실제 관측일","누적 다운로드 하한","누적 평가 수"],history.map(p=>[p.period,p.date,p.installs_lower!=null?compact(p.installs_lower)+"+":"—",compact(p.ratings)]));
  }
  function renderApple(){
    const apple=data.apple;if(!apple){root.innerHTML=missing("App Store");return;}
    const chartRow=apple.charts.find(c=>c.country===prefs.country&&c.kind===prefs.kind);
    const snapshots=apple.history.filter(h=>h.country===prefs.country&&h.kind===prefs.kind).sort((a,b)=>a.date.localeCompare(b.date));
    const dates=snapshots.map(h=>h.date);
    const chosen=snapshots.find(h=>h.date===prefs.appleDate)||snapshots.at(-1);
    const games=chosen?.games||chartRow?.games||[];
    const genre=g=>appleGenres[g.genre]||g.genre||"미분류";
    const counts=new Map();for(const g of games)counts.set(genre(g),(counts.get(genre(g))||0)+1);
    const ranked=[...counts.entries()].sort((a,b)=>b[1]-a[1]);
    root.innerHTML=header("국가별로 어떤 게임이 차트에 올랐을까?","Apple 공식 게임 전용 Top 100 차트. 무료·유료 게임의 순위이며 다운로드 수나 매출액으로 환산하지 않습니다. 국가를 합쳐 세계 순위를 만들지 않습니다.")+
      `<div class="gm-toolbar"><label>국가<select id="gm-country">${options([["kr","한국"],["us","미국"],["jp","일본"],["cn","중국"]],prefs.country)}</select></label><label>차트<select id="gm-kind">${options([["topfreeapplications","무료 게임"],["toppaidapplications","유료 게임"]],prefs.kind)}</select></label><label>관측일<select id="gm-apple-date">${options(dates.map(d=>[d,d]),chosen?.date||"")}</select></label><button id="gm-export">CSV 내려받기</button></div>`+
      note(`수집 ${esc(chartRow?.fetched||"미수집")} · 피드 기준 ${esc(chartRow?.source_updated||"미확보")} · ${chartRow?link(chartRow.url,"Apple 원본 피드"):"해당 국가·차트 수집 실패"}. 과거 이력은 수집 시작일부터 쌓입니다.`)+
      panel("차트 진입 게임의 장르 구성",note("게임 수 기준 구성입니다. 한 게임이 차지한 다운로드·매출 규모를 가중하지 않습니다. 장르는 Apple 상세 분류 중 첫 번째 게임 세부 장르를 대표로 사용합니다.")+`<div class="gm-chart"><canvas id="gm-apple-genres" role="img" aria-label="App Store 차트의 장르별 게임 수"></canvas></div>`)+
      panel(`${chosen?.date||"현재"} · 게임 차트`,table(["순위","게임","대표 장르"],games.map(g=>[g.rank,link(g.url||`https://apps.apple.com/${prefs.country}/app/id${g.id}`,g.name),esc(genre(g))])));
    select("#gm-country","country");select("#gm-kind","kind");select("#gm-apple-date","appleDate");
    on("#gm-export","click",()=>download(`app-store-${prefs.country}-${chosen?.date||"latest"}.csv`,["observed_date","country","chart","rank","game","genre","id"],games.map(g=>[chosen?.date,prefs.country,prefs.kind,g.rank,g.name,genre(g),g.id])));
    chart("gm-apple-genres","bar",ranked.map(p=>p[0]),[{label:"차트 진입 게임 수",data:ranked.map(p=>p[1]),backgroundColor:ranked.map((_,i)=>palette[i%palette.length])}]);
  }
  function financeSelect(selector,key){on(selector,"change",e=>{financePrefs[key]=e.target.value;render();});}
  function renderRevenue(){
    const revenue=data.revenue;if(!revenue){root.innerHTML=missing("게임별 매출");return;}
    const months=revenue.reports.map(r=>r.month).sort().reverse();
    if(!months.includes(financePrefs.month))financePrefs.month=months[0];
    const {month,store}=financePrefs,report=revenue.reports.find(r=>r.month===month);
    const rows=revenueRows(revenue,month,store),publishers=publisherRevenue(rows),leader=rows[0];
    const stores=[["google_play","Google Play"],["ios","App Store"],["combined","App Store + Google Play"]];
    const storeName=stores.find(([id])=>id===store)[1];
    const available=revenue.games.filter(g=>revenue.reports.some(r=>r.stores[store]?.some(p=>p.id===g.id)));
    if(!available.some(g=>g.id===financePrefs.game))financePrefs.game=leader?.id||available[0]?.id;
    const game=revenue.games.find(g=>g.id===financePrefs.game);
    const timeline=[];
    for(let d=new Date(`${[...months].sort()[0]}-01T00:00:00Z`);d.toISOString().slice(0,7)<=months[0];d.setUTCMonth(d.getUTCMonth()+1))timeline.push(d.toISOString().slice(0,7));
    const history=timeline.map(m=>revenueRows(revenue,m,store).find(r=>r.id===game?.id)?.usd_millions??null);
    const fmtChange=v=>v==null?"—":`${delta(v)}%`;
    root.innerHTML=header("어떤 게임이 얼마나 벌었을까?","공개 월간 보고서의 게임별 스토어 매출 추정치입니다. 스토어 수수료 차감 후 금액이며, 개발비·마케팅비 등을 차감한 순이익은 아닙니다.")+
      `<div class="gm-toolbar"><label>매출 월<select id="gm-rev-month">${options(months.map(m=>[m,m]),month)}</select></label><label>스토어<select id="gm-rev-store">${options(stores,store)}</select></label><button id="gm-export">CSV 내려받기</button></div>`+
      stats([[`${month} · ${storeName} 1위`,esc(leader?.name||"미확보"),`약 ${num(leader?.usd_millions,1)} 백만 달러`],["공개 매출 표본",`${rows.length}개 게임`,`${publishers.length}개 퍼블리셔 · 해당 스토어 Top 10`],["확인한 보고서",`${months.length}개 월`,`${[...months].sort()[0]} ~ ${months[0]} · 중간 미확보 월 있음`]])+
      note(`${link(report.url,"Appfigures 원문")} · ${link(report.image_url,"원본 매출 표")} · 발표 ${esc(report.published)} · 원문 대조 ${esc(report.reviewed)}. 전 세계 집계이지만 중국 전용 앱 등은 해당 버전의 범위입니다. 원스토어·광고·외부 결제 실적은 포함한 것으로 간주하지 않습니다.`)+
      `<div class="gm-grid">${panel(`${month} · 게임별 월 매출 추정`,`<div class="gm-chart gm-chart-tall"><canvas id="gm-revenue-rank" role="img" aria-label="게임별 월간 스토어 매출 추정"></canvas></div>`+note("단위: 백만 달러 · 공표된 반올림 값. 합산 스토어는 원문이 제공한 합계이며, 개별 스토어 Top 10을 더해 생성하지 않습니다."))}${panel("이 게임들을 서비스하는 퍼블리셔",table(["퍼블리셔","확인 게임 수","표본 소계 (백만 $)"],publishers.map(p=>[`${esc(p.publisher)}<small>${esc(p.games.join(" · "))}</small>`,p.games.length,num(p.value,1)]))+note("선택 월·스토어의 Top 10에 등장한 게임만 합산했습니다. 이 표는 퍼블리셔 전체 매출·개발사 수취액·로열티 배분을 뜻하지 않습니다. King·Supercell 등은 각 서비스 브랜드로 표시합니다."))}</div>`+
      panel("게임별 추정치와 변화",table(["순위·게임","퍼블리셔","대표 장르","월 매출 (백만 $)","전월 대비","전년 동월 대비"],rows.map(r=>[`${r.rank}. ${esc(r.name)}<small>${esc(r.scope)}</small>`,esc(r.publisher),esc(r.genre),num(r.usd_millions,1),fmtChange(revenueChange(revenue,r.id,month,store,1)),fmtChange(revenueChange(revenue,r.id,month,store,12))]))+note("전월·전년 동월에 같은 앱·스토어의 공개 값이 있어야 변화율을 계산합니다. 순위 밖 게임과 미확보 월은 0이 아닙니다. 앱 버전 간 범위 차이는 원문을 함께 확인하세요."))+
      panel("같은 게임의 매출 추이",`<div class="gm-toolbar"><label>게임<select id="gm-rev-game">${options(available.map(g=>[g.id,g.name]),financePrefs.game)}</select></label></div>`+note(`${esc(game?.scope||"")} · ${storeName} · 미확보 월은 선을 연결하지 않습니다.`)+`<div class="gm-chart"><canvas id="gm-revenue-history" role="img" aria-label="선택 게임의 월간 매출 추정 이력"></canvas></div>`+table(["관측 월","월 매출 (백만 $)","출처"],revenue.reports.map(r=>{const p=revenueRows(revenue,r.month,store).find(p=>p.id===game?.id);return [r.month,p?num(p.usd_millions,1):"미확보",link(r.url,"월간 보고서")];})))+
      panel("공식 발표에서 확인한 개별 게임 매출",table(["게임·회사","실적 기간","공식 매출 (백만 USD)","범위","출처"],(revenue.official_games||[]).map(r=>[`${esc(r.name)}<small>${esc(r.publisher)}</small>`,`${esc(r.period)}<small>${r.start} ~ ${r.date}</small>`,usdMoney(r.revenue_millions,r.currency,r,data.fx),esc(r.scope),link(r.url,`${r.published} 공식 발표`)]))+note("금액에 마우스를 올리거나 누르면 원통화·기간 평균환율을 확인할 수 있습니다. 공식 회사 매출과 위 스토어 추정치는 기준이 달라 합산하지 않습니다. 게임 이익이 따로 공시되지 않으면 추산하지 않습니다. Steam 개별 게임 매출은 무료 연속 자료 미확보입니다."));
    financeSelect("#gm-rev-month","month");financeSelect("#gm-rev-store","store");financeSelect("#gm-rev-game","game");
    on("#gm-export","click",()=>download(`game-revenue-${store}-${month}.csv`,["month","store","rank","game","publisher","genre","estimated_net_store_revenue_usd_millions","MoM_pct","YoY_pct","app_scope","source","published","reviewed"],rows.map(r=>[month,store,r.rank,r.name,r.publisher,r.genre,r.usd_millions,revenueChange(revenue,r.id,month,store,1),revenueChange(revenue,r.id,month,store,12),r.scope,report.url,report.published,report.reviewed])));
    chart("gm-revenue-rank","bar",rows.map(r=>r.name.split(" · ")[0]),[{label:"월 매출 추정 (백만 $)",data:rows.map(r=>r.usd_millions),backgroundColor:palette[0]}],{horizontal:true,decimals:1});
    chart("gm-revenue-history","line",timeline,[{label:`${game?.name} (백만 $)`,data:history,borderColor:palette[0],backgroundColor:palette[0],pointRadius:5,spanGaps:false}],{decimals:1});
  }
  function renderCompanies(){
    const financials=data.companies;if(!financials){root.innerHTML=missing("게임사 실적");return;}
    const companies=financials.companies.filter(c=>c.rows.length&&(financePrefs.complex==="include"||c.compare_default!==false));
    const dates=[...new Set(companies.flatMap(c=>c.rows.filter(r=>r.kind===financePrefs.kind).map(r=>r.date)))].sort().reverse();
    if(!dates.includes(financePrefs.date))financePrefs.date=dates[0]||"";
    if(!companies.some(c=>c.id===financePrefs.company))financePrefs.company=companies.find(c=>c.rows.some(r=>r.kind===financePrefs.kind&&r.date===financePrefs.date))?.id||companies[0]?.id;
    const {kind,date:chosenDate,company:chosenCompany,metric}=financePrefs;
    const selected=companies.find(c=>c.id===chosenCompany);
    const metrics=[["revenue","매출"],["operating_profit","영업이익"],["net_income","순이익"]],metricName=metrics.find(([id])=>id===metric)[1];
    const value=(c,r,key)=>usdAmount(r?.[key],c.currency,r,data.fx);
    const money=(c,r,key,suffix="")=>usdMoney(r?.[key],c?.currency,r,data.fx,suffix);
    const ordered=companies.map(c=>({c,r:c.rows.find(r=>r.kind===kind&&r.date===chosenDate)})).sort((a,b)=>(value(b.c,b.r,metric)??-Infinity)-(value(a.c,a.r,metric)??-Infinity));
    const measured=ordered.filter(p=>value(p.c,p.r,metric)!=null);
    const history=selected?.rows.filter(r=>r.kind===kind)||[],series=companySeries(history,kind);
    const unit="백만 USD",margin=r=>r?.operating_profit!=null&&r.revenue>0?r.operating_profit/r.revenue*100:null;
    const detail=history.find(r=>r.date===chosenDate),ref=r=>r?.refs?.revenue||Object.values(r?.refs||{})[0];
    const dateLabel=d=>kind==="annual"?`${d} 결산 연간`:`${d} 종료 분기`;
    const directory=directoryRows(financials.companies,financePrefs),regions=[...new Set(financials.companies.map(c=>c.region))].sort();
    const latest=c=>c.rows.at(-1);
    const growth=(c,r)=>{const usd=usdGrowth(c,r,data.fx),original=companyGrowth(c.rows,r);return usd==null?"—":memoValue(`${delta(usd)}%`,[`USD 기준 매출 YoY: ${delta(usd)}%`,`원통화 ${c.currency} 기준 YoY: ${original==null?"미확보":delta(original)+"%"}`,"각 비교 기간의 평균환율 적용 · 환율 변동 영향 포함"]);};
    root.innerHTML=header("세계 게임사와 플랫폼의 실적","국내·해외 업체의 매출과 이익을 USD로 비교합니다. 원통화와 실제 실적 기간은 보존하며, 비상장사도 공개 지표가 있으면 목록에 포함합니다.")+
      stats([["관측 업체",`${financials.companies.length}곳`,`${new Set(financials.companies.map(c=>c.country)).size}개 국가 · 공시 이력 ${financials.companies.filter(c=>c.rows.length).length}곳`],["해외 업체",`${financials.companies.filter(c=>c.country!=="한국").length}곳`,"미국·일본·중국·유럽·동남아 등"],["비상장 플랫폼",`${financials.companies.filter(c=>c.listing==="private"&&c.platform_id).length}곳`,"Epic Games · Valve/Steam 공개 사업 지표"]])+
      panel("전체 업체 목록",`<div class="gm-toolbar"><label>지역<select id="gm-directory-region">${options([["all","전 세계"],...regions.map(r=>[r,r])],financePrefs.region)}</select></label><label>사업<select id="gm-directory-role">${options([["all","모든 사업"],...Object.entries(roleNames)],financePrefs.role)}</select></label><label>업체·IP 검색<input id="gm-directory-query" type="search" value="${esc(financePrefs.query)}" placeholder="Nintendo, Unity, Unreal, Steam…"></label></div>`+
        note(`${directory.length}곳 표시 · 금액 단위: 백만 USD. 업체별 최근 보유 실적이므로 연간·분기와 결산일이 다를 수 있습니다. 금액에 마우스를 올리거나 누르면 원통화와 환산 근거가 나옵니다.`)+
        table(["업체·지역","사업·공개 범위","최근 보유 실적","매출 (USD)","영업이익 (USD)","보기"],directory.map(c=>{const r=latest(c);return [
          `${esc(c.name)}<small>${esc(c.country)} · ${listingName(c.listing)}${c.listing_url?` · ${link(c.listing_url,"전환 근거")}`:""}</small>`,`${esc(c.roles?.map(r=>roleNames[r]).join(" · ")||"")}<small>${esc(c.scope||c.brands)}</small>`,r?`${esc(r.period)}<small>${r.date} 종료 · ${r.kind==="annual"?"연간":"분기"}</small>`:"정기 손익 미확보",r?money(c,r,"revenue"):"미공개",r?money(c,r,"operating_profit"):"미공개",r?`<button data-company-open="${esc(c.id)}">실적 보기</button>`:c.platform_id?`<button data-platform-open="${esc(c.platform_id)}">공개 지표 보기</button>`:"미확보"
        ];})))+
      `<div id="gm-financial-comparison"></div>`+
      `<div class="gm-toolbar"><label>기간<select id="gm-fin-kind">${options([["quarter","분기 단독"],["annual","회계연도 연간"]],kind)}</select></label><label>결산일<select id="gm-fin-date">${options(dates.map(d=>[d,dateLabel(d)]),chosenDate)}</select></label><label>비교 지표<select id="gm-fin-metric">${options(metrics,metric)}</select></label><label>복합기업<select id="gm-fin-complex">${options([["exclude","Microsoft·Sea·Tencent 제외"],["include","Microsoft·Sea·Tencent 포함"]],financePrefs.complex)}</select></label><button id="gm-export">CSV 내려받기</button></div>`+
      note(`금액 단위: ${unit}. 결산일이 같은 분기·연간 실적을 실제 실적 기간의 평균환율로 환산합니다. USD 공시 금액은 그대로 사용합니다. EA·Take-Two 등은 3월 결산으로 FY와 달력 연도가 다릅니다. ${financials.companies.length}개 회사 추적 · 자동 자료 확인 ${esc(financials.checked)}.`)+
      panel(`${chosenDate||"미확보"} · ${metricName} 비교`,`<div class="gm-chart"><canvas id="gm-company-compare" role="img" aria-label="USD 기준 같은 결산일의 게임사 실적 비교"></canvas></div>`+table(["게임사·주요 브랜드","매출 (USD)","영업이익 (USD)","순이익 (USD)","영업이익률","매출 YoY (USD)","기간·출처"],ordered.map(({c,r})=>[
        `<button class="gm-company-pick" data-company="${esc(c.id)}" ${c.id===chosenCompany?'aria-pressed="true"':'aria-pressed="false"'}>${esc(c.name)}</button><small>${esc(c.brands)}</small>`,money(c,r,"revenue"),money(c,r,"operating_profit"),money(c,r,"net_income"),margin(r)==null?"—":`${num(margin(r),1)}%`,r?growth(c,r):"—",r?`${esc(r.period)}<small>${link(ref(r)?.url,`${ref(r)?.filed||""} 공시·발표`)}</small>`:`미확보<small>최근 보유: ${esc(c.rows.filter(p=>p.kind===kind).at(-1)?.date||"없음")}</small>`]))+note("YoY는 USD 기준으로 환율 영향이 포함됩니다. 증가율을 누르면 원통화 기준 YoY도 확인할 수 있습니다. 영업이익률은 원통화 비율과 같습니다. 미공개·수집 누락·환율 미확보는 0으로 채우지 않습니다. 인수·매각·회계 변경과 순이익 범위는 원문을 확인하세요."))+
      panel(`${esc(selected?.name||"회사 선택")} · 실적 추이`,`<div class="gm-toolbar"><label>상세 회사<select id="gm-fin-company">${options(companies.map(c=>[c.id,c.name]),chosenCompany)}</select></label></div>`+
        stats([["선택 기간 매출",money(selected,detail,"revenue"),`${chosenDate||"미확보"} · ${unit}`],["영업이익",money(selected,detail,"operating_profit"),`${unit} · 영업이익률 ${margin(detail)==null?"—":num(margin(detail),1)+"%"}`],["순이익",money(selected,detail,"net_income"),`${unit} · 회계상 이익`]])+
        note(`${esc(selected?.scope||selected?.brands||"")} · 순이익 기준: ${esc(selected?.net_income_basis||"공시 계정 기준")} · ${history.length}개 ${kind==="quarter"?"분기":"연간"} 관측 · FY는 결산연도 기준입니다. ${esc(financialStatus(selected||{}))} ${selected?.fetched?`· 마지막 수집/원문 대조 ${esc(selected.fetched)}`:""}`)+
        `<div class="gm-chart gm-chart-tall"><canvas id="gm-company-history" role="img" aria-label="선택 회사의 매출 영업이익 순이익 추이"></canvas></div>`+
        table(["실적 기간","매출 (USD)","영업이익 (USD)","순이익 (USD)","영업이익률","계산·출처"],history.slice(-16).reverse().map(r=>[`${esc(r.period)}<small>${r.start} ~ ${r.date}</small>`,money(selected,r,"revenue"),money(selected,r,"operating_profit"),money(selected,r,"net_income"),margin(r)==null?"—":`${num(margin(r),1)}%`,`${esc(calculationName(ref(r)?.calculation))}<small>${link(ref(r)?.url,`${ref(r)?.filed||""} 원문`)}</small>`]))+note("단위: 백만 USD. 표는 최근 16개 기간, CSV는 비교 대상 업체의 선택 기간 유형 전체 이력입니다. 원통화 공시의 3개월 값을 우선 사용하고 필요한 경우 같은 FY의 연간−9개월로 분기를 계산한 뒤 환산합니다. 연간을 4로 나누지 않습니다."))+
      panel("환산 기준",note(`${link(data.fx?.source_page||"https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html","ECB 공개 일별 기준환율")} · 각 실적 시작일~종료일의 고시일마다 원통화/EUR ÷ USD/EUR을 구하고, 그 일별 원통화/USD의 산술평균으로 원금액을 나눕니다. 주말·휴일은 추가하지 않습니다. 연간은 해당 회계연도 전체 고시일 평균이며 분기 평균을 단순 평균하지 않습니다. 원통화가 USD이면 재환산하지 않습니다. 환산액은 비교용이며 회사가 공시한 USD 실적과 차이가 날 수 있습니다. 연간 환산액과 각 분기 환산액의 합도 평균환율 차이로 일치하지 않을 수 있습니다.`)+note(`환율 조회: ${esc(data.fx?.fetched||"미확보")} · ${Object.keys(data.fx?.periods||{}).length}개 기간 · 미확보 ${data.fx?.missing?.length??"확인 필요"}개${data.fx?.status!=="ok"?" · 최근 수집 불완전: 기존 확보 기간을 유지하고 새 미확보 기간은 표시하지 않습니다.":""}`))+
      panel("게임별 추정 매출과 함께 읽기",note(`비상장사와 비공개 타이틀의 매출·이익을 모두 확보할 수는 없습니다. ${link("#/games/revenue","게임별 매출")}에서 공개된 스토어 추정치와 공식 타이틀 매출을 확인하세요. 스토어 추정치의 퍼블리셔별 소계와 이 화면의 연결 매출은 범위와 인식 기준이 달라 합산하지 않습니다.`));
    financeSelect("#gm-fin-kind","kind");financeSelect("#gm-fin-date","date");financeSelect("#gm-fin-metric","metric");financeSelect("#gm-fin-company","company");financeSelect("#gm-fin-complex","complex");
    financeSelect("#gm-directory-region","region");financeSelect("#gm-directory-role","role");
    on("#gm-directory-query","input",e=>{const pos=e.target.selectionStart;financePrefs.query=e.target.value;render();const input=root.querySelector("#gm-directory-query");input.focus();input.setSelectionRange(pos,pos);});
    root.querySelectorAll("[data-company-open]").forEach(button=>button.addEventListener("click",()=>{const c=financials.companies.find(c=>c.id===button.dataset.companyOpen),r=latest(c);Object.assign(financePrefs,{company:c.id,kind:r.kind,date:r.date,complex:c.compare_default===false?"include":financePrefs.complex});render();root.querySelector("#gm-financial-comparison").scrollIntoView({block:"start"});},{signal:renderEvents.signal}));
    bindPlatformButtons();
    root.querySelectorAll("[data-company]").forEach(button=>button.addEventListener("click",()=>{financePrefs.company=button.dataset.company;render();root.querySelector("#gm-fin-company").focus();},{signal:renderEvents.signal}));
    on("#gm-export","click",()=>download(`game-companies-USD-${kind}.csv`,["company","kind","period","start","end","revenue_usd_millions","operating_profit_usd_millions","net_income_usd_millions","original_currency","original_unit","original_revenue","original_operating_profit","original_net_income","operating_margin_pct","revenue_YoY_usd_pct","revenue_YoY_original_pct","fx_local_per_usd","fx_method","fx_observations","fx_first","fx_last","fx_fetched","fx_source","revenue_source","operating_profit_source","net_income_source","revenue_calculation","checked"],companies.flatMap(c=>c.rows.filter(r=>r.kind===kind).map(r=>{const q=fxQuote(data.fx,c.currency,r);return [c.name,r.kind,r.period,r.start,r.date,...metrics.map(([key])=>value(c,r,key)),c.currency,"millions",r.revenue,r.operating_profit,r.net_income,margin(r),usdGrowth(c,r,data.fx),companyGrowth(c.rows,r),q?.local_per_usd,q?.method,q?.observations,q?.first,q?.last,q?.fetched,q?.source,r.refs?.revenue?.url,r.refs?.operating_profit?.url,r.refs?.net_income?.url,r.refs?.revenue?.calculation,c.checked];}))));
    chart("gm-company-compare","bar",measured.map(p=>p.c.name),[{label:`${metricName} (${unit})`,data:measured.map(p=>value(p.c,p.r,metric)),moneyNotes:measured.map(p=>moneyMemo(p.r[metric],p.c.currency,p.r,data.fx)),backgroundColor:measured.map(p=>p.r[metric]<0?palette[4]:palette[0])}],{signed:true,decimals:1});
    chart("gm-company-history","line",series.map(p=>p.label),metrics.map(([key,label],i)=>({label:`${label} (${unit})`,data:series.map(p=>value(selected,p.row,key)),moneyNotes:series.map(p=>moneyMemo(p.row?.[key],selected?.currency,p.row,data.fx)),borderColor:palette[i],backgroundColor:palette[i],pointRadius:3,borderWidth:2,spanGaps:false})),{signed:true,decimals:1});
  }
  function bindPlatformButtons(){
    root.querySelectorAll("[data-platform-open]").forEach(button=>button.addEventListener("click",()=>{financePrefs.platform=button.dataset.platformOpen;financePrefs.platformMetric="";location.hash="#/games/platforms";},{signal:renderEvents.signal}));
  }
  function renderPlatforms(){
    const platforms=data.platforms;if(!platforms){root.innerHTML=missing("게임 플랫폼");return;}
    const profiles=platforms.profiles;
    const profile=profiles.find(p=>p.id===financePrefs.platform)||profiles[0];financePrefs.platform=profile.id;
    const company=data.companies?.companies.find(c=>c.id===profile.company_id);
    const rows=platformMetrics(platforms,profile.id),groups=new Map();
    for(const r of rows){if(!groups.has(r.id))groups.set(r.id,[]);groups.get(r.id).push(r);}
    for(const group of groups.values())group.sort((a,b)=>a.period.localeCompare(b.period));
    if(!groups.has(financePrefs.platformMetric))financePrefs.platformMetric=groups.keys().next().value||"";
    const history=groups.get(financePrefs.platformMetric)||[],metric=history.at(-1),latest=[...groups.values()].map(g=>g.at(-1));
    const financial=company?.rows.at(-1);
    const metricUnit=r=>monetaryMetric(r)?"백만 USD":r.unit;
    const metricValue=r=>monetaryMetric(r)?usdAmount(r.value,metricCurrency(r),r,data.fx):r.value;
    const metricText=r=>`${r.lower_bound?"초과 ":""}${monetaryMetric(r)?usdMoney(r.value,metricCurrency(r),r,data.fx," 백만 USD"):`${num(r.value,2)} ${esc(r.unit)}`}`;
    const kindName=r=>({revenue:"공시 매출",spend:"이용자 지출·거래액",creator_income:"창작자 수익",activity:"활성 이용",cumulative:"누적 규모",concurrency:"동시 온라인",units:"판매 대수"}[r.kind]||"공개 지표");
    const stamp=r=>r.observed_at?`${new Date(r.observed_at).toLocaleString("ko-KR",{timeZone:"Asia/Seoul"})} KST 관측`:r.published?`${esc(r.published)} 발표`:`${esc(r.reviewed||platforms.reviewed)} 원문 대조`;
    root.innerHTML=header("게임을 만들고, 유통하고, 수익화하는 플랫폼","엔진·스토어·콘솔·UGC·광고 플랫폼을 함께 봅니다. 회사 매출, 스토어 거래액, 창작자 수익, 이용자 수는 각각 다른 지표입니다.")+
      `<div class="gm-toolbar"><label>플랫폼<select id="gm-platform-choice">${options(profiles.map(p=>[p.id,p.name]),profile.id)}</select></label><button id="gm-platform-export">공개 지표 CSV</button></div>`+
      panel("플랫폼 업체 지도",table(["업체·운영사","사업","소유·공개 범위","수익 구조"],profiles.map(p=>[
        `<button class="gm-platform-pick" data-platform-pick="${esc(p.id)}" aria-pressed="${profile.id===p.id}">${esc(p.name)}</button><small>${esc(p.operator)} · ${esc(p.country)}</small>`,esc(p.roles.map(r=>roleNames[r]).join(" · ")),`${listingName(p.listing)}<small>${p.listing==="private"?"공개 사업 지표 관측":"공시 재무·사업 지표"}</small>`,esc(p.model)
      ])))+
      `<section id="gm-platform-detail" class="gm-panel"><h3>${esc(profile.name)}</h3><p class="gm-note">${esc(profile.products)}<br>${esc(profile.scope)} ${link(profile.url,"공식 자료")}</p>`+
      (financial?stats([[`${esc(company.name)} · ${financial.period} 매출`,usdMoney(financial.revenue,company.currency,financial,data.fx),`백만 USD · ${financial.date} 종료`],["영업이익",usdMoney(financial.operating_profit,company.currency,financial,data.fx),"백만 USD"],["순이익",usdMoney(financial.net_income,company.currency,financial,data.fx),`백만 USD · ${company.net_income_basis||"공시 계정 기준"}`]])+note(`${esc(company.scope||company.brands)} · ${link(financial.refs.revenue.url,"해당 실적 원문")} <button id="gm-platform-financial">분기·연간 실적 보기</button>`):note("전사 정기 손익 미확보. 아래의 공식 사업 지표를 관측하며 거래액에 수수료율을 곱해 회사 매출·이익을 추산하지 않습니다."))+
      note("금액은 백만 USD입니다. 마우스를 올리거나 누르면 원통화·실적 기간·평균환율을 확인할 수 있습니다. 이용자 수·계정·판매 대수의 원래 단위는 유지합니다.")+
      (latest.length?table(["최근 공개 지표","값","유형","기간·범위","기준일·출처"],latest.map(r=>[esc(r.label),metricText(r),kindName(r),`${esc(r.period)}<small>${esc(r.scope)}</small>`,`${stamp(r)}<small>${link(r.url,"공식 원문")}</small>`])):note("플랫폼의 연결 재무는 위에서 확인할 수 있습니다. 사업별 매출·이용자 수는 무료 공개 원문을 확인한 항목부터 추가합니다."))+`</section>`+
      (history.length?panel("같은 지표의 공개 이력",`<div class="gm-toolbar"><label>지표<select id="gm-platform-metric">${options([...groups].map(([id,g])=>[id,`${g[0].label} (${metricUnit(g[0])})`]),financePrefs.platformMetric)}</select></label></div>`+
        note(`${esc(metric?.label||"")} · ${esc(metric?metricUnit(metric):"")}. 미공개 기간은 보간하지 않습니다.${profile.id==="steam"?" 관측일은 UTC이며, 점은 조회 시 표시값입니다. 월별 최고치·평균 동접·MAU로 환산하지 않습니다.":" 회계연도(FY)와 달력 연도를 구분합니다. ‘초과’ 값은 원문의 하한을 그립니다."}`)+
        `<div class="gm-chart"><canvas id="gm-platform-metric-history" role="img" aria-label="선택 플랫폼의 동일 지표 공개 이력"></canvas></div>`+
        table(["관측·실적 기간","값","기준일·출처"],history.map(r=>[esc(r.period),metricText(r),`${stamp(r)}<small>${link(r.url,"공식 원문")}</small>`]))):"")+
      note(`Steam 동시 온라인만 매일 조회해 누적합니다. 그 외 사업 지표는 공개 발표를 원문 대조한 자료입니다.${platforms.steam?.status!=="ok"?` Steam 최근 조회 실패: 이전 관측일과 값을 유지합니다.`:""} ${link("#/games/companies","전체 해외·국내 게임사 실적 보기")}`);
    financeSelect("#gm-platform-choice","platform");financeSelect("#gm-platform-metric","platformMetric");
    root.querySelectorAll("[data-platform-pick]").forEach(button=>button.addEventListener("click",()=>{financePrefs.platform=button.dataset.platformPick;financePrefs.platformMetric="";render();root.querySelector("#gm-platform-detail").scrollIntoView({block:"start"});},{signal:renderEvents.signal}));
    on("#gm-platform-financial","click",()=>{Object.assign(financePrefs,{company:company.id,kind:financial.kind,date:financial.date,complex:company.compare_default===false?"include":financePrefs.complex});location.hash="#/games/companies";});
    on("#gm-platform-export","click",()=>download(`game-platform-${profile.id}.csv`,["platform","operator","listing","metric","kind","value","unit","original_value","original_unit","fx_local_per_usd","fx_method","fx_observations","fx_fetched","fx_source","lower_bound_exclusive","period","start","end","scope","observed_at_UTC","published","reviewed","source"],rows.map(r=>{const q=monetaryMetric(r)?fxQuote(data.fx,metricCurrency(r),r):null;return [profile.name,profile.operator,listingName(profile.listing),r.label,r.kind,metricValue(r),metricUnit(r),r.value,r.unit,q?.local_per_usd,q?.method,q?.observations,q?.fetched,q?.source,!!r.lower_bound,r.period,r.start,r.date,r.scope,r.observed_at,r.published,r.reviewed,r.url];})));
    if(history.length)chart("gm-platform-metric-history","line",history.map(r=>r.period),[{label:`${metric.label} (${metricUnit(metric)})`,data:history.map(metricValue),moneyNotes:history.map(r=>monetaryMetric(r)?moneyMemo(r.value,metricCurrency(r),r,data.fx):[]),borderColor:palette[0],backgroundColor:palette[0],pointRadius:5,spanGaps:false,showLine:profile.id!=="steam"}],{decimals:2});
  }
  function renderSources(){
    root.innerHTML=header("출처와 관측 범위","공개 데이터의 실제 값·추정치·순위를 구분합니다. 유료 API, 체험판, 개발자 계정 실적은 사용하지 않습니다.")+
      panel("현재 연결한 자료",table(["자료","범위·단위","갱신","한계"],[
        [link("https://newzoo.com/articles/global-games-market-2025","Newzoo 공개 발표"),"세계 시장 · 연간 십억 달러","공개 발표 확인 시 수기 반영","시장 규모 추정치. 과거 공시 인용판과 분리"],
        [link("https://steamcharts.com/","SteamCharts"),`${data.steam?.games.length||0}개 고정 표본 · 월평균/월 최고 동접`,esc(data.steam?.fetched||"미수집"),"전체 Steam 시장이 아닌 선택 표본. 평균 동접 ≠ MAU"],
        [link("https://play.google.com/store/games","Google Play 공개 목록"),`${data.mobile?.games.length||0}개 표본 · 누적 다운로드 하한·평점`,esc(data.mobile?.fetched||"미수집"),"장르별 공개 목록에서 발견한 표본. 누적 하한 차이 ≠ 월 다운로드"],
        [link("https://www.appbrain.com/","AppBrain 공개 프로필"),`${data["download-estimates"]?.observations.length||0}개 표본 · 최근 30일·누적 추정`,`${esc(data["download-estimates"]?.observed_at||"미확인")} 공개 화면 확인 · 수기`,"반올림 추정. 기준일이 다름. 자동 조회 제한으로 수기 확인 유지"],
        [link("https://rss.marketingtools.apple.com/","Apple 공식 게임 RSS"),"4개국 무료·유료 게임 Top 100",esc(data.apple?.fetched||"미수집"),"다운로드·매출액 없음. 순위와 장르 구성만 관측"],
        [link("https://appfigures.com/resources/tagged/games","Appfigures 공개 월간 보고서"),`${data.revenue?.reports.length||0}개 월 · 스토어별 Top 10 매출 추정`,`${esc(data.revenue?.reviewed||"미확인")} 원본 표 대조 · 수기`,"수수료 차감 후 스토어 매출 추정. 전체 게임·전체 퍼블리셔 실적 아님"],
        [link("https://www.sec.gov/edgar/sec-api-documentation","SEC Company Facts"),"EA·Take-Two·Roblox·Unity·AppLovin·Microsoft·Sea·Playtika·NetEase·Gravity 연결 재무",esc(data.companies?.checked||"미수집"),"공시 원통화 · 외국 상장사는 연간만 있거나 구조화 공시가 늦을 수 있음"],
        [link("https://opendart.fss.or.kr/","OpenDART 연결 재무"),"크래프톤·넷마블·NC·펄어비스·컴투스", "무료 공시 API · 기존 CI 키 사용", "공시 발표 후 갱신 · 손익계산서 3개월 값과 누적값 구분"],
        ["공식 IR·보도자료", "Nintendo·Sony G&NS·Bandai Namco·SEGA·Square Enix·Konami·Capcom·CD PROJEKT·Tencent·Nexon 등", "원문 대조 후 수기 반영", "회사·부문·계속영업 범위를 표시 · 수기 자료는 확인일 유지"],
        [link(data.fx?.source_page||"https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html","ECB 공개 일별 환율"),"KRW·JPY·CNY·PLN → USD · 실제 실적 기간의 고시일 평균",esc(data.fx?.fetched||"미확보"),"원통화/USD의 일별 교차환율 평균으로 환산 · 원통화 보존 · USD 공시 금액은 그대로 · 환율 미확보는 결측"],
        [link("https://store.epicgames.com/en-US/news/epic-games-store-2025-year-in-review","Epic Games 공개 연간 보고서"), "EGS 지출·이용자·계정 · Fab 창작자 수익", `${esc(data.platforms?.reviewed||"미확인")} 원문 대조`, "전사·Unreal Engine 매출·순이익으로 간주하지 않음"],
        [link("https://store.steampowered.com/stats/?l=english","Steam 공식 온라인 통계"), "Steam 동시 온라인·화면 표시 최고값", esc(data.platforms?.steam?.fetched||"미확보"), "회사 매출·거래액·MAU 아님 · 조회 시점 관측값"],
        ["원스토어·Steam 개별 게임 매출","연속 무료 자료 미확보","—","0으로 처리하거나 다른 스토어로 추정해 채우지 않음"]]))+
      panel("비교하는 방법",`<ul class="gm-reading"><li><b>장르 합계에는 대표 장르 하나만</b><p>Steam은 게임 플레이 기준 수동 분류, 모바일 추정 표본은 대표 장르와 세부 장르, 나머지 목록은 스토어 분류를 사용합니다. 플랫폼 간 분류가 완전히 같지는 않습니다.</p></li><li><b>다운로드와 이용량을 함께 읽기</b><p>다운로드는 유입, 누적은 보급, 동시접속자는 동시 이용을 보여줍니다. 플랫폼을 넘겨 합산하거나 이용자 수로 환산하지 않습니다.</p></li><li><b>표본과 결측 확인</b><p>선정한 게임과 현재 스토어에 남아 있는 게임 중심의 표본 편향이 있습니다. 출시 전과 누락된 달은 관측값 없음으로 남기며 보간하지 않습니다.</p></li><li><b>매출과 잠재 시장 구분</b><p>무료 스토어 자료만으로 광고·외부 결제·타 PC 스토어를 포함한 전 세계 실매출을 복원할 수 없습니다. 전체 시장은 별도의 공개 시장 규모 자료로 봅니다.</p></li></ul>`)+
      panel("최근 자동 수집의 누락",table(["소스","실패 항목 수","처리"],[["SteamCharts",data.steam?.errors.length??"—","기존 성공값과 실제 수집일 유지"],["Google Play",data.mobile?.errors.length??"—","기존 값 유지 또는 미확보 표시"],["Apple RSS",data.apple?.errors.length??"—","국가·차트별 기존 성공값 유지"]]))+
      panel("게임사별 자료 상태",table(["게임사","최근 보유 실적","확인일","수집 상태"],(data.companies?.companies||[]).map(c=>[esc(c.name),esc(c.rows.at(-1)?.date||"미확보"),esc(c.checked),esc(financialStatus(c))])));
  }
  return ()=>{alive=false;abort.abort();renderEvents.abort();destroy();root.classList.remove("gm-root");};
}
