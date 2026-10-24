/* Public game market observatory. All metrics keep their source and denominator. */
const palette = ["#2a78d6","#1baf7a","#eda100","#4a3aa7","#e34948","#008300","#e87ba4","#eb6834","#5597a5","#8b764e","#7c8a24","#795cb5"];
const prefs = {grain:"month",metric:"share",from:"2020-01",to:"",steamGenre:"all",mobileGenre:"all",query:"",sort:"downloads_30d",country:"kr",kind:"topfreeapplications",appleDate:"",selected:"",paid:"all",page:0};
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

export function mount(root,{view="overview",tabsRoot}={}){
  const abort=new AbortController();let renderEvents=new AbortController(),alive=true, charts=[],data=null;
  const destroy=()=>{charts.forEach(c=>c.destroy());charts=[];};
  const on=(selector,event,fn)=>root.querySelector(selector)?.addEventListener(event,fn,{signal:renderEvents.signal});
  const select=(selector,key)=>on(selector,"change",e=>{prefs[key]=e.target.value;prefs.page=0;render();});
  const status=document.createElement("p");status.className="page-loading";status.textContent="게임 시장 공개 데이터 불러오는 중…";root.append(status);
  if(tabsRoot){tabsRoot.innerHTML=`<nav class="commodity-tabs gm-tabs" aria-label="게임 시장 화면">${[["overview","시장 규모"],["steam","Steam 장르"],["mobile","모바일 다운로드"],["apple","App Store 차트"],["sources","출처·범위"]].map(([id,name])=>`<a href="#/games/${id}" class="${view===id?"active":""}" ${view===id?'aria-current="page"':""}>${name}</a>`).join("")}</nav>`;}
  const names=["market","steam","mobile","apple","download-estimates"];
  Promise.all(names.map(async name=>{try{const r=await fetch(`data/games/${name}.json`,{signal:abort.signal});if(!r.ok)throw Error(`HTTP ${r.status}`);return [name,await r.json()];}catch(e){if(e.name==="AbortError")throw e;return[name,null];}})).then(entries=>{
    if(!alive)return;data=Object.fromEntries(entries);render();
    const dates=[data.steam?.fetched,data.mobile?.fetched,data.apple?.fetched].filter(Boolean);
    document.getElementById("last-updated").textContent=`게임 자동 수집 ${dates.sort().at(-1)||"미수집"} · 추정치 기준일은 각 행 표시`;
  }).catch(e=>{if(alive)status.textContent=`데이터를 불러오지 못했습니다: ${e.message}`;});
  function chart(id,type,labels,datasets,{percentAxis=false,stacked=false,horizontal=false}={}){
    const canvas=root.querySelector(`#${id}`);if(!canvas)return;
    if(!window.Chart){canvas.replaceWith(Object.assign(document.createElement("p"),{textContent:"차트 라이브러리를 불러오지 못했습니다. 아래 표에서 값을 확인할 수 있습니다."}));return;}
    const ink=getComputedStyle(document.documentElement).getPropertyValue("--ink-2").trim();
    const grid=getComputedStyle(document.documentElement).getPropertyValue("--grid").trim();
    charts.push(new window.Chart(canvas,{type,data:{labels,datasets},options:{responsive:true,maintainAspectRatio:false,animation:false,indexAxis:horizontal?"y":"x",interaction:{mode:"index",intersect:false},plugins:{legend:{position:"bottom",display:datasets.length>1,labels:{color:ink,boxWidth:12}},tooltip:{callbacks:{label:c=>`${c.dataset.label}: ${num(horizontal?c.parsed.x:c.parsed.y,percentAxis?1:0)}${percentAxis?"%":""}`}}},scales:{x:{stacked,ticks:{color:ink,maxTicksLimit:12},grid:{display:false}},y:{stacked,min:0,max:percentAxis?100:undefined,ticks:{color:ink,callback:v=>percentAxis?`${v}%`:compact(v)},grid:{color:grid}}}}}));
  }
  function header(title,description){return `<div class="gm-intro"><h2>${title}</h2><p>${description}</p></div>`;}
  function panel(title,body,extra=""){return `<section class="gm-panel ${extra}"><h3>${title}</h3>${body}</section>`;}
  function table(headers,rows){return `<div class="gm-table-wrap"><table class="gm-table"><thead><tr>${headers.map(h=>`<th scope="col">${h}</th>`).join("")}</tr></thead><tbody>${rows.length?rows.map(r=>`<tr>${r.map(c=>`<td>${c}</td>`).join("")}</tr>`).join(""):`<tr><td colspan="${headers.length}">조건에 맞는 관측값이 없습니다.</td></tr>`}</tbody></table></div>`;}
  function stats(items){return `<dl class="gm-stats">${items.map(([label,value,detail])=>`<div><dt>${label}</dt><dd>${value}</dd><small>${detail}</small></div>`).join("")}</dl>`;}
  function download(name,headers,rows){const blob=new Blob([csvText(headers,rows)],{type:"text/csv;charset=utf-8"});const url=URL.createObjectURL(blob);const a=document.createElement("a");a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
  function missing(name){return header("데이터 확인 필요",`${name} 자료를 불러오지 못했습니다. 새로고침 후 출처·범위에서 수집 상태를 확인해 주세요.`);}
  function render(){
    if(!alive)return;renderEvents.abort();renderEvents=new AbortController();destroy();root.classList.add("gm-root");
    if(view==="overview")renderMarket();else if(view==="steam")renderSteam();else if(view==="mobile")renderMobile();else if(view==="apple")renderApple();else renderSources();
  }
  function renderMarket(){
    const market=data.market;if(!market){root.innerHTML=missing("시장 규모");return;}
    const latest=market.latest,history=market.history;
    root.innerHTML=header("게임 시장은 얼마나 커지고 있을까?","시장 전체의 지출 규모와, 사람들이 선택하는 장르의 변화를 나눠 봅니다. 공개 자료만 사용하며 플랫폼·표본마다 관측 범위가 다릅니다.")+
      stats([[`${latest.year} 세계 시장 추정`,`${num(latest.total,1)} 십억 달러`,`${link(latest.url,"Newzoo")} · ${latest.published} 발표`],["전년 대비",`${delta(latest.yoy)}%`,"해당 보고서가 발표한 성장률"],["모바일 비중",`${num(latest.platforms[0].value/latest.total*100,1)}%`,"모바일·PC·콘솔 콘텐츠 시장"]])+
      `<div class="gm-grid">${panel(`${latest.year} 플랫폼별 시장 규모`,note("단위: 십억 달러 · 시장 추정치")+`<div class="gm-chart"><canvas id="gm-platform" role="img" aria-label="플랫폼별 시장 매출 추정치"></canvas></div>`+table(["플랫폼","시장 규모","발표 YoY"],latest.platforms.map(p=>[esc(p.name),num(p.value,1),`${delta(p.yoy)}%`])))}${panel("데이터로 읽는 세 가지 변화",`<ul class="gm-reading"><li><b>수요의 유입</b><p>모바일 다운로드에서 최근 30일 추정치와 누적 보급 규모를 비교합니다.</p><a href="#/games/mobile">모바일 다운로드 보기</a></li><li><b>계속 즐기는 장르</b><p>Steam 월평균 동시접속자와 장르별 표본 비중의 과거·현재를 비교합니다.</p><a href="#/games/steam">Steam 장르 변화 보기</a></li><li><b>국가별 선택</b><p>한국·미국·일본·중국 App Store 게임 차트를 관측합니다.</p><a href="#/games/apple">국가별 차트 보기</a></li></ul>`)}</div>`+
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
    if(!data.mobile||!data["download-estimates"]){root.innerHTML=missing("모바일 다운로드");return;}
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
  function renderSources(){
    root.innerHTML=header("출처와 관측 범위","공개 데이터의 실제 값·추정치·순위를 구분합니다. 유료 API, 체험판, 개발자 계정 실적은 사용하지 않습니다.")+
      panel("현재 연결한 자료",table(["자료","범위·단위","갱신","한계"],[
        [link("https://newzoo.com/articles/global-games-market-2025","Newzoo 공개 발표"),"세계 시장 · 연간 십억 달러","공개 발표 확인 시 수기 반영","시장 규모 추정치. 과거 공시 인용판과 분리"],
        [link("https://steamcharts.com/","SteamCharts"),`${data.steam?.games.length||0}개 고정 표본 · 월평균/월 최고 동접`,esc(data.steam?.fetched||"미수집"),"전체 Steam 시장이 아닌 선택 표본. 평균 동접 ≠ MAU"],
        [link("https://play.google.com/store/games","Google Play 공개 목록"),`${data.mobile?.games.length||0}개 표본 · 누적 다운로드 하한·평점`,esc(data.mobile?.fetched||"미수집"),"장르별 공개 목록에서 발견한 표본. 누적 하한 차이 ≠ 월 다운로드"],
        [link("https://www.appbrain.com/","AppBrain 공개 프로필"),`${data["download-estimates"]?.observations.length||0}개 표본 · 최근 30일·누적 추정`,`${esc(data["download-estimates"]?.observed_at||"미확인")} 공개 화면 확인 · 수기`,"반올림 추정. 기준일이 다름. 자동 조회 제한으로 수기 확인 유지"],
        [link("https://rss.marketingtools.apple.com/","Apple 공식 게임 RSS"),"4개국 무료·유료 게임 Top 100",esc(data.apple?.fetched||"미수집"),"다운로드·매출액 없음. 순위와 장르 구성만 관측"],
        ["원스토어·모바일 월간 매출","연속 무료 자료 미확보","—","0으로 처리하거나 다른 스토어로 추정해 채우지 않음"]]))+
      panel("비교하는 방법",`<ul class="gm-reading"><li><b>장르 합계에는 대표 장르 하나만</b><p>Steam은 게임 플레이 기준 수동 분류, 모바일 추정 표본은 대표 장르와 세부 장르, 나머지 목록은 스토어 분류를 사용합니다. 플랫폼 간 분류가 완전히 같지는 않습니다.</p></li><li><b>다운로드와 이용량을 함께 읽기</b><p>다운로드는 유입, 누적은 보급, 동시접속자는 동시 이용을 보여줍니다. 플랫폼을 넘겨 합산하거나 이용자 수로 환산하지 않습니다.</p></li><li><b>표본과 결측 확인</b><p>선정한 게임과 현재 스토어에 남아 있는 게임 중심의 표본 편향이 있습니다. 출시 전과 누락된 달은 관측값 없음으로 남기며 보간하지 않습니다.</p></li><li><b>매출과 잠재 시장 구분</b><p>무료 스토어 자료만으로 광고·외부 결제·타 PC 스토어를 포함한 전 세계 실매출을 복원할 수 없습니다. 전체 시장은 별도의 공개 시장 규모 자료로 봅니다.</p></li></ul>`)+
      panel("최근 자동 수집의 누락",table(["소스","실패 항목 수","처리"],[["SteamCharts",data.steam?.errors.length??"—","기존 성공값과 실제 수집일 유지"],["Google Play",data.mobile?.errors.length??"—","기존 값 유지 또는 미확보 표시"],["Apple RSS",data.apple?.errors.length??"—","국가·차트별 기존 성공값 유지"]]));
  }
  return ()=>{alive=false;abort.abort();renderEvents.abort();destroy();root.classList.remove("gm-root");};
}
