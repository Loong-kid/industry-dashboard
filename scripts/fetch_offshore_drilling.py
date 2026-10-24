"""Refresh offshore issuer evidence; failed cohorts retain their last good data.

Network-free rebuild: python scripts/fetch_offshore_drilling.py --offline
Noble's reviewed PDF transcription and non-GAAP supplements are explicit manual
evidence. A newer report is flagged for review, never silently treated as read.
"""
import argparse
import copy
import json
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from offshore_drilling import *

SEC_UA={'User-Agent':'industry-dashboard personal research wkorotk@gmail.com'}


def get(url,*,sec=False):
    response=requests.get(url,headers=SEC_UA if sec else {'User-Agent':'Mozilla/5.0'},timeout=45)
    response.raise_for_status()
    if not response.content:raise ValueError('Empty source')
    return response.content


def report_date(content,fallback):
    with pymupdf.open(stream=content,filetype='pdf') as doc:
        text=' '.join(p.get_text() for p in list(doc)[:2])
    matches=re.findall(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(20\d{2})',text)
    if matches:
        valid=[dt.date(int(y),MONTHS[m.lower()],int(d)).isoformat() for m,d,y in matches]
        valid=[d for d in valid if d<=collection_date()]
        if valid:return max(valid)
    matches=re.findall(r'(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(20\d{2})',text)
    if matches:return max(dt.date(int(y),MONTHS[m.lower()],int(d)).isoformat() for d,m,y in matches)
    return fallback


def discover(company,reviewed):
    config=COMPANIES[company];fallback=reviewed['url']
    if company in ('valaris','seadrill'):
        # A pinned, reviewed source remains usable when the publisher's JS index
        # denies automated access. Fresh-news monitoring below detects new FSRs.
        return fallback
    if company=='odfjell':return config['index']
    soup=BeautifulSoup(get(config['index']),'html.parser')
    if company=='transocean':
        candidates=[urljoin(config['index'],a['href']) for a in soup.select('a[href]') if 'FleetStatusReport' in a['href'] and '.pdf' in a['href'].lower()]
    elif company=='borr':
        candidates=[urljoin(config['index'],a['href']) for a in soup.select('a[href]') if '.pdf' in a['href'].lower() and any(t in a['href'].lower() for t in ('fleet','availability'))]
    else:
        candidates=[urljoin(config['index'],a['href']).split('?')[0] for a in soup.select('a[href]') if 'noble-corporation-fleet-status-report' in a['href'] and '/download/' in a['href']]
    if not candidates:raise ValueError('No official fleet report link')
    return candidates[0]


def monitor_q4_news(company,last_date):
    host={'valaris':'https://www.valaris.com','seadrill':'https://ir.seadrill.com'}[company]
    response=requests.get(host+'/feed/PressRelease.svc/GetPressReleaseList',params={'LanguageId':1,'pageSize':15,'bodyType':1,'pressReleaseDateFilter':3,'year':-1},timeout=45)
    response.raise_for_status();payload=response.json()
    rows=payload.get('GetPressReleaseListResult',[])
    if not isinstance(rows,list):raise ValueError('News index format changed')
    pending=[]
    for row in rows:
        title=row.get('Headline','');raw=row.get('PressReleaseDate','')
        try:date=dt.datetime.strptime(raw.split(' ')[0],'%m/%d/%Y').date().isoformat()
        except ValueError:continue
        if date>last_date and date<=collection_date() and re.search('fleet status|contract awards',title,re.I):
            pending.append({'date':date,'title':title,'url':urljoin(host,row.get('LinkToDetailPage',''))})
    return pending


def apply_curated(state,curated):
    for company in COMPANIES:
        data=state.setdefault('fleets',{}).setdefault(company,{'rows':[]})
        additions=[copy.deepcopy(r) for r in curated.get('additional_rigs',[]) if r['company']==company]
        replacements={r['id']:r for r in additions}
        data['rows']=[copy.deepcopy(replacements[r['id']]) if r['id'] in replacements and max(s.get('as_of','') for s in r['sources'])<=max(s.get('as_of','') for s in replacements[r['id']]['sources']) else r for r in data['rows']]
        ids={r['id'] for r in data['rows']}
        data['rows'] += [r for r in additions if r['id'] not in ids]
        for row in data['rows']:
            patch=curated.get('patches',{}).get(row['id'],{})
            for key,value in patch.items():
                if key not in ('sources_add','add_contracts','contracts_override'):row[key]=copy.deepcopy(value)
            if patch.get('contracts_override') is not None:
                patch_date=max((s.get('as_of','') for s in patch.get('sources_add',[])),default=curated['reviewed'])
                if data.get('as_of','')<=patch_date:row['contracts']=copy.deepcopy(patch['contracts_override'])
            for source in patch.get('sources_add',[]):
                if source not in row['sources']:row['sources'].append(source)
            for c in patch.get('add_contracts',[]):
                value=contract(row['id'],c['customer'],c['location'],c['start'],c['end'],c.get('dayrate'),c.get('kind','firm'),c.get('note',''),c['source'])
                if not any(existing['id']==value['id'] for existing in row['contracts']):row['contracts'].append(value)
    for key in ('financial_supplements','events','fixtures','market_backlog'):
        state[key]=copy.deepcopy(curated.get(key,{} if key=='financial_supplements' else []))
    reviewed={u.rstrip('/') for u in curated.get('reviewed_news',[])}
    for data in state['fleets'].values():
        if 'pending_reports' in data:
            data['pending_reports']=[r for r in data['pending_reports'] if r['url'].rstrip('/') not in reviewed]
            data['review_needed']=bool(data['pending_reports'])
    if not state.get('market'):
        state['market']=copy.deepcopy(curated['market']);state['market_source']=curated['market_source']


def collect(offline=False):
    curated=json.loads((MANUAL/'curated.json').read_text(encoding='utf8'))
    state_path=OUT/'offshore_state.json'
    state=json.loads(state_path.read_text(encoding='utf8')) if state_path.exists() else {'fleets':{},'financials':{}}
    if not state.get('fleets',{}).get('noble'):
        state.setdefault('fleets',{})['noble']={'rows':copy.deepcopy(curated['noble_fleet']), 'as_of':curated['sources']['noble']['as_of'],
          'mode':'reviewed_transcription','checked':curated['reviewed'],'ok':True,'message':'공식 FSR 대조 입력 · 새 보고서 감지 시 검토 후 갱신'}
    failures=[]
    if not offline:
        CACHE.mkdir(parents=True,exist_ok=True)
        parsers={'transocean':parse_transocean,'valaris':parse_valaris,'seadrill':parse_seadrill,'borr':parse_borr,'odfjell':parse_odfjell_fleet}
        for key,parser in parsers.items():
            old=state['fleets'].get(key,{})
            try:
                source=copy.deepcopy(curated['sources'][key]);url=discover(key,source)
                body=get(url)
                source['url']=url;source['as_of']=collection_date() if key=='odfjell' else report_date(body,source['as_of'])
                parsed=parser(body,source)
                old_count=len([r for r in old.get('rows',[]) if r['ownership_kind'] not in ('joint_venture',)])
                if old_count and len(parsed)<old_count*.75:raise ValueError('Unexpected fleet shrinkage requires review')
                state['fleets'][key]={'rows':parsed,'as_of':source['as_of'],'checked':collection_date(),'ok':True,'mode':'automatic','source':source}
                (CACHE/(key+('.html' if key=='odfjell' else '.pdf'))).write_bytes(body)
                print(key,'fleet',len(parsed),source['as_of'])
            except Exception as e:
                state['fleets'][key]={**old,'checked':collection_date(),'ok':False,'message':f'마지막 성공 자료 유지 · {type(e).__name__}: {str(e)[:180]}'}
                failures.append(key+' fleet');print(key,'fleet retained:',type(e).__name__)
        # The reviewed Noble copy is never re-dated on a successful index check.
        try:
            body=get(COMPANIES['noble']['index']);soup=BeautifulSoup(body,'html.parser')
            candidates=[clean(x.get_text()) for x in soup.select('time,.noble-event-date')]
            if not candidates:raise ValueError('Noble report dates missing')
            pending=[]
            for text in candidates:
                try:date=dt.datetime.strptime(text,'%B %d, %Y').date().isoformat()
                except ValueError:continue
                if date>state['fleets']['noble']['as_of']:pending.append(date)
            state['fleets']['noble'].update(checked=collection_date(),ok=True,review_needed=bool(pending))
        except Exception as e:
            state['fleets']['noble'].update(checked=collection_date(),ok=False,message='공시 목록 확인 실패 · 검토 입력된 마지막 선대 유지')
            failures.append('noble index')
        for key in ('valaris','seadrill'):
            try:
                pending=monitor_q4_news(key,state['fleets'].get(key,{}).get('as_of',''))
                # Reviewed events supplement, but never silently replace, the FSR.
                reviewed_urls={e['url'].rstrip('/') for e in curated.get('events',[])}|{u.rstrip('/') for u in curated.get('reviewed_news',[])}
                pending=[r for r in pending if r['url'].rstrip('/') not in reviewed_urls]
                state['fleets'][key]['pending_reports']=pending
                state['fleets'][key]['review_needed']=bool(pending)
            except Exception:
                state['fleets'][key]['news_check_ok']=False
        for key,config in COMPANIES.items():
            if 'cik' not in config:continue
            try:
                url=f"https://data.sec.gov/api/xbrl/companyfacts/CIK{config['cik']:010d}.json"
                body=get(url,sec=True);payload=json.loads(body)
                if int(payload['cik'])!=config['cik']:raise ValueError('SEC issuer mismatch')
                parsed=parse_sec_financials(payload)
                state['financials'][key]={'rows':parsed,'checked':collection_date(),'ok':True,'source_url':url}
                (CACHE/(key+'_facts.json')).write_bytes(body)
                print(key,'quarterly financials',len(parsed))
            except Exception as e:
                old=state['financials'].get(key,{})
                state['financials'][key]={**old,'checked':collection_date(),'ok':False,'message':f'마지막 재무자료 유지 · {type(e).__name__}'}
                failures.append(key+' financials');print(key,'financials retained:',type(e).__name__)
        try:
            index='https://www.odfjelldrilling.com/investor/reports-and-presentations/'
            soup=BeautifulSoup(get(index),'html.parser');reports=[]
            for tr in soup.select('tr'):
                m=re.search(r'ODL\s*[–-]\s*Q([1-4])\s*(20\d{2})',tr.get_text(' ',strip=True))
                a=tr.select_one('a[href]')
                if m and a and int(m[2])>=2023:reports.append((int(m[2]),int(m[1]),urljoin(index,a['href'])))
            if not reports:raise ValueError('Odfjell report list missing')
            old=state['financials'].get('odfjell',{});merged={r['date']:r for r in old.get('rows',[])};failed=[]
            for year,quarter,url in sorted(set(reports)):
                if qend(year,quarter)>collection_date():continue
                try:
                    path=CACHE/f'odfjell_financial_{year}_{quarter}.pdf'
                    body=path.read_bytes() if path.exists() else get(url)
                    src={'title':f'Odfjell Q{quarter} {year} report','url':url,'as_of':qend(year,quarter),'published':report_date(body,qend(year,quarter))}
                    parsed=parse_odfjell_financials(body,year,quarter,src)
                    merged.update({r['date']:r for r in parsed if r['date']>='2023-01-01'})
                    path.write_bytes(body)
                except Exception:failed.append(f'{year}Q{quarter}')
            if not merged:raise ValueError('Odfjell reports could not be parsed')
            latest=max((y,q) for y,q,u in reports)
            state['financials']['odfjell']={'rows':[merged[d] for d in sorted(merged)],'checked':collection_date(),'ok':f'{latest[0]}Q{latest[1]}' not in failed,'source_url':index,'failed_periods':failed}
            print('odfjell quarterly financials',len(merged),'unparsed',failed)
        except Exception as e:
            old=state['financials'].get('odfjell',{});state['financials']['odfjell']={**old,'ok':False,'checked':collection_date(),'message':f'마지막 Odfjell 실적 유지 · {type(e).__name__}'}
            failures.append('odfjell financials');print('Odfjell financials retained:',str(e)[:100])
        try:
            url=curated['market_source']['url'];body=get(url);parsed=parse_market(body)
            prior={(r['date'],r['type']):r for r in state.get('market',curated['market'])}
            prior.update({(r['date'],r['type']):r for r in parsed})
            state['market']=sorted(prior.values(),key=lambda r:(r['date'],r['type']))
            state['market_source']={**curated['market_source'],'as_of':max(r['date'] for r in parsed)}
            state['market_status']={'ok':True,'checked':collection_date()}
        except Exception as e:
            state['market_status']={'ok':False,'checked':collection_date(),'message':'공개 월간 자료 확인 실패 · 대조 입력한 마지막 관측치 유지'}
            failures.append('market');print('Market retained:',type(e).__name__)
        state['checked']=collection_date()
        state['collection_status']={'ok':not failures,'checked':collection_date(),'message':'일부 출처 확인 실패: '+', '.join(failures) if failures else '공개 선대·SEC 재무 확인 완료'}
    apply_curated(state,curated)
    state['reviewed']=curated['reviewed']
    atomic_json(state_path,state)
    for name,doc in build_documents(state).items():atomic_json(OUT/(name+'.json'),doc)
    print('Published',sum(len(x['rows']) for x in state['fleets'].values()),'rig records')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--offline',action='store_true')
    collect(parser.parse_args().offline)
