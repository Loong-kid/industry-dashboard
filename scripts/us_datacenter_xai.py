"""SpaceX consolidated and AI/SI segment accounts from public SEC filings."""
import copy,datetime as dt
from fetch_cpu_companies import reference
from us_datacenter_sources import parse_instance,parse_spacex_bootstrap

BOOTSTRAP=dict(form='S-1/A',filingDate='2026-06-01',accessionNumber='0001628280-26-039276',
    url='https://www.sec.gov/Archives/edgar/data/1181412/000162828026039276/spaceexplorationtechnologi.htm')


def periods(fields,cik,asof):
    """Direct fiscal quarters or exact YTD differences, never annual / four."""
    groups={};annual={}
    for field,facts in fields.items():
        selected={}
        for f in facts:
            if f['filed']>asof or f['end']>asof:continue
            key=f['start'],f['end']
            if key not in selected or (f['filed'],f['accn'])>(selected[key]['filed'],selected[key]['accn']):selected[key]=f
        def ref(f):return reference(dict(f,tag=f['source_tag']),cik)
        def put(target,f,value,start,parts):
            r=target.setdefault(f['end'],dict(start=start,date=f['end'],year=int(f['end'][:4]),refs={}))
            if target is groups:r['quarter']=(int(f['end'][5:7])+2)//3
            r[field]=value/1e6
            r['refs'][field]=dict(ref(f),start=start,components=[ref(p) for p in parts],
                calculation='reported period' if len(parts)==1 else 'same fiscal-year YTD minus prior YTD')
        for (start,end),f in sorted(selected.items()):
            days=(dt.date.fromisoformat(end)-dt.date.fromisoformat(start)).days+1
            if start.endswith('01-01') and end.endswith('12-31') and 350<=days<=380:put(annual,f,f['val'],start,[f])
            if end[5:] not in ('03-31','06-30','09-30','12-31'):continue
            if 75<=days<=105:
                put(groups,f,f['val'],start,[f]);continue
            if not start.endswith('01-01'):continue
            q=(int(end[5:7])+2)//3
            prior_end=f'{end[:4]}-'+{2:'03-31',3:'06-30',4:'09-30'}.get(q,'')
            prior=selected.get((start,prior_end))
            # Prefer a reported standalone quarter over a derived observation.
            direct=next((g for (s,e),g in selected.items() if e==end and 75<=(dt.date.fromisoformat(e)-dt.date.fromisoformat(s)).days+1<=105),None)
            if prior and not direct:
                value=f['val']-prior['val']
                if 'profit' not in field and value<0:raise ValueError('Negative SpaceX revenue or investment difference')
                put(groups,f,value,(dt.date.fromisoformat(prior_end)+dt.timedelta(days=1)).isoformat(),[f,prior])
    return [r for _,r in sorted(groups.items())],[r for _,r in sorted(annual.items())]


def collect_xai(spec,old,client,asof,full=False,offline=False):
    fields=copy.deepcopy(old.get('fields',{}));known=set(old.get('filings',[]));errors=[]
    if not offline:
        try:
            if full or BOOTSTRAP['accessionNumber'] not in known:
                fresh=parse_spacex_bootstrap(client.get(BOOTSTRAP['url']),BOOTSTRAP,asof)
                for field,values in fresh.items():fields.setdefault(field,[]).extend(values)
                known.add(BOOTSTRAP['accessionNumber'])
            for f in client.filings(spec['cik'],asof):
                if f['form'] not in ('10-Q','10-K') or not full and f['accessionNumber'] in known:continue
                fresh=parse_instance(client.instance(f),'xai',spec,f,asof)
                if not all(fresh.get(field) for field in ('revenue','profit','capex','segment_revenue','segment_profit','segment_capex')):
                    raise ValueError('New SpaceX filing lacks consolidated or AI/SI fields')
                for field,values in fresh.items():fields.setdefault(field,[]).extend(values)
                known.add(f['accessionNumber'])
        except Exception as e:errors.append('SpaceX·AI/SI 공시 검토 필요 · '+type(e).__name__)
    for field,values in fields.items():
        fields[field]=list({(v['start'],v['end'],v['accn'],v['source_tag']):v for v in values}.values())
    rows,annual=periods(fields,spec['cik'],asof)
    if not rows or not annual:
        if not old.get('rows'):raise ValueError('No verified SpaceX / xAI history')
        result=copy.deepcopy(old);result.update(core_ok=False,cloud_ok=False,errors=errors);return result
    if old.get('rows') and (len(rows)<len(old['rows']) or rows[-1]['date']<old['rows'][-1]['date']):
        raise ValueError('SpaceX history regressed')
    for r in rows+annual:
        if r.get('segment_revenue') is not None and r.get('revenue',0)>0:
            r['segment_share']=r['segment_revenue']/r['revenue']*100
            if not 0<=r['segment_share']<=100:raise ValueError('AI/SI exceeds SpaceX revenue')
            r['refs']['segment_share']=dict(r['refs']['segment_revenue'],components=[r['refs']['segment_revenue'],r['refs']['revenue']],calculation='AI/SI revenue / SpaceX consolidated revenue × 100')
    return dict(rows=rows,annual=annual,core_rows=rows,core_annual=annual,fields=fields,filings=sorted(known),
        core_ok=old.get('core_ok',True) if offline else not errors,cloud_ok=old.get('cloud_ok',True) if offline else not errors,
        errors=old.get('errors',[]) if offline else errors,checked=old.get('checked',asof) if offline else asof,
        fetched=old.get('fetched',asof) if offline or errors else asof)
