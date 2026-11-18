const el=(tag,cls,text)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(text!=null)e.textContent=text;return e;};
const fmt=n=>new Intl.NumberFormat('ko-KR',{maximumFractionDigits:2}).format(n);
const period=r=>`FY${r.reported_fy} Q${r.reported_quarter}`;
const numeric=r=>['range','point'].includes(r.guidance_kind);
const amount=r=>numeric(r)?`${fmt(r.amount_low)}${r.amount_high!==r.amount_low?'~'+fmt(r.amount_high):''} 백만 USD`:r.review_status==='pending'?'검토 대기':r.review_status==='release_only'?'금액 미확인':'금액 미제시 · 확인 발언';
const revisions={raised:'상향',lowered:'하향',maintained:'유지',range_changed:'범위 변경',not_comparable:'상향·유지 판정 안 함'};

export function renderMOCVDGuidance(doc){
  const root=el('section','mg-root');root.setAttribute('aria-label','광학 고객사 미래 CAPEX 가이던스');
  root.append(el('p','mg-intro','실제 지출보다 먼저 나온 투자 계획을 발표 당시 기준으로 봅니다. 다음 분기 증가와 연간 예산 상향은 다르며, 생산능력 목표·발주액·현금지출을 구분합니다.'));
  const overview=el('div','mg-overview');
  const desc=[...doc.rows].sort((a,b)=>b.announced_at.localeCompare(a.announced_at)||b.reported_fy-a.reported_fy||b.reported_quarter-a.reported_quarter);
  for(const [key,c] of Object.entries(doc.companies)){
    const rows=desc.filter(r=>r.company===key),latest=rows[0],reviewed=rows.find(r=>r.review_status==='call_reviewed'),card=el('article','mg-summary');
    card.append(el('h3','',c.name),el('p','mg-meta',`${period(latest)} · ${latest.announced_at}${latest.date_basis==='filed'?' 공시 접수':''}`));
    card.append(el('p','mg-headline',latest.headline),el('p','mg-amount',amount(latest)));
    card.append(el('p','mg-meta',`대상: ${latest.target_period} / ${latest.basis}`));
    if(reviewed&&reviewed.id!==latest.id)card.append(el('p','mg-previous',`최근 확인한 콜 ${period(reviewed)} · ${reviewed.headline}`));
    const status=doc.companies_status?.[key];if(status?.ok===false)card.append(el('p','mg-warning','새 공시 조회 실패 · 확인된 이력 유지'));
    overview.append(card);
  }
  root.append(overview);
  const controls=el('div','mg-controls');
  const select=(label,values)=>{const l=el('label','',label),s=el('select');s.setAttribute('aria-label','CAPEX 가이던스 '+label);for(const [value,text]of values){const o=el('option','',text);o.value=value;s.append(o);}l.append(s);controls.append(l);return s;};
  const company=select('기업',[['','전체'],...Object.entries(doc.companies).map(([k,c])=>[k,c.name])]);
  const fy=select('발표 회계연도',[['','전체'],...[...new Set(doc.rows.map(r=>r.reported_fy))].sort((a,b)=>b-a).map(y=>[String(y),'FY'+y])]);
  const kind=select('발언 유형',[['','전체'],['quantitative','금액 목표'],['capex','CAPEX 방향·발주'],['investment','증설·투자 계획'],['review','미확인·검토 대기']]);
  const count=el('span','mg-count');count.setAttribute('aria-live','polite');controls.append(count);root.append(controls);
  const wrap=el('div','mg-table-wrap');wrap.tabIndex=0;wrap.setAttribute('role','region');wrap.setAttribute('aria-label','발표 분기별 미래 CAPEX 가이던스 이력');
  const table=el('table','mg-table'),thead=el('thead'),head=el('tr');for(const title of ['발표 분기·일자','기업','계획 대상·기준','미래 CAPEX 가이던스','근거']){const th=el('th','',title);th.scope='col';head.append(th);}thead.append(head);table.append(thead);const body=el('tbody');table.append(body);wrap.append(table);root.append(wrap);
  const dialog=el('dialog','mg-dialog');const close=el('button','mg-close','닫기');close.type='button';close.setAttribute('aria-label','가이던스 근거 닫기');close.addEventListener('click',()=>dialog.close?dialog.close():dialog.removeAttribute('open'));const detail=el('div');dialog.append(close,detail);dialog.addEventListener('click',e=>{if(e.target===dialog)close.click();});root.append(dialog);
  const open=row=>{
    detail.replaceChildren();const title=el('h3','',`${doc.companies[row.company].name} · ${period(row)}`);title.id='mg-dialog-title';dialog.setAttribute('aria-labelledby',title.id);detail.append(title,el('p','mg-meta',`${row.announced_at} · ${row.date_basis==='filed'?'공시 접수일':'발표일'}`));
    const list=el('dl');for(const [label,value]of [['가이던스',row.headline],['미래 금액',amount(row)],['계획 대상 기간',row.target_period],['공시 기준',row.basis],['동일 대상 예산 비교',revisions[row.revision]],['확인 내용',row.summary],['발언·자료',row.speaker],['원문 구절',row.quote||'숫자·설명은 확인 내용에서 요약했습니다.'],['검토 상태',row.review_status==='call_reviewed'?'공개 컨콜 전문 검토':row.review_status==='release_only'?'공식 발표자료 확인 · 컨콜 미확인':'새 공시 검토 대기']]){list.append(el('dt','',label),el('dd','',value));}detail.append(list);
    const sources=el('p','mg-sources');for(const [label,url]of [[row.source_label,row.source_url],['공식 공시·IR',row.official_url]]){if(!url?.startsWith('https://'))continue;const a=el('a','',label);a.href=url;a.target='_blank';a.rel='noopener noreferrer';sources.append(a);}detail.append(sources);
    if(dialog.showModal)dialog.showModal();else dialog.setAttribute('open','');
  };
  function render(){
    const rows=desc.filter(r=>(!company.value||r.company===company.value)&&(!fy.value||String(r.reported_fy)===fy.value)&&(!kind.value||(kind.value==='quantitative'?numeric(r):kind.value==='capex'?['directional','relative_order'].includes(r.guidance_kind):kind.value==='investment'?['capacity_only','investment_plan','investment_priority'].includes(r.guidance_kind):['not_found','release_only','pending_review'].includes(r.guidance_kind))));
    count.textContent=`${rows.length} / ${doc.rows.length}개 발표`;body.replaceChildren();
    for(const row of rows){const tr=el('tr'),date=el('th','mg-date',period(row));date.scope='row';date.append(el('small','',row.announced_at+(row.date_basis==='filed'?' 접수':'')));const target=el('td','mg-target',row.target_period);target.append(el('small','',row.basis));const forecast=el('td','mg-forecast');forecast.append(el('span','mg-kind',row.kind_label),el('span','mg-statement',row.headline),el('small','',amount(row)));const source=el('td'),button=el('button','mg-evidence','근거');button.type='button';button.setAttribute('aria-label',doc.companies[row.company].name+' '+period(row)+' 가이던스 근거');button.addEventListener('click',()=>open(row));source.append(button);tr.append(date,el('td','mg-firm',doc.companies[row.company].name),target,forecast,source);body.append(tr);}
    if(!rows.length){const tr=el('tr'),td=el('td','mg-empty','조건에 맞는 확인 기록이 없습니다. 금액 미확인은 0이 아닙니다.');td.colSpan=5;tr.append(td);body.append(tr);}
  }
  for(const s of [company,fy,kind])s.addEventListener('change',render);render();
  const method=el('details','mg-method');method.append(el('summary','','가이던스·변경 판정 기준'),el('p','',doc.methodology),el('p','','정량 상향·유지는 동일 기업·대상 기간·투자 범위·단위가 같은 금액 목표끼리만 판정합니다. 컨콜 전문은 공개 재게시 자료이며 공식 공시와 구분합니다. 새 실적 공시는 자동 감지하고, 금액·기간·컨콜 발언은 원문 검토 후 확정합니다.'));
  root.append(method,el('p','mg-meta',`발언 검토 ${doc.reviewed} · 새 공시 확인 ${doc.checked||'첫 수집 대기'} · FY는 회사 회계연도입니다. 이 표는 상단 실적 기간 필터와 별도로 전체 발표 이력을 보존합니다.`));return root;
}
