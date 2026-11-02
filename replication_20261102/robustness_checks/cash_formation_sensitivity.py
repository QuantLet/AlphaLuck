"""Cash versus trading over common seven-day horizons and to the close.
Default: replay included cash_hourly_account_inputs.csv with standard library.
Rebuild inputs: python cash_formation_sensitivity.py --root FULL_PROJECT
"""
from pathlib import Path
import argparse,csv,json,math,sys
from collections import defaultdict
B=Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path);a=ap.parse_args()
if a.root:
 import numpy as np
 import pandas as pd
 sys.path.insert(0,str(a.root/'src'))
 import organiser_hourly as oh
 import funding_hourly_sensitivity as fh
 m=oh.Market(a.root)
 formations=pd.read_csv(a.root/'data/derived/organiser_hourly_sweep.csv').formation_hour.astype(int).tolist()
 hours=sorted(set(formations+[h+168 for h in formations if m.lo+(h+168)*fh.HOUR<=m.hi]))
 times=[m.lo+h*fh.HOUR for h in hours]
 # Add the exact close, which need not be a whole hour after opening.
 endpoints=sorted(set(times+[m.hi]));inp=[]
 old=pd.read_csv(a.root/'data/derived/holding_vs_trading_accounts.csv').set_index('tag')
 worst=0.
 for tag in m.tags:
  e=m.equity[m.equity.tag.eq(tag)].set_index('t').reindex(endpoints)
  assert e.equity.notna().all()
  pay=fh.at_times(m.hours,m.pay[tag].cumsum(),np.array(endpoints),side='right',initial=0.)
  values=e.equity.to_numpy()-e.funding.to_numpy()+pay
  gross=np.zeros(len(endpoints))
  for coin in m.coins:
   q=m.quantity(tag,coin,np.array(endpoints));px=m.price(coin,np.array(endpoints));gross+=np.where(q!=0,abs(q)*px,0.)
  for t,v,g in zip(endpoints,values,gross):
   inp.append({'tag':tag,'formation_hour':(t-m.lo)/fh.HOUR,'equity':float(v),'gross_notional':float(g)})
  j=endpoints.index(m.lo+24*fh.HOUR)
  inherited=float(old.loc[tag,'hold_net']-old.loc[tag,'hold_mtm']-old.loc[tag,'funding_hold'])+10000
  worst=max(worst,abs(values[j]-inherited),abs(values[-1]-10000-old.loc[tag,'actual_net']))
 assert worst<1e-6,worst
 with (B/'cash_hourly_account_inputs.csv').open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(inp[0]));w.writeheader();w.writerows(inp)
 (B/'cash_input_validation.json').write_text(json.dumps({'accounts':len(m.tags),'formation_hours':formations,'max_difference_from_main_24h_and_close_usd':worst,'equity_convention':'recorded equity minus daily-booked funding plus hourly-proxy funding, matching organiser_hourly.Sweep.actual_path; excludes transfers and tips from return paths','valuation':'same pooled transaction prices as frozen-book comparison'},indent=2)+'\n')
rows=list(csv.DictReader((B/'cash_hourly_account_inputs.csv').open()))
byhour=defaultdict(dict)
for r in rows:byhour[float(r['formation_hour'])][r['tag']]={k:float(r[k]) for k in ['equity','gross_notional']}
meta=json.loads((B/'cash_input_validation.json').read_text());formations=meta['formation_hours'];close=max(byhour)
assert len(byhour[close])==32
out=[]
for h in formations:
 start=byhour[h];assert set(start)==set(byhour[close])
 record={'formation_hour':h}
 for horizon,end in [('to_close',close),('168h',h+168)]:
  if end not in byhour:
   for bp in [0,10,100]:record[f'cash_gap_pp_{horizon}_cost{bp}']=None;record[f'cash_accounts_ahead_{horizon}_cost{bp}']=None
   continue
  for bp in [0,10,100]:
   gaps=[s['equity']-s['gross_notional']*bp/10000-byhour[end][tag]['equity'] for tag,s in start.items()]
   record[f'cash_gap_pp_{horizon}_cost{bp}']=sum(gaps)/3200
   record[f'cash_accounts_ahead_{horizon}_cost{bp}']=sum(g>0 for g in gaps)
 out.append(record)
with (B/'cash_formation_sweep.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
summary={}
for horizon in ['to_close','168h']:
 summary[horizon]={}
 for bp in [0,10,100]:
  v=sorted(r[f'cash_gap_pp_{horizon}_cost{bp}'] for r in out if r[f'cash_gap_pp_{horizon}_cost{bp}'] is not None)
  import statistics
  summary[horizon][str(bp)]={'windows':len(v),'positive':sum(x>0 for x in v),'median_pp':statistics.median(v),'minimum_pp':min(v),'maximum_pp':max(v)}
summary['at_24h']=next(r for r in out if r['formation_hour']==24)
assert summary['168h']['0']['windows']==169
assert math.isclose(summary['at_24h']['cash_gap_pp_to_close_cost0'],29.74480430912334,abs_tol=1e-10)
assert summary['at_24h']['cash_accounts_ahead_to_close_cost0']==27
# Formation equity cancels at zero cost: cash gap equals negative realised P&L.
for h in [1,24,169]:
 direct=-sum(byhour[h+168][tag]['equity']-s['equity'] for tag,s in byhour[h].items())/3200
 assert math.isclose(direct,next(r for r in out if r['formation_hour']==h)['cash_gap_pp_168h_cost0'],abs_tol=1e-12)
summary['interpretation']='Zero-cost cash gap is negative post-formation realised P&L, not a separate source of alpha. All formation windows overlap on one market path. Costs are hypothetical closure charges on formation gross notional.'
(B/'cash_formation_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
