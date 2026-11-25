"""Price-only industry momentum with exact market-session anchors and no filling."""
import math

WINDOWS = {'ret_1d':1,'ret_1w':5,'ret_1m':21,'ret_3m':63,'ret_6m':126,'ret_12m':252}


def valid(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and value > 0


def clean_prices(rows):
    return {date:float(value) for date,value in rows if valid(value)}


def equal_weight_history(calendar, members):
    """Rebalance equally at each common observation; a missing member is never dropped.

    Between common dates weights drift without rebalancing. Missing sessions are
    absent from the output (renderers retain calendar gaps). No IPO backfill.
    """
    if not members:
        return []
    maps = [clean_prices(rows) for rows in members]
    result = []
    previous = None
    level = 100.0
    for date in calendar:
        if not all(date in prices for prices in maps):
            continue
        if previous is not None:
            level *= sum(prices[date]/prices[previous] for prices in maps)/len(maps)
        result.append([date,round(level,8)])
        previous = date
    return result


def metrics(calendar, history, benchmark):
    values = clean_prices(history)
    reference = clean_prices(benchmark)
    current = values.get(calendar[-1]) if calendar else None
    result = {key:None for key in WINDOWS}
    for key, lag in WINDOWS.items():
        if current is not None and len(calendar) > lag:
            base = values.get(calendar[-1-lag])
            if base is not None:
                result[key] = round((current/base-1)*100,6)
    for label, lag in [('relative_1m',21),('relative_3m',63)]:
        if current is not None and len(calendar) > lag:
            date = calendar[-1-lag]
            base, b0, b1 = values.get(date), reference.get(date), reference.get(calendar[-1])
            result[label] = round(((current/base-1)-(b1/b0-1))*100,6) if all(valid(v) for v in (base,b0,b1)) else None
        else:
            result[label] = None
    means = {}
    for count in (50,200):
        window = [values.get(d) for d in calendar[-count:]]
        mean = sum(window)/count if len(window)==count and all(valid(v) for v in window) else None
        means[count] = mean
        result[f'sma{count}_gap'] = round((current/mean-1)*100,6) if valid(current) and valid(mean) else None
    short, long = means[50], means[200]
    result['trend'] = 'unavailable' if not all(valid(v) for v in (current,short,long)) else 'up' if current>short>long else 'down' if current<short<long else 'mixed'
    return result


def build_market(spec, snapshots, collected_at, version):
    benchmark_spec = spec['benchmark']
    benchmark_snapshot = snapshots.get(benchmark_spec['symbol'],{})
    benchmark_history = benchmark_snapshot.get('prices',[])
    calendar = [r[0] for r in benchmark_history]
    asof = calendar[-1] if calendar else None
    benchmark_ok = bool(benchmark_snapshot.get('ok') and calendar)
    benchmark = {**benchmark_spec,'history':benchmark_history,'date':asof,'ok':benchmark_ok,
                 'fetched':benchmark_snapshot.get('fetched'),'errors':benchmark_snapshot.get('errors',[]),
                 'metrics':metrics(calendar,benchmark_history,benchmark_history)}
    rows = []
    for industry in spec['industries']:
        members = [snapshots.get(i['symbol'],{}) for i in industry['instruments']]
        histories = [member.get('prices',[]) for member in members]
        if industry['kind']=='basket':
            history = equal_weight_history(calendar,histories)
        else:
            allowed = set(calendar)
            history = [r for r in histories[0] if r[0] in allowed]
        last = history[-1] if history else None
        errors = [f"{i['symbol']}: {error}" for i,member in zip(industry['instruments'],members) for error in member.get('errors',[])]
        if not benchmark_ok:
            status = 'benchmark_error'
        elif not all(member.get('ok') for member in members):
            status = 'fetch_error'
        elif not last or last[0]!=asof:
            status = 'stale'
        else:
            status = 'ok'
        calculated = metrics(calendar,history,benchmark_history)
        rows.append({**industry,'history':history,'metrics':calculated,'status':status,
                     'eligible':status=='ok' and calculated['ret_3m'] is not None,
                     'first_date':history[0][0] if history else None,'price_date':last[0] if last else None,'price':last[1] if last else None,
                     'fetched':min((m.get('fetched') or '' for m in members),default='') or None,'errors':errors,
                     'member_coverage':sum(asof in clean_prices(h) for h in histories) if asof else 0,
                     'member_count':len(members),
                     'instruments':[{**i,'quote_name':member.get('quote_name'),'price_date':member.get('prices',[['',None]])[-1][0] if member.get('prices') else None,
                                     'fetched':member.get('fetched'),'ok':member.get('ok',False),
                                     'provider':member.get('provider'),
                                     'price_source':'https://finance.naver.com/item/fchart.naver?code='+i['symbol'].split('.')[0] if member.get('provider')=='naver' else 'https://finance.yahoo.com/quote/'+i['symbol']+'/history/'} for i,member in zip(industry['instruments'],members)]})
    ranked = sorted((row for row in rows if row['eligible']),key=lambda r:(-r['metrics']['ret_3m'],r['id']))
    for row in rows:
        row['rank_3m'] = next((n+1 for n,r in enumerate(ranked) if r['id']==row['id']),None)
    success_dates=[benchmark_snapshot.get('fetched'),*(row.get('fetched') for row in rows)]
    fetched=min(success_dates) if all(success_dates) else None
    return {'id':'momentum_'+spec['id'],'market':spec['id'],'name':spec['name'],'currency':spec['currency'],
            'timezone':spec['timezone'],'updated':asof,'fetched':fetched,'collected_at':collected_at,'frequency':'daily','stale_days':4,
            'universe_version':version,'benchmark':benchmark,'calendar':calendar,'rows':rows,
            'anchors':{key:calendar[-1-lag] if len(calendar)>lag else None for key,lag in WINDOWS.items()},
            'collection_status':{'ok':benchmark_ok and all(r['status']=='ok' for r in rows),'checked':collected_at,
                                 'excluded':sum(not r['eligible'] for r in rows),'count':len(rows)},
            'auto_collect_time':'08:40 / 18:40 KST'}
