from collect_prices import *
from collections import Counter
cash=json.loads((OLD/'results/cash_ledger.json').read_text());positions=json.loads((OLD/'results/positions_ledger.json').read_text());targets=set();states=[]
for p in POS:
    model=p['model_id'];flow=next(x for x in cash if x['model_id']==model and x['category']=='external_funding' and x['time_utc']>'2026-02-10')
    q=Counter()
    for x in positions:
        if x['model_id']==model and x['time_utc']<flow['time_utc']:
            for a in x['changes']:q[a['token_id']]+=a['quantity_raw']
    q={t:v for t,v in q.items() if v};assert all(v>0 for v in q.values())
    targets|=q.keys();targets|=p['formation_positions_raw'].keys()
    states.append({'model_id':model,'funding':flow,'before_funding_positions_raw':q})
(RAW/'funding_checkpoints.json').write_text(json.dumps(states,indent=2))
cut=max(dt.datetime.fromisoformat(s['funding']['time_utc']).replace(tzinfo=dt.timezone.utc).timestamp() for s in states)
scan_prices(('funding',cut,targets,'02'))
