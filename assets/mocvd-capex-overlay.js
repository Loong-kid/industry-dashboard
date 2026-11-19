/* CAPEX guidance stays separate from cash actuals and their headline statistics. */
const MOCVDCapexOverlay = (() => {
  const issuers={mocvd_coherent_capex:'coherent',mocvd_lumentum_capex:'lumentum'};
  const numeric=r=>['range','point'].includes(r.guidance_kind);
  const fiscal=date=>{const y=Number(date.slice(0,4)),m=Number(date.slice(5,7));return {fy:y+(m>6?1:0),q:Math.floor(((m+5)%12)/3)+1};};
  const fyLabel=(date,annual)=>{const {fy,q}=fiscal(date);return `FY${fy}${annual?'':` Q${q}`}`;};
  const descending=(a,b)=>b.announced_at.localeCompare(a.announced_at)||b.id.localeCompare(a.id);
  const short=r=>r.review_status==='pending'?'검토 대기':r.review_status==='release_only'?'콜 미확인':r.guidance_kind==='directional'?'CAPEX 증가':r.guidance_kind==='relative_order'?'발주 계획':r.guidance_kind==='capacity_only'?'증설 계획':numeric(r)?'금액 가이던스':r.guidance_kind==='not_found'?'금액·방향 미확인':'투자 계획';
  const attach=(doc,guidance)=>!issuers[doc?.id]?doc:{...doc,mocvd_guidance:{rows:(guidance?.rows||[]).filter(r=>r.company===issuers[doc.id]),unavailable:!guidance,status:guidance?.companies_status?.[issuers[doc.id]]}};

  function plan(doc,filtered,range={}) {
    if(!doc.mocvd_guidance)return null;
    const annual=doc.frequency==='yearly',from=range.from||'0000-00-00',to=range.to||'9999-12-31';
    const actualDates=[...new Set(Object.values(filtered).flatMap(points=>points.filter(p=>p[1]!=null).map(p=>p[0])))].sort();
    const known=new Map(Object.entries(doc.period_labels||{}).map(([date,label])=>[label,date]));
    const axisDate=date=>{
      const label=fyLabel(date,annual),f=fiscal(date);
      if(known.has(label))return known.get(label);
      if(annual)return `${f.fy}-06-30`; // FY-axis placeholder, never a cash observation.
      const y=Number(date.slice(0,4)),m=Math.ceil(Number(date.slice(5,7))/3)*3;
      return new Date(Date.UTC(y,m,0)).toISOString().slice(0,10);
    };
    const events=[];
    for(const row of doc.mocvd_guidance.rows){
      if(row.announced_at>to)continue;
      const target=row.target_end||row.announced_at;
      const duration=(Date.parse(row.target_end)-Date.parse(row.target_start))/86400000+1;
      let anchors=[target];
      if(!annual&&row.review_status==='call_reviewed'&&row.guidance_kind==='directional'&&duration>100&&duration<=380){
        // "Increase each remaining quarter" belongs on every target quarter,
        // without inventing a dollar path or duplicating the call history.
        const start=new Date(Date.parse(row.target_start)+14*86400000),end=new Date(row.target_end);
        const first=start.getUTCFullYear()*4+Math.floor(start.getUTCMonth()/3),last=end.getUTCFullYear()*4+Math.floor(end.getUTCMonth()/3);
        anchors=Array.from({length:last-first+1},(_,i)=>new Date(Date.UTC(Math.floor((first+i)/4),((first+i)%4+1)*3,0)).toISOString().slice(0,10));
      }
      const dates=[...new Set(anchors.filter(d=>d>=from&&d<=to).map(axisDate))].filter(d=>d>=from&&d<=to);
      if(!dates.length)continue;
      const date=dates.at(-1);
      const cash=numeric(row)&&row.review_status==='call_reviewed'&&row.basis==='전사 현금 CAPEX'&&row.currency==='USD'&&row.amount_unit==='million';
      const validAmount=cash&&Number.isFinite(row.amount_low)&&Number.isFinite(row.amount_high)&&row.amount_low>=0&&row.amount_high>=row.amount_low;
      const sm=Number(row.target_start?.slice(5,7)),sd=Number(row.target_start?.slice(8,10)),em=Number(row.target_end?.slice(5,7)),ed=Number(row.target_end?.slice(8,10));
      const aligned=annual?em===6&&ed>=24&&((sm===7&&sd<=7)||(sm===6&&sd>=24))
        :em%3===0&&ed>=24&&((sm%3===1&&sd<=7)||(sm%3===0&&sd>=24));
      const quant=validAmount&&aligned&&(annual?duration>=350&&duration<=380:duration>=70&&duration<=100);
      events.push({row,date,dates,label:fyLabel(target,annual),targeted:!!row.target_end,quant,short:short(row)});
    }
    events.sort((a,b)=>descending(a.row,b.row));
    const groups=new Map();for(const event of events)for(const date of event.dates){if(!groups.has(date))groups.set(date,[]);groups.get(date).push(event);}
    const ranges=[...groups.values()].flatMap(group=>{const latest=group.find(e=>e.quant);return latest?[latest]:[];});
    return {events,groups,ranges,dates:[...groups.keys()],labels:Object.fromEntries([...groups.keys()].map(date=>[date,fyLabel(date,annual)])),annual,lastActual:actualDates.at(-1),unavailable:doc.mocvd_guidance.unavailable,status:doc.mocvd_guidance.status};
  }

  function datasets(model,labels,palette){
    if(!model?.ranges.length)return [];
    return ['하단','상단'].map((bound,i)=>({label:`컨콜 가이던스 ${bound}`,isCapexGuidance:true,
      data:labels.map(date=>{const event=model.ranges.find(e=>e.date===date);return event?event.row[i?'amount_high':'amount_low']:null;}),
      borderColor:palette[1],backgroundColor:palette[1],borderWidth:2,borderDash:[5,4],
      showLine:false,pointStyle:'rectRot',pointRadius:4,pointHoverRadius:6,spanGaps:false,hidden:false}));
  }

  function plugin(model,css){
    let hits=[];
    return {id:'mocvdCapexGuidance',
      beforeDraw(chart){
        if(!model?.lastActual||!model.dates.some(d=>d>model.lastActual))return;
        const i=chart.data.labels.indexOf(model.lastActual);if(i<0)return;
        const {ctx,chartArea:a,scales:{x}}=chart;
        const start=(x.getPixelForValue(i)+x.getPixelForValue(i+1))/2;
        ctx.save();ctx.fillStyle=css('--neutral-tint');ctx.fillRect(start,a.top,a.right-start,a.bottom-a.top);ctx.restore();
      },
      afterDraw(chart){
        hits=[];if(!model?.events.length)return;
        const {ctx,chartArea:a,scales:{x,y}}=chart;
        const textY=a.top-15;ctx.save();ctx.font=`11px ${getComputedStyle(chart.canvas).fontFamily}`;ctx.textBaseline='middle';
        const latest=model.events[0];let previousRight=-Infinity;
        for(const date of [...model.groups.keys()].sort()){
          const group=model.groups.get(date),e=group[0],i=chart.data.labels.indexOf(date);if(i<0)continue;
          const px=x.getPixelForValue(i);const up=e.row.review_status==='call_reviewed'&&e.row.capex_direction==='increase_qoq';
          ctx.fillStyle=up?css('--up'):css('--muted');ctx.beginPath();
          if(up){ctx.moveTo(px,textY-5);ctx.lineTo(px+4,textY+3);ctx.lineTo(px-4,textY+3);ctx.closePath();}else ctx.arc(px,textY,3,0,Math.PI*2);
          ctx.fill();
          const text=e.short+(group.length>1?` · ${group.length}`:'');const w=ctx.measureText(text).width;
          const tx=Math.max(a.left,Math.min(px+8,a.right-w));
          if((tx>previousRight+10&&tx+w< x.getPixelForValue(Math.min(i+1,chart.data.labels.length-1))-8)||e===latest){
            ctx.fillStyle=css('--ink-2');ctx.fillText(text,tx,textY);previousRight=tx+w;
          }
          hits.push({x:px,y:textY,event:e});
        }
        const guideIndex=chart.data.datasets.findIndex(d=>d.isCapexGuidance);
        if(guideIndex>=0&&chart.isDatasetVisible(guideIndex)&&chart.isDatasetVisible(guideIndex+1)){
          ctx.strokeStyle=chart.data.datasets[guideIndex].borderColor;ctx.lineWidth=2;ctx.setLineDash([4,3]);
          for(const e of model.ranges){const px=x.getPixelForValue(chart.data.labels.indexOf(e.date)),low=y.getPixelForValue(e.row.amount_low),high=y.getPixelForValue(e.row.amount_high);ctx.beginPath();ctx.moveTo(px,low);ctx.lineTo(px,high);ctx.stroke();}
        }
        ctx.restore();
      },
      afterEvent(chart,args){
        const event=args.event,hit=hits.filter(p=>Math.abs(p.x-event.x)<12&&Math.abs(p.y-event.y)<13).sort((a,b)=>Math.abs(a.x-event.x)-Math.abs(b.x-event.x))[0];
        if(event.type==='click'&&hit)chart.$mocvdOpen?.(hit.event.row.id);
      }
    };
  }

  function controls(card,chart,doc,model){
    if(!model)return;
    const make=(tag,cls,text)=>{const el=document.createElement(tag);if(cls)el.className=cls;if(text!=null)el.textContent=text;return el;};
    const root=make('section','mcg-overlay');root.setAttribute('aria-label','CAPEX 그래프 컨콜 가이던스');
    const line=make('div','mcg-line');line.append(make('span','mcg-key','컨콜 가이던스'));
    const newest=model.events[0];
    line.append(make('span','mcg-latest',newest?`${newest.row.target_period} · ${newest.row.headline}`:model.unavailable?'가이던스 자료 불러오기 실패 · 실제 집행액은 유지':'선택 기간에 확인된 가이던스 없음'));
    const details=make('details','mcg-evidence'),summary=make('summary','','발표 이력·근거');details.append(summary);
    if(newest){
      const select=make('select');select.setAttribute('aria-label','CAPEX 그래프 가이던스 발표 선택');
      for(const e of model.events){const o=make('option','',`${e.row.announced_at} · FY${e.row.reported_fy} Q${e.row.reported_quarter} · ${e.short}`);o.value=e.row.id;select.append(o);}
      const body=make('div','mcg-detail');details.append(select,body);
      const show=id=>{
        const e=model.events.find(e=>e.row.id===id)||newest,r=e.row;body.replaceChildren();
        body.append(make('p','',`${r.headline} · 대상 ${r.target_period}`),make('p','',r.summary));
        body.append(make('p','mcg-note',`${r.announced_at}${r.date_basis==='filed'?' 공시 접수':' 발표'} · ${r.basis} · ${e.targeted?'대상 기간에 표시':'기간 미제시: 발표 분기에 표시'}`));
        if(numeric(r)&&!e.quant)body.append(make('p','mcg-note','이 그래프의 현금 CAPEX 범위·표시 주기와 달라 금액 좌표로 환산하지 않았습니다.'));
        if(r.quote)body.append(make('blockquote','',r.quote));
        const sources=make('div','mcg-sources');
        for(const [label,url] of [[r.source_label,r.source_url],['공식 공시·IR',r.official_url]])if(url?.startsWith('https://')){const a=make('a','',label);a.href=url;a.target='_blank';a.rel='noopener noreferrer';sources.append(a);}
        body.append(sources);
      };
      select.addEventListener('change',()=>show(select.value));show(newest.row.id);
      chart.$mocvdOpen=id=>{select.value=id;show(id);details.open=true;};
    }
    root.append(line,make('p','mcg-note','그래프 위 표시는 컨콜 발언입니다. ▲ 증가는 금액 좌표가 아니며, 금액 가이던스는 같은 기간·현금 기준일 때만 별도 점선 범위로 표시합니다.'),details);
    if(model.status?.ok===false)root.append(make('p','mcg-warning','새 공시 조회 실패 · 기존 검토 이력 유지'));
    const wrap=card.querySelector('.chart-wrap');wrap.after(root);
  }
  return {issuers,attach,plan,datasets,plugin,controls};
})();
if(typeof module!=='undefined')module.exports=MOCVDCapexOverlay;
