"""USD cloud segment facts from native SEC XBRL instances, not estimates."""
import math
import re
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from cpu_business_history import local,REVENUE_TAGS


def field_for(key,tag,members):
    members={local(m).lower() for m in members}
    members-={'operatingsegmentsmember','reportablesegmentmember'}
    revenue=tag in REVENUE_TAGS
    if key=='xai':
        field='revenue' if revenue else 'profit' if tag=='OperatingIncomeLoss' else 'capex' if tag in ('PaymentsToAcquirePropertyPlantAndEquipment','SegmentExpenditureAdditionToLongLivedAssets') else None
        if not members:return field
        if members in ({'aimember'},{'simember'}):return 'segment_'+field if field else None
    if key=='amzn' and members in ({'amazonwebservicesmember'},{'amazonwebservicessegmentmember'}):
        return 'cloud_revenue' if revenue else 'cloud_profit' if tag=='OperatingIncomeLoss' else None
    if key=='googl' and members in ({'googlecloudmember'},{'googlecloudsegmentmember'}):
        return 'cloud_revenue' if revenue else 'cloud_profit' if tag=='OperatingIncomeLoss' else None
    if key=='msft' and members=={'microsoftcloudmember'} and revenue:return 'cloud_revenue'
    if key=='orcl':
        if tag=='CloudRevenues' and not members:return 'cloud_revenue'
        if revenue and members in ({'cloudservicesmember'},{'cloudrevenuesmember'},{'cloudmember'},{'cloudbusinessmember'}):return 'cloud_revenue'
    return None


def parse_instance(raw,key,meta,filing,asof):
    if filing['filingDate']>asof:return {}
    root=ET.fromstring(raw);contexts={}
    for c in root.findall('{*}context'):
        p={local(x.tag):x.text for x in c.findall('./{*}period/*')}
        identifier=c.find('./{*}entity/{*}identifier')
        if identifier is None or int(identifier.text)!=meta['cik']:raise ValueError('Cloud issuer mismatch')
        members=[x.text for x in c.findall('.//{*}explicitMember')]
        contexts[c.get('id')]=(p,members)
    units={u.get('id'):[local(x.text) for x in u.findall('.//{*}measure')] for u in root.findall('{*}unit')}
    result={}
    for fact in root:
        p,members=contexts.get(fact.get('contextRef'),({},[]));tag=local(fact.tag)
        field=field_for(key,tag,members)
        if not field or not p.get('startDate') or not p.get('endDate') or not '2014-01-01'<=p['endDate']<=asof:continue
        if units.get(fact.get('unitRef'))!=['USD']:continue
        try:value=float(fact.text)
        except (ValueError,TypeError):continue
        if not math.isfinite(value) or field=='cloud_revenue' and value<0:continue
        row=dict(start=p['startDate'],end=p['endDate'],val=value,accn=filing['accessionNumber'],filed=filing['filingDate'],form=filing['form'],
                 source_tag=tag+' · '+', '.join(members),source_url=filing['url'])
        identity=field,row['start'],row['end']
        if identity in result and result[identity]['val']!=value:raise ValueError('Conflicting cloud dimensional facts')
        result[identity]=row
    fields={}
    for (field,_,_),r in result.items():fields.setdefault(field,[]).append(r)
    return fields


def parse_spacex_bootstrap(html,filing,asof):
    """The IPO prospectus has no XBRL instance. Read its complete segment tables.

    Use the AI column and the reported total, not a similarly named MD&A table
    or a subtotal. These are retrospectively recast common-control accounts.
    """
    if filing['filingDate']>asof:return {}
    fields={};seen=set()
    for table in BeautifulSoup(html,'html.parser').select('table'):
        text=table.get_text(' ',strip=True)
        match=re.match(r'(Year Ended December 31,|Three Months Ended March 31,) (20\d{2}) Space Connectivity AI Total Reportable Segments ',text)
        if not match:continue
        year=int(match[2]);end=f'{year}-'+('12-31' if match[1].startswith('Year') else '03-31')
        values={}
        for row in table.select('tr'):
            cells=[c.get_text(' ',strip=True) for c in row.find_all(['td','th'],recursive=False)]
            if not cells:continue
            label=cells[0]
            field='revenue' if label.startswith('Revenue ') else 'profit' if label.startswith('Income (loss) from operations ') else 'capex' if label.startswith('Capital expenditures ') else None
            if not field:continue
            amounts=[]
            for cell in cells[1:]:
                token=cell.replace('$','').replace(',','').strip()
                if token in ('—','–','-'):amounts.append(0.)
                elif re.fullmatch(r'\(?-?\d+(?:\.\d+)?\)?',token):amounts.append(float(token.strip('()'))*(-1 if token.startswith('(') else 1))
            if len(amounts)!=4:raise ValueError('Unexpected SpaceX segment columns')
            values[field]=(amounts[2],amounts[3],label)
        if set(values)!={'revenue','profit','capex'}:continue
        if end in seen:raise ValueError('Duplicate SpaceX complete segment table')
        seen.add(end)
        for field,(segment,total,label) in values.items():
            for name,value in [(field,total),('segment_'+field,segment)]:
                fields.setdefault(name,[]).append(dict(start=f'{year}-01-01',end=end,val=value*1e6,
                    form=filing['form'],filed=filing['filingDate'],accn=filing['accessionNumber'],
                    source_tag='IPO prospectus segment table · '+label+' · '+('AI' if name.startswith('segment_') else 'Total reportable segments'),source_url=filing['url']))
    if seen!={'2023-12-31','2024-12-31','2025-12-31','2025-03-31','2026-03-31'}:
        raise ValueError('SpaceX IPO historical tables incomplete')
    return fields
