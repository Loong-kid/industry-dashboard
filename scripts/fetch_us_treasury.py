"""Refresh QRA vintages, nominal coupon auctions and daily par yields anonymously."""
import argparse
import concurrent.futures
import datetime as dt
import json
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from us_treasury_sources import (ROOT, HOME, QRA, YIELDS, TERMS, Client, merge_auctions,
    parse_borrowing, parse_statement, parse_yields, parse_calendar, save, today)

OUT = ROOT / 'data/us-treasury'


def collect_qra(client, old):
    archive = QRA + '/quarterly-refunding-archives/'
    latest = client.get(QRA + '/most-recent-quarterly-refunding-documents', refresh=True)
    latest_soup = BeautifulSoup(latest, 'html.parser')
    result = {}
    for name, slug, parser, label in [
        ('borrowing','quarterly-refunding-financing-estimates-by-calendar-year',parse_borrowing,'Financing Estimates:'),
        ('statements','official-remarks-on-quarterly-refunding-by-calendar-year',parse_statement,'Policy Statement:')]:
        html = client.get(archive + slug, refresh=True)
        soup = BeautifulSoup(html, 'html.parser')
        # Archive links are ordered newest first. Limit by the year headings,
        # not by guessing press-release IDs.
        urls = []
        for a in soup.select('main a[href*="/news/press-releases/"]'):
            cell = a.find_parent(['td','th'])
            header = ' '.join(cell.get('headers',[])) if cell else ''
            heading = a.find_previous(['h2','h3','h4'])
            match = re.search(r'(?:19|20)\d{2}', header or (heading.get_text(' ',strip=True) if heading else ''))
            if match and int(match[0]) < 2014:
                continue
            urls.append(urljoin(HOME,a['href']))
        current = [urljoin(HOME,a['href']) for a in latest_soup.select('main a[href]') if a.get_text(' ',strip=True).startswith(label)]
        urls = list(dict.fromkeys(current+urls))
        if not current or not urls:
            raise ValueError('QRA archive discovery failed: '+name)
        previous = {r['source_url']:r for r in old.get(name,[])}
        def job(url):
            if url in previous and url not in current:
                return previous[url]
            # Compatibility with locally inspected source files, then cached
            # HTTP for historical publications. Current releases are refreshed.
            parsed = parser(client.get(url,refresh=url in current),url)
            return parsed if parsed['publication_date'] <= today() else None
        rows=[]
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            for row in pool.map(job, urls):
                if row and row['publication_date'] >= '2014-01-01':
                    rows.append(row)
        if name=='borrowing':
            rows.extend(json.loads(p.read_text(encoding='utf-8')) for p in (ROOT/'manual/us-treasury').glob('borrowing-*.json'))
        rows=list({r['source_url']:r for r in rows}.values())
        if not rows:
            raise ValueError('Empty QRA archive')
        result[name]=sorted(rows,key=lambda r:r['publication_date'])
        print('QRA',name,len(rows),'latest',result[name][-1]['publication_date'],flush=True)
    # Official tentative calendar remains useful before an offering is announced.
    result['calendar_url'] = next((urljoin(HOME,a['href']) for a in latest_soup.select('main a[href]') if 'Auction Schedule: PDF' in a.get_text()),QRA)
    result['calendar_xml_url'] = next((urljoin(HOME,a['href']) for a in latest_soup.select('main a[href]') if 'Auction Schedule: XML' in a.get_text()),None)
    if not result['calendar_xml_url']:
        raise ValueError('Tentative auction XML link missing')
    result['calendar']=parse_calendar(client.get(result['calendar_xml_url'],refresh=True))
    return result


def collect_auctions(client, old):
    shared='cusip,security_type,security_term,original_security_term,floating_rate,issue_date,reopening,offering_amt,high_yield,bid_to_cover_ratio'
    def job(spec):
        term,newer=spec
        date='comp_auction_close_date' if newer else 'auction_date'
        inflation='inflation_protected' if newer else 'inflation_index_security'
        fields=shared+','+inflation+','+date+(','+','.join(['dir_bid_comp_par_awarded','indir_bid_comp_par_awarded','prim_deal_comp_par_awarded']) if newer else ',direct_bidder_accepted,indirect_bidder_accepted,primary_dealer_accepted')
        return newer,client.api('treasury_securities_auctions_v2' if newer else 'auctions_query',{'filter':f'original_security_term:eq:{term},{inflation}:eq:No,{date}:gte:2014-01-01','sort':date,'fields':fields})
    legacy=[];updated=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for newer,part in pool.map(job,[(t,n) for t in TERMS for n in [False,True]]):
            (updated if newer else legacy).extend(part)
    rows=merge_auctions(legacy,updated)
    if len(rows)<700 or not any(r['term']=='10-Year' and r['completed'] for r in rows):
        raise ValueError('Incomplete nominal coupon auction archive')
    # Only completed results dated today or earlier enter historical charts.
    for row in rows:
        if row['date']>today():
            row.update(completed=False,high_yield=None,bid_to_cover=None,direct=None,indirect=None,dealer=None)
    print('Auctions',len(rows),'completed',sum(r['completed'] for r in rows),flush=True)
    return dict(rows=rows)


def collect_yields(client, old):
    current=int(today()[:4]); prior={r['date']:r for r in old.get('rows',[])}
    def job(year):
        return parse_yields(client.get(YIELDS,params={'data':'daily_treasury_yield_curve','field_tdr_date_value':year},refresh=year>=current-1))
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for rows in pool.map(job,range(2014,current+1)):
            prior.update({r['date']:r for r in rows if '2014-01-01'<=r['date']<=today()})
    rows=sorted(prior.values(),key=lambda r:r['date'])
    if len(rows)<2000:
        raise ValueError('Incomplete daily yield archive')
    print('Yields',len(rows),rows[0]['date'],rows[-1]['date'],flush=True)
    return dict(rows=rows,source_url=HOME+'/resource-center/data-chart-center/interest-rates/TextView?type=daily_treasury_yield_curve')


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--only',choices=['qra','auctions','yields']);args=ap.parse_args()
    failed=[];status={}
    for name,fn in [('qra',collect_qra),('auctions',collect_auctions),('yields',collect_yields)]:
        path=OUT/(name+'.json');old=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
        if args.only and name!=args.only:
            status[name]={k:old.get(k) for k in ['ok','checked','fetched']};continue
        try:
            doc=fn(Client(),old)
            doc.update(ok=True,checked=today(),fetched=today())
            save(path,doc)
        except Exception as exc:
            failed.append(name);print(name,'FAILED',str(exc)[:220],flush=True)
            if not old:
                continue
            doc=dict(old,ok=False,checked=today(),error='Official source refresh failed; last successful observations retained.')
            save(path,doc)
        status[name]={k:doc.get(k) for k in ['ok','checked','fetched']}
    save(OUT/'state.json',dict(checked=today(),fetched=min((r['fetched'] for r in status.values() if r.get('fetched')),default=None),ok=not failed and all(r.get('ok') for r in status.values()),sources=status))
    if failed:
        raise SystemExit('Failed sources: '+', '.join(failed))


if __name__=='__main__':
    main()
