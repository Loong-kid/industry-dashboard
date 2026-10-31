"""USD cloud segment facts from native SEC XBRL instances, not estimates."""
import math
import xml.etree.ElementTree as ET
from cpu_business_history import local,REVENUE_TAGS


def field_for(key,tag,members):
    members={local(m).lower() for m in members}
    members-={'operatingsegmentsmember','reportablesegmentmember'}
    revenue=tag in REVENUE_TAGS
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
