"""Reproduce the reviewed global-equipment snapshot from issuer documents.

Run with --download to populate the ignored source cache from the reviewed
manifest. New reporting periods must be added to that manifest after review.
"""
import argparse,hashlib,json,re
import requests
from equipment_global_sources import *
from fetch_cpu_companies import load,save,parse_annual


def import_sources(download=False):
    manifest=load(ROOT/'manual/equipment_ir_sources.json',{})
    seeds=load(ROOT/'manual/equipment_reviewed.json',{})
    CACHE.mkdir(parents=True,exist_ok=True)
    if download:
        import pymupdf
        for name,source in manifest.items():
            if (CACHE/(name+source['extension'])).exists():continue
            r=requests.get(source['url'],headers={'User-Agent':'industry-dashboard personal research wkorotk@gmail.com'},timeout=45);r.raise_for_status()
            (CACHE/(name+source['extension'])).write_bytes(r.content)
    result={};documents={}
    for name,source in manifest.items():
        path=CACHE/(name+source['extension'])
        textpath=CACHE/(name+'.txt')
        if source['extension']=='.pdf' and not textpath.exists():
            import pymupdf
            with pymupdf.open(path) as pdf:textpath.write_text('\n'.join(p.get_text(sort=True) for p in pdf),encoding='utf-8')
        if path.exists():documents[name]=dict(url=source['url'],sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    for key in ('asm','tel','advantest','besi'):
        reports=[]
        for name,source in manifest.items():
            if source.get('company')!=key or source['extension']!='.pdf':continue
            text=(CACHE/(name+'.txt')).read_text(encoding='utf-8')
            parser={'asm':parse_asm,'tel':parse_tel,'advantest':parse_adv_report,'besi':parse_besi}[key]
            reports.append(parser(text,source['year'],source['quarter'],source['url']))
        if key in ('tel','advantest'):rows,annual=difference_cumulative(reports)
        else:rows=reports;annual=annualize(rows)
        result[key]=dict(rows=rows,annual=annual)
    source=manifest['disco_book']
    rows,annual=parse_disco((CACHE/'disco_book.xlsx').read_bytes(),source['url'])
    result['disco']=dict(rows=rows,annual=annual)
    # TEL's workbook supplies cash PP&E purchases and older completed years.
    import openpyxl
    book=openpyxl.load_workbook(CACHE/'tel_book.xlsx',read_only=True,data_only=True)
    income=list(book['1-2 Consol. Statements of Incom'].values)
    cash=list(book['1-4 Consol. Statements of Cash'].values)
    capex=next(r for r in cash if r[1]=='Purchase of property, plant and equipment')
    profit=next(r for r in income if r[1]=='Operating income')
    result['tel']['annual']=[observation(int(year),4,4,dict(revenue=income[4][col],profit=profit[col],capex=abs(capex[col])),manifest['tel_book']['url'],'공시 연간')
        for col,year in enumerate(income[3]) if isinstance(year,int)]
    for key,cohort in seeds['companies'].items():
        target=result.setdefault(key,dict(rows=[],annual=[]))
        for period in ('rows','annual'):
            by={(r['year'],r.get('quarter',4)):r for r in target[period]}
            for row in cohort.get(period,[]):
                identity=row['year'],row.get('quarter',4)
                if identity in by:
                    merged=dict(by[identity]);merged.update(row);merged['refs']={**by[identity]['refs'],**row['refs']};by[identity]=merged
                else:by[identity]=row
            target[period]=sorted(by.values(),key=lambda r:r['date'])
    for key in ('asml','camtek'):
        payload=load(CACHE/f'sec_{key}_facts.json',{})
        result[key]['annual']=parse_annual(payload,METADATA[key],today())
    result['hanmi']=parse_hanmi(load(ROOT/'manual/equipment_hanmi.json',{}))
    for key,cohort in result.items():
        cohort.update(checked=seeds['reviewed'],fetched=seeds['reviewed'],ok=True)
        cohort['rows'].sort(key=lambda r:r['date']);cohort['annual'].sort(key=lambda r:r['date'])
        if key in ('asm','besi'):
            existing={r['year']:r for r in annualize(cohort['rows'])}
            existing.update({r['year']:r for r in cohort['annual']})
            cohort['annual']=sorted(existing.values(),key=lambda r:r['date'])
        for metric in ('revenue','profit','capex'):
            actual=[r for r in cohort['rows'] if metric in r]
            years=[r for r in cohort['annual'] if metric in r]
            if not actual and not years:raise ValueError(key+': missing '+metric)
        print(key,len(cohort['rows']),'quarters',len(cohort['annual']),'years')
    save(ROOT/'manual/equipment_global.json',dict(reviewed=seeds['reviewed'],documents=documents,companies=result))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--download',action='store_true')
    import_sources(parser.parse_args().download)
