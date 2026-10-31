"""Native SEC RPO snapshots and Microsoft's disclosed segment profit proxies."""
import calendar,copy,datetime as dt,math
from xml.etree import ElementTree as ET
from cpu_business_history import local,REVENUE_TAGS
from fetch_cpu_companies import reference

VERSION=1
RPO_SCOPES={
 'amzn':'장기계약 RPO · AWS 중심 · 원래 계약기간 1년 초과',
 'msft':'Commercial RPO · Azure 외 Microsoft 365·지원·라이선스 등 포함',
 'googl':'Google Cloud RPO · GCP·Workspace 등 포함',
 'orcl':'Oracle 전사 RPO · 클라우드·소프트웨어 지원 등 포함',
}
SEGMENTS={'ic':'Intelligent Cloud','ai':'Agents and Infra'}


def field_for(key,tag,members,instant):
    names={local(m).lower() for m in members}-{'operatingsegmentsmember','reportablesegmentmember'}
    if instant and tag=='RevenueRemainingPerformanceObligation':
        if key=='msft':return 'rpo' if names=={'commercialcustomersmember'} else 'rpo_total' if not names else None
        if key=='googl':return 'rpo' if names in ({'googlecloudmember'},{'googlecloudsegmentmember'}) else 'rpo_total' if not names else None
        if key in ('amzn','orcl') and not names:return 'rpo'
    if key=='msft' and not instant:
        segment='ic' if names=={'intelligentcloudmember'} else 'ai' if names=={'agentsandinframember'} else None
        if segment and (tag in REVENUE_TAGS or tag=='OperatingIncomeLoss'):
            return segment+('_profit' if tag=='OperatingIncomeLoss' else '_revenue')
    return None


def parse_instance(raw,key,spec,filing,asof):
    if filing['filingDate']>asof:return {}
    root=ET.fromstring(raw);contexts={}
    for c in root.findall('{*}context'):
        identifier=c.find('./{*}entity/{*}identifier')
        if identifier is None or int(identifier.text)!=spec['cik']:raise ValueError('Contract issuer mismatch')
        period={local(x.tag):x.text for x in c.findall('./{*}period/*')}
        contexts[c.get('id')]=(period,[m.text for m in c.findall('.//{*}explicitMember')])
    units={u.get('id'):[local(m.text) for m in u.findall('.//{*}measure')] for u in root.findall('{*}unit')}
    selected={}
    for fact in root:
        p,members=contexts.get(fact.get('contextRef'),({},[]));instant='instant' in p;end=p.get('instant',p.get('endDate'))
        field=field_for(key,local(fact.tag),members,instant)
        if not field or not end or not '2014-01-01'<=end<=asof or units.get(fact.get('unitRef'))!=['USD']:continue
        if not instant and not p.get('startDate'):continue
        try:value=float(fact.text)
        except (ValueError,TypeError):continue
        if not math.isfinite(value) or 'profit' not in field and value<0:continue
        start=end if instant else p['startDate'];identity=field,start,end
        row=dict(start=start,end=end,val=value,filed=filing['filingDate'],accn=filing['accessionNumber'],form=filing['form'],
            source_tag=local(fact.tag)+' · '+', '.join(members),source_url=filing['url'],instant=instant)
        if identity in selected and selected[identity]['val']!=value:raise ValueError('Conflicting contract or segment facts')
        selected[identity]=row
    fields={}
    for (field,_,_),row in selected.items():fields.setdefault(field,[]).append(row)
    return fields


def snapshots(facts,spec,asof):
    selected={}
    for f in facts:
        if not f['instant'] or f['filed']>asof or f['end']>asof:continue
        end=f['end']
        if end not in selected or (f['filed'],f['accn'])>(selected[end]['filed'],selected[end]['accn']):selected[end]=f
    result=[]
    for end,f in sorted(selected.items()):
        month=int(end[5:7]);fy=int(end[:4])+(spec['fiscal_start']!=1 and month>=spec['fiscal_start'])
        quarter=((month-spec['fiscal_start'])%12)//3+1
        ref=reference(dict(f,tag=f['source_tag']),spec['cik'])
        result.append(dict(date=end,start=end,year=fy,quarter=quarter,rpo=f['val']/1e6,
            refs={'rpo':dict(ref,instant=True,calculation='reported point-in-time remaining performance obligations; not a quarterly flow',components=[ref])}))
    return result


def fiscal_snapshots(rows,spec):
    month=spec['fiscal_start']-1 or 12
    return [copy.deepcopy(r) for r in rows if r['date'][5:]==f'{month:02d}-{calendar.monthrange(int(r["date"][:4]),month)[1]}']


def segment_income(fields,segment,spec,asof):
    # Pair revenue/profit from one filing vintage. A later recast annual must
    # not be subtracted from an older, unrecast nine-month cumulative period.
    bundles={}
    for metric in ('revenue','profit'):
        for f in fields.get(segment+'_'+metric,[]):
            if f['filed']>asof or f['end']>asof:continue
            bundles.setdefault((f['start'],f['end'],f['accn']),{})[metric]=f
    pairs=[b for b in bundles.values() if set(b)=={'revenue','profit'}]
    rank=lambda b:(b['revenue']['filed'],b['revenue']['accn'])
    duration=lambda b:(dt.date.fromisoformat(b['revenue']['end'])-dt.date.fromisoformat(b['revenue']['start'])).days+1
    def ref(f):return reference(dict(f,tag=f['source_tag']),spec['cik'])
    def row(b,prior=None):
        end=b['revenue']['end'];start=(dt.date.fromisoformat(prior['revenue']['end'])+dt.timedelta(days=1)).isoformat() if prior else b['revenue']['start']
        month=int(end[5:7]);r=dict(start=start,date=end,year=int(end[:4])+(spec['fiscal_start']!=1 and month>=spec['fiscal_start']),quarter=((month-spec['fiscal_start'])%12)//3+1,refs={})
        for m in ('revenue','profit'):
            f=b[m];parts=[ref(f)]+([ref(prior[m])] if prior else [])
            r[m]=(f['val']-(prior[m]['val'] if prior else 0))/1e6
            r['refs'][m]=dict(parts[0],start=start,end=end,components=parts,calculation='first reported annual vintage minus available same-fiscal-year 9-month YTD' if prior else 'reported same-filing period')
        if r['revenue']<=0:raise ValueError('Non-positive segment revenue; check reporting basis')
        r['margin']=r['profit']/r['revenue']*100
        r['refs']['margin']=dict(r['refs']['profit'],components=[r['refs']['profit'],r['refs']['revenue']],calculation=SEGMENTS[segment]+' operating profit / same segment revenue × 100 · cloud profitability proxy')
        return r
    direct={};years={}
    for b in pairs:
        end=b['revenue']['end']
        if 75<=duration(b)<=105 and (end not in direct or rank(b)>rank(direct[end])):direct[end]=b
        if 350<=duration(b)<=380:years.setdefault(end,[]).append(b)
    rows={end:row(b) for end,b in direct.items()};annual=[]
    for end,versions in sorted(years.items()):
        annual.append(row(max(versions,key=rank)))
        if end in rows:continue
        original=min(versions,key=rank);f=original['revenue']
        priors=[b for b in pairs if b['revenue']['start']==f['start'] and b['revenue']['end']<end and 260<=duration(b)<=290 and rank(b)[0]<=f['filed']]
        if not priors:continue
        prior=max(priors,key=rank)
        if 75<=(dt.date.fromisoformat(end)-dt.date.fromisoformat(prior['revenue']['end'])).days<=105:rows[end]=row(original,prior)
    return dict(rows=[r for _,r in sorted(rows.items())],annual=annual)


def collect(key,spec,old,client,asof,full=False,offline=False):
    fields=copy.deepcopy(old.get('facts',{}));known=set(old.get('filings',[]));errors=[]
    if not offline:
        try:
            filings=[f for f in client.filings(spec['cik'],asof) if f['form'] in ('10-Q','10-K') and f['reportDate']>='2014-01-01']
            pending=[f for f in filings if full or old.get('version')!=VERSION or f['accessionNumber'] not in known]
            print(key,len(pending),'RPO/segment filings to read',flush=True)
            for f in pending:
                try:
                    fresh=parse_instance(client.instance(f),key,spec,f,asof)
                    if key=='msft' and f['reportDate']>='2026-09-30' and not all(fresh.get(s) for s in ('ai_revenue','ai_profit')):
                        raise ValueError('New Microsoft segment mapping needs review')
                    # Google did not disclose a separate Cloud RPO in every old
                    # filing. Its consolidated series is retained separately.
                    if f['reportDate']>='2024-01-01' and not fresh.get('rpo') and not (key=='googl' and fresh.get('rpo_total')):
                        raise ValueError('New filing has no mapped RPO')
                    for field,values in fresh.items():fields.setdefault(field,[]).extend(values)
                    known.add(f['accessionNumber'])
                except Exception as e:errors.append(f['filingDate']+' RPO·부문 공시 검토 필요 · '+type(e).__name__)
        except Exception as e:errors.append('RPO·부문 공시 목록 조회 실패 · '+type(e).__name__)
    for field,values in fields.items():fields[field]=list({(v['start'],v['end'],v['accn'],v['source_tag']):v for v in values}.values())
    rpo=snapshots(fields.get('rpo',[]),spec,asof);total=snapshots(fields.get('rpo_total',[]),spec,asof)
    if not rpo and not total and not old:raise ValueError(key+' has no verified RPO history')
    result=dict(version=VERSION,facts=fields,filings=sorted(known),rpo=dict(rows=rpo,annual=fiscal_snapshots(rpo,spec)),
        rpo_total=dict(rows=total,annual=fiscal_snapshots(total,spec)),
        segments={s:segment_income(fields,s,spec,asof) for s in SEGMENTS} if key=='msft' else {},
        checked=old.get('checked',asof) if offline else asof,fetched=old.get('fetched',asof) if offline or errors else asof,
        ok=old.get('ok',True) if offline else not errors,errors=old.get('errors',[]) if offline else errors)
    for field in ('rpo','rpo_total'):
        prior=old.get(field,{}).get('rows',[]);now=result[field]['rows']
        if prior and (len(now)<len(prior) or now[-1]['date']<prior[-1]['date']):raise ValueError(key+' RPO history regressed')
    return result
