"""Public neocloud disclosures: actual GAAP accounts, AI revenue and ASC 606 RPO."""
import argparse,calendar,copy,datetime as dt,json,re
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from cpu_business_history import SecClient
from fetch_cpu_companies import load,save,parse_facts,parse_annual,TAGS
from fetch_us_datacenter import fiscal_payload,normalized,merge_business,parse_business
from us_datacenter_contracts import snapshots,fiscal_snapshots
from neocloud_sources import native_cloud,nebius_tables,nebius_letter,nebius_rpo,clean
from neocloud_presentations import documents

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'data/datacenter';CACHE=ROOT/'.cache/neocloud'


def merge_fields(fields,fresh):
    for name,values in fresh.items():
        merged={tuple(r.get(k) for k in ('start','end','accn','source_tag')):r for r in fields.get(name,[])+values}
        fields[name]=sorted(merged.values(),key=lambda r:(r['end'],r['start'],r['filed']))


def nbis_core(payload,fields,spec,asof):
    """USD continuing operations only; 6-K tables supply untagged quarters."""
    facts={}
    for metric,tags in TAGS.items():
        rows=[]
        for tag in tags:
            for f in payload['facts']['us-gaap'].get(tag,{}).get('units',{}).get('USD',[]):
                if f.get('start','')>=spec['since'] and f['filed']>='2025-01-01':rows.append(dict(f,source_tag='us-gaap:'+tag))
        rows+=fields.get(metric,[])
        facts[metric]={'units':{'USD':rows}}
    synthetic=dict(cik=spec['cik'],facts={'us-gaap':facts})
    tags={m:[m] for m in TAGS}
    return [normalized(parser(synthetic,spec,asof,tags)) for parser in (parse_facts,parse_annual)]


def rpo_history(payload,spec,asof,fields=None):
    values=payload['facts']['us-gaap'].get('RevenueRemainingPerformanceObligation',{}).get('units',{}).get('USD',[])
    facts=[dict(f,start=f['end'],instant=True,source_tag='us-gaap:RevenueRemainingPerformanceObligation') for f in values if not f.get('start') and f['end']>=spec['since']
        and int(f['end'][5:7]) in (3,6,9,12) and int(f['end'][8:10])==calendar.monthrange(int(f['end'][:4]),int(f['end'][5:7]))[1]]
    rows=snapshots(facts+(fields or {}).get('rpo',[]),spec,asof)
    if not rows:raise ValueError('No verified ASC 606 RPO')
    return dict(rows=rows,annual=fiscal_snapshots(rows,spec))


def collect(offline=False,full=False):
    asof=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date().isoformat()
    meta=load(ROOT/'manual/us-datacenter/neoclouds.json',{});state=load(OUT/'us_neocloud_state.json',dict(companies={}))
    client=SecClient(CACHE/'sec')
    for key,spec in meta.items():
        old=state['companies'].get(key,{})
        if offline:
            if not old:raise ValueError('Offline publication needs verified normalized state')
            continue
        fields=copy.deepcopy(old.get('fields',{}));known=set(old.get('filings',[]));errors=[]
        try:
            payload=json.loads(client.get(f'https://data.sec.gov/api/xbrl/companyfacts/CIK{spec["cik"]:010d}.json',refresh=True))
            if int(payload['cik'])!=spec['cik']:raise ValueError('SEC issuer mismatch')
            save(CACHE/(key+'_facts.json'),payload)
            if key!='crwv':
                filings=[f for f in client.filings(spec['cik'],asof) if f['filingDate']>=('2024-10-01' if key=='nbis' else '2024-08-01')]
                if key=='iren':filings=[f for f in filings if f['form'] in ('10-K','10-Q')]
                pending=[f for f in filings if f['accessionNumber'] not in known or full]
                print(key,len(pending),'new filings to inspect',flush=True)
                for f in pending:
                    if f['form'] in ('10-K','10-Q','20-F'):
                        fresh=native_cloud(client.instance(f),key,spec,f)
                        if not fresh:raise ValueError('New financial filing has no mapped AI cloud revenue')
                        merge_fields(fields,fresh)
                    elif key=='nbis' and f['form']=='6-K':
                        soup=BeautifulSoup(client.get(f['url']),'html.parser')
                        if re.search(r'financial|results',soup.get_text(' ',strip=True),re.I):
                            links={urljoin(f['url'],a['href']) for a in soup.select('a[href]') if re.fullmatch(r'99\.[12]',clean(a.get_text(strip=True)))}
                            if not links:
                                base=f['url'].rsplit('/',1)[0]+'/'
                                index=json.loads(client.get(base+'index.json'))
                                links={base+i['name'] for i in index['directory']['item'] if re.search(r'ex99(?:d|-|_)?[12]\.htm$',i['name'],re.I)}
                            for url in sorted(links):
                                raw=client.get(url);ref=dict(f,url=url)
                                fresh=nebius_tables(raw,ref);merge_fields(fresh,nebius_letter(raw,ref));merge_fields(fresh,nebius_rpo(raw,ref));merge_fields(fields,fresh)
                                text=BeautifulSoup(raw,'html.parser').get_text(' ',strip=True)
                                if 'financial results' in text.lower() and ('Loss from operations' in text or 'CONSOLIDATED STATEMENTS OF OPERATIONS' in text) and not fresh.get('revenue'):
                                    raise ValueError('Unmapped new Nebius earnings tables')
                    known.add(f['accessionNumber'])
            if key=='nbis':core,annual=nbis_core(payload,fields,spec,asof)
            else:
                payload=fiscal_payload(payload,spec)
                core,annual=[normalized(parser(payload,spec,asof,TAGS)) for parser in (parse_facts,parse_annual)]
            core=[r for r in core if r['start']>=spec['since'] and r.get('revenue') is not None]
            annual=[r for r in annual if r['start']>=spec['since'] and r.get('revenue') is not None]
            cloud,cloud_annual=parse_business({'cloud_revenue':fields.get('cloud_revenue',[])},spec,asof) if key!='crwv' else ([],[])
            rows=merge_business(core,cloud);years=merge_business(annual,cloud_annual)
            if key=='crwv':
                for r in rows+years:
                    for field,m in [('cloud_revenue','revenue'),('cloud_profit','profit')]:
                        if m in r:r[field]=r[m];r['refs'][field]=dict(r['refs'][m],calculation='single reportable AI cloud segment · same consolidated '+m)
                    r['cloud_share']=100.;r['refs']['cloud_share']=dict(r['refs']['revenue'],calculation='single AI cloud segment / consolidated revenue × 100')
            for group in (rows,years):
                for r in group:
                    if r.get('revenue',0)>0 and r.get('profit') is not None:
                        r['margin']=r['profit']/r['revenue']*100
                        r['refs']['margin']=dict(r['refs']['profit'],components=[r['refs']['profit'],r['refs']['revenue']],calculation='consolidated GAAP operating profit / same-period consolidated revenue × 100')
            if not rows or not annual or not all(rows[-1].get(m) is not None for m in ('revenue','profit','capex','cloud_revenue')):raise ValueError('Latest financial quarter is incomplete')
            rpo=rpo_history(payload,spec,asof,fields)
            if old.get('schema_version')==1:
                for name,new in [('rows',rows),('annual',years)]:
                    prior=old.get(name,[])
                    if prior and (len(new)<len(prior) or new[-1]['date']<prior[-1]['date']):raise ValueError('Financial history regressed')
                prior=old['rpo']['rows']
                if len(rpo['rows'])<len(prior) or rpo['rows'][-1]['date']<prior[-1]['date']:raise ValueError('RPO history regressed')
            c=dict(schema_version=1,rows=rows,annual=years,rpo=rpo,fields=fields,filings=sorted(known),core_ok=True,cloud_ok=True,checked=asof,fetched=asof,errors=[])
        except Exception as e:
            if not old:raise RuntimeError(key+' has no complete verified history') from e
            c=copy.deepcopy(old);c.update(core_ok=False,cloud_ok=False,checked=asof,errors=[type(e).__name__+': '+str(e)])
        state['companies'][key]=c;save(OUT/'us_neocloud_state.json',state)
        print(key,len(c['rows']),'quarters',len(c['annual']),'years; RPO',len(c['rpo']['rows']),'snapshots;',len(c['errors']),'warnings',flush=True)
    for d in documents(meta,state['companies']):save(OUT/(d['id']+'.json'),d)
    if not offline:state['updated']=dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
    save(OUT/'us_neocloud_state.json',state)
    return state


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--offline',action='store_true');p.add_argument('--full-history',action='store_true')
    a=p.parse_args();collect(a.offline,a.full_history)
