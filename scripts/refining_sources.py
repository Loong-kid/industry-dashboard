"""Reviewed main statement rows, excluding segment/guarantor and variance tables."""
import re
import itertools
import datetime as dt
from fetch_cpu_companies import reference, days
from oil_sources import financial_soup, html_row, norm, quarter_end


def statement_facts(content,meta,key):
    soup=financial_soup(content);year=int(meta['date'][:4]);q=(int(meta['date'][5:7])-1)//3+1
    annual=meta['form'].startswith('10-K');income=None;cash=None
    for table in soup.find_all('table'):
        text=norm(table.get_text(' ',strip=True))
        if len(text)>24000 or re.search(r'Consolidating Adjustments|\bVariance\b|Operating Segments|Quarterly Results',text,re.I):continue
        if income is None and not re.search(r'\bChange\b',text[:400],re.I) and re.search(r'(?:Operating revenues|Revenues|Sales and other operating revenues)',text,re.I) and re.search(r'(?:Income|Loss).*before income tax',text,re.I) and re.search(r'(?:Earnings (?:\(loss\) )?per common share|Per Share Data|Per Share of Common Stock|per share data)',text,re.I):income=table
        if cash is None and re.search(r'cash.*operating activities',text,re.I) and re.search(r'cash.*financing activities',text,re.I) and re.search(r'Capital expenditures|Additions to property',text,re.I):cash=table
    fields={}
    patterns={
        'revenue':r'^(?:Operating revenues|Revenues|Sales and other operating revenues)\b',
        'profit':r'^(?:Operating (?:income|loss)|(?:Income|Loss)(?: \((?:income|loss)\))? from (?:continuing )?operations)\b',
        'cost':r'^Total Costs and Expenses\b',
        'interest':r'^Interest and debt expense\b',
        'capex':r'^Capital expenditures(?: and investments)?\b' if key!='mpc' else r'^Additions to property, plant and equipment\b',
    }
    if key=='vlo':patterns.update(vie_capex=r'^Capital expenditures of (?:certain variable interest entities|VIEs)\b',dgd_capex=r'^Diamond Green Diesel Holdings LLC',other_vie_capex=r'^Other VIEs\b')
    if key=='mpc':patterns['related_sales']=r'^Sales to related parties\b'
    for field,pattern in patterns.items():
        is_cash=field.endswith('capex');table=cash if is_cash else income
        if table is None:continue
        # Header-only VIE lines must never be mistaken for an aggregate.
        if field=='vie_capex':
            candidates=[r for r in table.find_all('tr') if re.match(pattern,norm(r.get_text(' ',strip=True)),re.I)]
            if not candidates or not re.search(r'\d|[—–]',norm(candidates[0].get_text(' ',strip=True))):continue
        count=3 if annual else 2 if is_cash or q==1 else 4
        inline,values=html_row(soup,pattern,count,table)
        if inline:items=inline
        elif values is not None:
            if annual:periods=[(f'{year-i}-01-01',f'{year-i}-12-31') for i in range(3)]
            elif is_cash:periods=[(f'{year}-01-01',meta['date']),(f'{year-1}-01-01',quarter_end(year-1,q))]
            else:
                periods=[(f'{year}-{(q-1)*3+1:02d}-01',meta['date']),(f'{year-1}-{(q-1)*3+1:02d}-01',quarter_end(year-1,q))]
                if q>1:periods += [(f'{year}-01-01',meta['date']),(f'{year-1}-01-01',quarter_end(year-1,q))]
            items=[dict(start=start,end=end,val=value*1e6,source_tag='original main statement row: '+field) for (start,end),value in zip(periods,values)]
        else:continue
        fields[field]={(f['start'],f['end']):f for f in items}
    result=[]
    for field in ['revenue','profit','capex']:
        if field=='profit' and key=='psx':
            items=[]
            for period,sales in fields.get('revenue',{}).items():
                if any(period not in fields.get(f,{}) for f in ['cost','interest']):continue
                cost=fields['cost'][period];interest=fields['interest'][period]
                items.append(dict(sales,val=sales['val']-cost['val']+interest['val'],source_tag='derived consolidated operating subtotal',derivation='Sales and other operating revenues − total costs and expenses + interest and debt expense. Equity earnings, asset-sale gains and other non-sales income excluded.',inputs=[sales,cost,interest]))
        else:items=list(fields.get(field,{}).values())
        for f in items:
            f=dict(f)
            if field=='revenue' and key=='mpc' and (f['start'],f['end']) in fields.get('related_sales',{}):
                related=fields['related_sales'][f['start'],f['end']]
                f.update(val=f['val']+related['val'],inputs=[dict(f),related],derivation='Sales and other operating revenues plus separately presented sales to related parties.',source_tag='total consolidated sales including separately presented related-party sales')
            if field=='capex':
                parts=[dict(f)]+[group[f['start'],f['end']] for name,group in fields.items() if name!='capex' and name.endswith('capex') and (f['start'],f['end']) in group]
                f['val']=sum(abs(part['val']) for part in parts)
                if len(parts)>1:f.update(derivation='Sum of cash capital expenditures excluding VIEs plus separately disclosed consolidated VIE cash capital expenditures; excludes deferred turnaround/catalyst costs and nonconsolidated JV investments.',inputs=parts,source_tag='sum of consolidated cash capital expenditures rows')
            result.append(dict(f,metric=field,filed=meta['filed'],accn=meta['accn'],form=meta['form'],source_url=meta['url']))
    return result


def reported_accounts(facts,cik,asof):
    """Use each year's first annual/YTD basis, not later discontinued-op totals.

    Direct quarters must reconcile to the actual first nine-month statement.
    Comparatives can supply restated Q1/Q2 when the same year's Q3 reclassified
    discontinued operations. Cash quarters are actual cumulative differences.
    """
    rows={};annual={}
    def ref(f):return reference(dict(f,tag=f.get('source_tag','original statement row')),cik)
    def write(target,year,q,metric,value,parts):
        end=quarter_end(year,q) if q else f'{year}-12-31'
        r=target.setdefault(end,dict(date=end,year=year,**({'quarter':q,'start':f'{year}-{(q-1)*3+1:02d}-01'} if q else {}),refs={}))
        refs=[ref(f) for f in parts]
        r[metric]=value/1e6;r['refs'][metric]=dict(refs[0],components=refs,calculation='reported original-year annual' if not q else 'reported quarter on original-year basis' if len(parts)==1 else 'same fiscal-year cumulative difference on original-year basis')
    for year in range(2014,int(asof[:4])+1):
        for metric in ['revenue','profit','capex']:
            fs=[f for f in facts if f['metric']==metric and f['end']<=asof and f['filed']<=asof and f['start']>=f'{year}-01-01' and f['end']<=f'{year}-12-31']
            def candidates(start,end):
                found={}
                for f in sorted(fs,key=lambda f:(f['filed'],f['accn'])):
                    if f['start']==start and f['end']==end:found.setdefault(f['val'],f)
                return list(found.values())
            ytd={q:candidates(f'{year}-01-01',quarter_end(year,q)) for q in range(1,5)}
            af=[f for f in ytd[4] if f['form'].startswith('10-K')]
            if af:write(annual,year,None,metric,af[0]['val'],[af[0]])
            if metric=='capex':
                for q in range(1,5):
                    current=af[0] if q==4 and af else ytd[q][0] if ytd[q] and q!=4 else None
                    if not current:continue
                    previous=ytd[q-1][0] if q>1 and ytd[q-1] else None
                    if q>1 and previous is None:continue
                    value=current['val']-(previous['val'] if previous else 0)
                    if value>=0:write(rows,year,q,metric,value,[current]+([previous] if previous else []))
                continue
            direct={q:candidates(f'{year}-{(q-1)*3+1:02d}-01',quarter_end(year,q)) for q in range(1,4)}
            selected={q:options[0] for q,options in direct.items() if options}
            if ytd[3] and len(selected)==3:
                target=ytd[3][0]['val']
                compatible=next((combo for combo in itertools.product(*(direct[q] for q in (1,2,3))) if abs(sum(f['val'] for f in combo)-target)<=3e6),None)
                if compatible is None:raise ValueError(f'{year} {metric}: direct quarters do not match original nine months')
                selected=dict(zip((1,2,3),compatible))
            for q,f in selected.items():write(rows,year,q,metric,f['val'],[f])
            if af and ytd[3]:
                value=af[0]['val']-ytd[3][0]['val']
                if metric=='profit' or value>=0:write(rows,year,4,metric,value,[af[0],ytd[3][0]])
    return [r for _,r in sorted(rows.items())],[r for _,r in sorted(annual.items())]
