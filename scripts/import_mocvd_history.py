"""Import bounded, reviewed historical source snapshots; never interpolate quarters.

Input: original AIXTRON PDFs plus SEC companyfacts JSON snapshots. The SEC
snapshots may be obtained from Canli Capital's explicitly published public archive.
The archive's uncompressed SHA-256 must match its published selection metadata.
Only dated financial facts and provenance are exported, not full reports.
"""
import argparse
import calendar
import datetime as dt
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVENUE = ['RevenueFromContractWithCustomerExcludingAssessedTax',
           'RevenueFromContractWithCustomerIncludingAssessedTax', 'Revenues', 'SalesRevenueNet']
TAGS = {'revenue': REVENUE, 'profit': ['OperatingIncomeLoss'],
        'capex': ['PaymentsToAcquirePropertyPlantAndEquipment']}


def aix_history(folder, asof):
    registry=read(folder/'aix-registry.json')
    annual_values={
        2014:[153.4,193.8,-58.3,148.5,65.2,66.928],
        2015:[167.1,197.8,-26.7,151.0,42.9,24.011],
        2016:[225.1,196.5,-21.4,155.7,78.1,26.146],
        2017:[263.8,230.4,4.9,188.0,108.6,30.266],
        2018:[302.5,268.8,41.5,221.8,138.3,53.314],
        2019:[231.9,259.6,39.0,207.3,116.7,51.051],
        2020:[301.4,269.2,34.8,223.0,150.9,50.824],
        2021:[497.3,429.0,99.0,366.5,214.6,77.041],
    }
    rows=[]
    for source in sorted(registry,key=lambda r:(r['year'],r['quarter'])):
        y,q=source['year'],source['quarter']
        text=Path(source['path']).with_suffix('.txt').read_text(encoding='utf-8')
        summary='\n'.join(text.split('PAGE ')[:4])
        row=dict(date=f'{y}-{q*3:02}-{calendar.monthrange(y,q*3)[1]}',year=y,quarter=q,
                 url=source['url'],fetched=asof,refs={},orders_scope='equipment' if y==2014 else 'total')
        if q==4:
            keys=['orders_ytd','revenue_ytd','ebit_ytd','equipment_ytd','backlog','advances']
            row.update(zip(keys,annual_values[y]))
            # PDF pages include the cover and differ from printed page numbers.
            pages={2014:[3,3,3,35,3,55],2015:[37,3,3,35,3,56],
                   2016:[40,3,3,37,3,60],2017:[3,3,3,33,3,53],
                   2018:[56,87,87,57,56,89],2019:[63,93,93,64,63,95],
                   2020:[75,107,107,77,75,109],2021:[85,120,120,86,85,122]}
            row['refs'].update(zip(keys,pages[y]))
            rows.append(row);continue
        def flow(pattern):
            m=re.search(r'^\s*'+pattern+r'\s+([^\n]+)',summary,re.M|re.I)
            if not m:raise ValueError(f'AIX {y} Q{q} missing {pattern}')
            vals=re.findall(r'[-+]?\d+\.\d+',m[1])
            return float(vals[1 if y==2017 and q==1 else 0])
        row['orders_ytd']=flow(r'(?:(?:Equipment|Total) )?Order intake')
        row['revenue_ytd']=flow('Revenues')
        row['ebit_ytd']=flow(r'(?:Operating result \(EBIT\)|EBIT)')
        row['backlog']=flow(r'(?:Equipment )?Order backlog(?:\s*\([^\n]*?\))?')
        if y==2017 and q in [2,3]:
            row.update(zip(['orders_ytd','revenue_ytd','ebit_ytd','backlog'],
                           {2:[128.5,114.1,-24.1,93.4],3:[197.9,176.3,-19.5,99.2]}[q]))
        for key in ['orders_ytd','revenue_ytd','ebit_ytd','backlog']:row['refs'][key]=2
        # Tables are preferred to narratives, which can discuss a single
        # quarter inside an otherwise YTD report.
        m=re.search(r'^\s*Equipment revenues\s+([\d,.]+)\s',text,re.M|re.I)
        if not m:m=re.search(r'^\s*([\d.]+)\s+[^\n]*Equipment revenues\s*$',text,re.M|re.I)
        if not m:
            period={1:'Q1',2:'H1',3:'9M'}[q]
            m=re.search(fr'Equipment revenues in {period}/{y} were EUR\s+([\d.]+)',text,re.I)
        if not m and q==1:
            m=re.search(r'Equipment revenues[^\n]{0,90}?EUR\s+([\d.]+)',text,re.I)
        if m:
            row['equipment_ytd']=float(m[1].replace(',',''))/(1000 if ',' in m[1] else 1)
            row['refs']['equipment_ytd']=text[:m.start()].count('PAGE ')
        m=re.search(r'^\s*Contract liabilities for advance payments\s+([\d.]+)',summary,re.M)
        if m:row['advances']=float(m[1]);row['refs']['advances']=2
        else:
            # Balance sheet units are EUR thousands; do not read the cash-flow
            # line with the same caption (a change, not the closing balance).
            for match in re.finditer(r'^\s*Advance payments from customers\s+([\d,]+)\s+([\d,]+)\s*$',text,re.M):
                nearby=text[max(0,match.start()-7000):match.start()]
                if re.search('Balance Sheet|BALANCE SHEET|statement of financial position',nearby,re.I):
                    row['advances']=float(match[1].replace(',',''))/1000
                    row['refs']['advances']=text[:match.start()].count('PAGE ');break
        rows.append(row)
    return rows


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sec_history(folder, company, asof):
    raw = (folder/f'{company}-sec-mirror.json').read_bytes()
    meta = read(folder/f'{company}-selected.json')
    assert hashlib.sha256(raw).hexdigest() == meta['source_sha256'], 'Source hash mismatch'
    doc = json.loads(raw)
    cik = {'coherent':820318, 'lumentum':1633978, 'veeco':103145, 'powi':833640}[company]
    assert int(doc['cik']) == cik
    facts = doc['facts']['us-gaap']
    def select(tags):
        result = {}
        for priority, tag in reversed(list(enumerate(tags))):
            for item in facts.get(tag, {}).get('units', {}).get('USD', []):
                if not item.get('start') or item['filed'] > asof or item['end'] > asof:
                    continue
                if item.get('form') not in ['10-K','10-Q','10-K/A','10-Q/A']:
                    continue
                key = (item['start'], item['end'])
                rank = (item['filed'], -priority)
                if key not in result or rank > result[key]['rank']:
                    result[key] = dict(item, tag=tag, rank=rank)
        return result
    selected = {key:select(tags) for key,tags in TAGS.items()}
    # Coherent stopped presenting an operating-income subtotal. Reconstruct it
    # from pretax income + interest expense - net nonoperating income. Its
    # OtherOperatingIncomeExpenseNet is income-positive in the XBRL source;
    # the printed statement instead presents expenses as positive numbers.
    if company == 'coherent':
        pretax = select(['IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest'])
        interest = select(['InterestExpenseOperating','InterestExpense'])
        other = select(['OtherOperatingIncomeExpenseNet'])
        for interval,a in pretax.items():
            if interval[1] < '2024-07-01' or interval in selected['profit']:
                continue
            if interval not in interest or interval not in other:
                continue
            components = [a,interest[interval],other[interval]]
            if len({v['accn'] for v in components}) != 1:
                continue
            selected['profit'][interval] = dict(a, val=a['val']+interest[interval]['val']-other[interval]['val'],
                tag='calculated_operating_profit', components=[dict(v,rank=None) for v in components])
    def length(interval):
        return (dt.date.fromisoformat(interval[1])-dt.date.fromisoformat(interval[0])).days+1
    annual_intervals = {key for values in selected.values() for key in values if 350 <= length(key) <= 380}
    # Actual fiscal starts anchor 52/53-week reporters. Do not use calendar FY
    # labels from XBRL's fy field: comparative facts carry the filing's FY.
    anchors = sorted(annual_intervals)
    if company in ['veeco','powi']:
        # An incomplete current year still has valid published quarters.
        years={int(e[:4]) for values in selected.values() for s,e in values if s.endswith('-01-01')}
        anchors=sorted(set(anchors) | {(f'{y}-01-01',f'{y}-12-31') for y in years})
    annuals, quarters = {}, {}
    def provenance(fact):
        accn = fact['accn']
        return dict(url=f'https://www.sec.gov/Archives/edgar/data/{cik}/{accn.replace("-", "")}/{accn}-index.html',
                    accession=accn,filed=fact['filed'],tag=fact['tag'],start=fact['start'],end=fact['end'],
                    archive_url=f'https://canlicapital.com/company-data/{cik:010}.json',
                    archive_sha256=meta['source_sha256'],
                    **({'calculation':'pretax + interest - other income (income-positive XBRL)',
                        'components':fact['components']} if fact.get('components') else {}))
    for start,end in anchors:
        fiscalyear = int(end[:4])
        if not 2014 <= fiscalyear <= int(asof[:4]):continue
        annual = dict(date=end,year=fiscalyear,period=f'FY{fiscalyear}',fetched=asof,refs={})
        for metric,values in selected.items():
            a=values.get((start,end))
            if a:
                annual[metric]=round(a['val']/1e6,6);annual['refs'][metric]=provenance(a)
            ytd={e:v for (s,e),v in values.items() if s==start and start<=e<=end}
            ends=sorted({e for (s,e) in values if start<=s<=e<=end and 75<=length((s,e))<=105} | set(ytd))
            for e in ends:
                elapsed=(dt.date.fromisoformat(e)-dt.date.fromisoformat(start)).days+1
                q=round(elapsed/91.25)
                if not 1<=q<=4 or abs(elapsed-q*91.25)>15:continue
                if e==end:q=4
                direct=[v for (s,ee),v in values.items() if ee==e and s>=start and 75<=length((s,e))<=105]
                supporting=[]
                if direct:
                    a=max(direct,key=lambda v:v['rank']);value=a['val'];supporting=[provenance(a)]
                elif e in ytd:
                    a=ytd[e]
                    if q==1:value=a['val'];supporting=[provenance(a)]
                    else:
                        previous=[v for ee,v in ytd.items() if ee<e and abs((dt.date.fromisoformat(ee)-dt.date.fromisoformat(start)).days+1-(q-1)*91.25)<=15]
                        if not previous:continue
                        prev=max(previous,key=lambda v:v['end'])
                        value=a['val']-prev['val'];supporting=[provenance(a),provenance(prev)]
                else:continue
                row=quarters.setdefault((fiscalyear,q),dict(date=e,year=fiscalyear,quarter=q,period=f'FY{fiscalyear} Q{q}',fetched=asof,refs={}))
                assert row['date']==e, f'Duplicate fiscal period: {company} {fiscalyear}Q{q}'
                row[metric]=round(value/1e6,6)
                row['refs'][metric]=dict(supporting[0],supporting_sources=supporting,
                    calculation='reported quarter' if len(supporting)==1 else 'YTD minus previous YTD')
        if annual['refs']:
            annual['url']=next(iter(annual['refs'].values()))['url'];annuals[end]=annual
    for row in quarters.values():row['url']=next(iter(row['refs'].values()))['url']
    return dict(quarters=sorted(quarters.values(),key=lambda r:r['date']),annuals=sorted(annuals.values(),key=lambda r:r['date']),
                provenance=dict(entity=doc['entityName'],cik=cik,sec_url=meta['source_url'],archive_sha256=meta['source_sha256'],captured=meta['fetched_at']))


def main():
    p=argparse.ArgumentParser();p.add_argument('--source-dir',type=Path,required=True);p.add_argument('--as-of',required=True)
    args=p.parse_args();dt.date.fromisoformat(args.as_of)
    result=dict(reviewed=args.as_of,companies={})
    for company in ['coherent','lumentum','veeco']:
        result['companies'][company]=sec_history(args.source_dir,company,args.as_of)
        rows=result['companies'][company]['quarters']
        print(company,len(rows),{k:sum(k in r for r in rows) for k in TAGS})
    result['aix']=aix_history(args.source_dir,args.as_of)
    dest=ROOT/'manual/mocvd_history.json'
    if dest.exists():
        existing=read(dest)
        result.update({k:v for k,v in existing.items() if k not in result})
        result['companies'].update({k:v for k,v in existing.get('companies',{}).items() if k not in result['companies']})
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=1)+'\n',encoding='utf-8')


if __name__=='__main__':main()
