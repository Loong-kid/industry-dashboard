"""Reported equipment financials from issuer PDFs. Never parse adjusted EBITA."""
import datetime as dt
import re

import pymupdf

from telecom_sources import reporting_period
from fetch_telecom import merge_rows


def numeric(text):
    text=re.sub(r'\s','',text).replace(',','').replace('−','-')
    if text in ['—','–','-']:return 0.0  # explicit issuer dash in a numeric table cell
    if text.startswith('(') and text.endswith(')'):text='-'+text[1:-1]
    return float(text)


def row_values(page,label,count,min_x,depth=3):
    """Read a row in its actual numeric columns, excluding notes and parent data.

    Group adjacent words within each monetary cell (including space-separated
    thousands); use the first baseline for wrapped labels, never the next row.
    """
    rects=page.search_for(label)
    if not rects:raise ValueError('PDF label unavailable: '+label)
    rect=rects[0]
    words=[w for w in page.get_text('words') if w[0]>=min_x and rect.y0-2<=w[1]<=rect.y0+depth and re.fullmatch(r'[\d,.()\-−—–]+',w[4])]
    if not words:raise ValueError('PDF numeric row unavailable: '+label)
    baseline=min(w[1] for w in words)
    words=sorted([w for w in words if abs(w[1]-baseline)<2.5],key=lambda w:w[0])
    groups=[];right=-100
    for word in words:
        if word[0]-right>8:groups.append(word[4])
        else:groups[-1]+=' '+word[4]
        right=word[2]
    if len(groups)<count:raise ValueError(f'PDF numeric column mismatch {label}: {groups}')
    return [numeric(g) for g in groups[:count]]


def pdf_ref(url,page,location,**extra):
    return dict(dict(url=url,pdf_page=page+1,location=location,calculation='reported quarter'),**extra)


def parse_ericsson_pdf(raw,url,year,quarter,asof):
    doc=pymupdf.open(stream=raw,filetype='pdf');rows=[]
    for metric,heading,label in [
        ('revenue','Condensed consolidated income statement','Net sales'),
        ('profit','Condensed consolidated income statement','Earnings before financial items and income tax (EBIT)'),
        ('capex','Condensed consolidated statement of cash flow','Investments in property, plant and equipment')]:
        candidates=[(i,p) for i,p in enumerate(doc) if heading.casefold() in p.get_text().casefold() and 'isolated quarters' in p.get_text().casefold() and label in p.get_text()]
        if not candidates:raise ValueError('Ericsson isolated reported statement changed')
        # Contents mentions headings but has no row of actual amounts.
        i,page=next((i,p) for i,p in candidates if 'SEK million' in p.get_text())
        text=page.get_text();header=text[text.casefold().find('isolated quarters, sek million'):]
        labels=re.findall(r'^Q([1-4])\s*$',header,re.M)
        count=quarter+4
        if len(labels)<count:raise ValueError('Ericsson quarter header changed')
        values=row_values(page,label,count,280,depth=4)
        for index,value in enumerate(values):
            y=year if index<quarter else year-1
            q=quarter-index if index<quarter else 4-(index-quarter)
            row=reporting_period(y,q)
            if row['date']>asof:continue
            row[metric]=abs(value) if metric=='capex' else value
            row['refs'][metric]=pdf_ref(url,i,'IFRS isolated quarters · '+label)
            rows=merge_rows(rows,[row])
    return rows


def parse_nokia_pdf(raw,url,year,quarter,asof):
    doc=pymupdf.open(stream=raw,filetype='pdf');rows=[]
    for metric,heading,labels in [
        ('revenue','Consolidated income statement',['Net sales']),
        ('profit','Consolidated income statement',['Operating profit','Operating (loss)/profit','Operating profit/(loss)','Operating loss']),
        ('capex','Consolidated statement of cash flows',['Purchase of property, plant and equipment and intangible assets'])]:
        candidates=[(i,p) for i,p in enumerate(doc) if heading.casefold() in p.get_text().casefold() and 'EUR million' in p.get_text()]
        if not candidates:raise ValueError('Nokia consolidated statement changed')
        i,page=candidates[0]
        label=next((s for s in labels if page.search_for(s)),None)
        if not label:raise ValueError('Nokia reported metric unavailable')
        headers=[w for w in page.get_text('words') if re.fullmatch(r"Q[1-4]['’]\d{2}",w[4])]
        if not headers:raise ValueError('Nokia actual quarter header unavailable')
        left=min(w[0] for w in headers)-15
        values=row_values(page,label,4 if quarter==2 else 2,left,depth=4)
        for y,value in zip([year,year-1],values):
            row=reporting_period(y,quarter)
            if row['date']>asof:continue
            row[metric]=abs(value) if metric=='capex' else value
            row['refs'][metric]=pdf_ref(url,i,'Reported IFRS · '+label)
            rows=merge_rows(rows,[row])
        if quarter==2:
            # Q1 is the half-year minus Q2 in the SAME restated document.
            for y,current,cumulative in zip([year,year-1],values[:2],values[2:]):
                value=(abs(cumulative)-abs(current)) if metric=='capex' else cumulative-current
                if metric!='profit' and value<0:raise ValueError('Nokia incompatible same-document YTD')
                row=reporting_period(y,1);row[metric]=value
                row['refs'][metric]=pdf_ref(url,i,'Reported IFRS · same-document H1 minus Q2 · '+label,calculation='same-document H1 minus Q2')
                rows=merge_rows(rows,[row])
    return rows


def zte_report(raw,url,year,quarter,asof):
    """Keep current consolidated and comparative columns, never parent-only.

    Q1 2026 is a scanned statement and is handled by a reviewed source record.
    PRC operating profit has a different definition; keep the issuer label.
    """
    doc=pymupdf.open(stream=raw,filetype='pdf');reports={}
    annual=quarter==4
    for metric,label in [('revenue','Operating revenue'),('profit','Operating profit'),('capex','Cash paid for acquisition of property, plant and equipment')]:
        candidates=[]
        for i,p in enumerate(doc):
            t=p.get_text().lower()
            if not p.search_for(label) and not (metric=='capex' and p.search_for(label.replace('paid for','paid to'))):continue
            expected='consolidated cash flow statement' if metric=='capex' else 'consolidated income statement'
            if (expected in t[:450] and re.search(r'note\s+v\b',t)) or (quarter==3 and ('cash flow statement' if metric=='capex' else 'income statement') in t):candidates.append((i,p))
        if not candidates:raise ValueError('ZTE statement unavailable: '+metric)
        i,page=candidates[0]
        if not page.search_for(label):label=label.replace('paid for','paid to')
        # Q3 4 columns: current consolidated, current parent, prior consolidated,
        # prior parent. Annual and H1 are 2 consolidated columns.
        vals=row_values(page,label,4 if quarter==3 else 2,270 if quarter==3 else 380,depth=30 if metric=='capex' else 4)
        values=[vals[0],vals[2]] if quarter==3 else vals
        for y,value in zip([year,year-1],values):
            reports.setdefault(y,dict(year=y,quarter=quarter,fields={}))['fields'][metric]=dict(value=None,ytd=abs(value)/1000 if metric=='capex' else value/1000,
                tag='PRC:'+metric,filed=asof,start=f'{y}-01-01',end=reporting_period(y,quarter)['date'],**pdf_ref(url,i,'PRC ASBEs · Consolidated · '+label))
        if quarter==3 and metric!='capex':
            # A second statement contains Jul-Sep isolated income. Its values
            # are used directly while the first statement remains the YTD.
            i,page=candidates[1]
            vals=row_values(page,label,4,270,depth=4)
            for y,value in zip([year,year-1],[vals[0],vals[2]]):reports[y]['fields'][metric]['value']=value/1000;reports[y]['fields'][metric]['direct_pdf_page']=i+1
    return list(reports.values())
