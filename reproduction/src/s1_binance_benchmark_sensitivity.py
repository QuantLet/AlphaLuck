"""Price-only S1 sensitivity; never modifies the input project.

python s1_binance_benchmark_sensitivity.py --root PROJECT --prices MARKS.csv --out OUTPUT
Optional --reference-benchmark-script verifies the zero-position-safe internal benchmark.
Both actual and frozen books are revalued; recorded realised P&L, fees and funding are unchanged.
Binance spot is a proxy, never an exact Hyperliquid oracle, execution, or liquidation price.
"""
from pathlib import Path
import argparse,datetime,hashlib,importlib.util,json,sys
import numpy as np
import pandas as pd
COINS=('BTC','ETH','SOL','BNB','DOGE','XRP')
GRID=300_000
CAPITAL=10000.0

def utc(t):return datetime.datetime.fromtimestamp(int(t)/1000,datetime.timezone.utc).isoformat()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,(np.integer,)):return int(x)
 if isinstance(x,(np.floating,float)):return float(x) if np.isfinite(x) else None
 if isinstance(x,np.bool_):return bool(x)
 return x

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--root',required=True,type=Path);ap.add_argument('--prices',required=True,type=Path);ap.add_argument('--out',required=True,type=Path)
 ap.add_argument('--reference-benchmark-script',type=Path);ap.add_argument('--ledger-label',default='Inherited from input equity.parquet, unchanged')
 ap.add_argument('--start-ms',type=int,default=1760738400000);ap.add_argument('--end-ms',type=int,default=1762214399000)
 args=ap.parse_args();args.root=args.root.resolve();args.out.mkdir(parents=True,exist_ok=True)
 der=args.root/'data/derived';lo,hi=args.start_ms,args.end_ms
 pan=pd.read_parquet(der/'panel.parquet');pan=pan[pan.season.eq('S1')&pan.t.between(lo,hi)]
 eq=pd.read_parquet(der/'equity.parquet');eq=eq[eq.season.eq('S1')&eq.t.between(lo,hi)]
 fills=pd.read_parquet(der/'fills.parquet');fills=fills[fills.season.eq('S1')]
 fu=pd.read_parquet(der/'funding.parquet');fu=fu[fu.season.eq('S1')]
 marks=pd.read_csv(args.prices);marks=marks[marks.coin.isin(COINS)&marks.t.between(lo,hi)]
 assert not marks.duplicated(['coin','t']).any()
 if 'source_close_time_ms' in marks:assert (marks.source_close_time_ms<marks.t).all()
 prices=marks.pivot(index='t',columns='coin',values='px').sort_index()
 original_grid=np.sort(pan.t.unique());base_end=int(original_grid[-1]);external_end=int(prices.index.max())
 assert external_end>=base_end
 fullgrid=np.arange(int(original_grid[0]),external_end+GRID,GRID,dtype='int64')
 assert np.array_equal(original_grid,fullgrid[fullgrid<=base_end])
 assert prices.reindex(fullgrid)[list(COINS)].notna().all().all()
 # Extra terminal only carries unchanged positions and cash; no unobserved late events may exist.
 late_fills=fills[fills.time.gt(base_end)&fills.time.le(external_end)]
 late_funding=fu[fu.time.gt(base_end)&fu.time.le(external_end)]
 if len(late_fills) or len(late_funding):raise ValueError('Cannot forward carry past input terminal: late ledger events exist')
 refs={}
 if args.reference_benchmark_script:
  sys.path.insert(0,str(args.root/'src'))
  spec=importlib.util.spec_from_file_location('reference_exante',args.reference_benchmark_script)
  ref=importlib.util.module_from_spec(spec);spec.loader.exec_module(ref);ref.DER=str(der)
  for h in (12,24,48):refs[h]=ref.run('S1',form_hours=h,mmr=0).set_index('tag')
 rows=[];position_rows=[];price_rows=[];path_rows=[];max_ref_error=0.;endpoint_identity_max_error=0.
 for tag,w in pan.groupby('tag'):
  meta=w.iloc[0]
  ep=eq[eq.tag.eq(tag)].sort_values('t').set_index('t').reindex(fullgrid).ffill()
  assert ep.equity.notna().all()
  qmap={};imap={};emap={};reval=np.zeros(len(fullgrid))
  for coin,cg in w.groupby('coin'):
   if coin.startswith('@'):continue
   if coin not in COINS:raise ValueError('Unmapped perpetual '+coin)
   cg=cg.sort_values('t').set_index('t').reindex(fullgrid).ffill()
   q=cg.signed_size.to_numpy(float);pi=cg.px.to_numpy(float);pe=prices[coin].reindex(fullgrid).to_numpy(float)
   nonzero=q!=0
   assert np.isfinite(q).all() and np.isfinite(pi[nonzero]).all() and np.isfinite(pe).all()
   correction=np.zeros(len(q));correction[nonzero]=q[nonzero]*(pe[nonzero]-pi[nonzero]);reval+=correction
   qmap[coin]=q;imap[coin]=pi;emap[coin]=pe
   for policy,t in [('input_grid_terminal',base_end),('last_completed_bar_terminal',external_end)]:
    ix=int(np.searchsorted(fullgrid,t));price_rows.append(dict(tag=tag,coin=coin,terminal_policy=policy,t=t,internal_px=pi[ix],external_px=pe[ix],difference=pe[ix]-pi[ix],actual_q=q[ix]))
  for h in (12,24,48):
   t0=lo+h*3600000;i0=int(np.searchsorted(fullgrid,t0));assert fullgrid[i0]==t0
   e0=float(ep.equity.iloc[i0]);e0ext=e0+reval[i0]
   frozen_i=np.full(len(fullgrid)-i0,e0);frozen_e=np.full(len(fullgrid)-i0,e0ext)
   gross_i=np.zeros(len(frozen_i));gross_e=np.zeros(len(frozen_i));nheld=0
   for coin,q in qmap.items():
    q0=float(q[i0]);position_rows.append(dict(tag=tag,model=meta.model,formation_hours=h,coin=coin,freeze_t=t0,quantity=q0,internal_freeze_px=imap[coin][i0],external_freeze_px=emap[coin][i0]))
    if q0==0:continue # essential: zero positions never multiply NaN marks
    nheld+=1;pi=imap[coin][i0:];pe=emap[coin][i0:]
    if not np.isfinite(pi).all() or not np.isfinite(pe).all():raise ValueError('Nonfinite nonzero frozen valuation')
    frozen_i+=q0*(pi-pi[0]);frozen_e+=q0*(pe-pe[0]);gross_i+=abs(q0*pi);gross_e+=abs(q0*pe)
   for policy,t in [('input_grid_terminal',base_end),('last_completed_bar_terminal',external_end)]:
    ix=int(np.searchsorted(fullgrid,t));j=ix-i0
    actual_i=float(ep.equity.iloc[ix]-CAPITAL);actual_e=actual_i+reval[ix]
    hold_i=float(frozen_i[j]-CAPITAL);hold_e=float(frozen_e[j]-CAPITAL)
    # Coherent revaluation cancels the freeze-price basis from the terminal difference.
    predicted_hold_shift=sum(q[i0]*(emap[c][ix]-imap[c][ix]) for c,q in qmap.items() if q[i0]!=0)
    endpoint_identity_max_error=max(endpoint_identity_max_error,abs((hold_e-hold_i)-predicted_hold_shift))
    if policy=='input_grid_terminal' and refs:
     max_ref_error=max(max_ref_error,abs(hold_i-float(refs[h].loc[tag,'hold_net'])))
    row=dict(tag=tag,model=meta.model,formation_hours=h,freeze_t=t0,terminal_policy=policy,terminal_t=t,instruments_held=nheld,actual_internal_net=actual_i,actual_external_net=actual_e,frozen_internal_net=hold_i,frozen_external_net=hold_e,internal_advantage=hold_i-actual_i,external_advantage=hold_e-actual_e,freeze_equity_internal=e0,freeze_equity_external=e0ext,actual_mark_shift=reval[ix],frozen_mark_shift=hold_e-hold_i,realised_at_freeze=float(ep.realised.iloc[i0]),fees_at_freeze=float(ep.fees.iloc[i0]),funding_at_freeze=float(ep.funding.iloc[i0]),realised_at_terminal=float(ep.realised.iloc[ix]),fees_at_terminal=float(ep.fees.iloc[ix]),funding_at_terminal=float(ep.funding.iloc[ix]))
    for label,fp,gp in [('internal',frozen_i,gross_i),('external',frozen_e,gross_e)]:
     ratio=np.divide(fp[:j+1],gp[:j+1],out=np.full(j+1,np.nan),where=gp[:j+1]>0)
     row[label+'_min_margin_ratio']=float(np.nanmin(ratio)) if np.isfinite(ratio).any() else None
     for mmr in (.01,.025,.05):
      bad=np.flatnonzero(fp[:j+1]<mmr*gp[:j+1]);suffix=str(mmr)
      row[label+'_breach_'+suffix]=bool(len(bad));row[label+'_breach_t_'+suffix]=int(fullgrid[i0+bad[0]]) if len(bad) else None
    rows.append(row)
   for j,t in enumerate(fullgrid[i0:]):path_rows.append(dict(tag=tag,formation_hours=h,t=int(t),actual_internal_equity=float(ep.equity.iloc[i0+j]),actual_external_equity=float(ep.equity.iloc[i0+j]+reval[i0+j]),frozen_internal_equity=float(frozen_i[j]),frozen_external_equity=float(frozen_e[j]),frozen_internal_gross=float(gross_i[j]),frozen_external_gross=float(gross_e[j])))
 assert max_ref_error<1e-6 and endpoint_identity_max_error<1e-6
 d=pd.DataFrame(rows);summaries=[]
 for (policy,h),g in d.groupby(['terminal_policy','formation_hours']):
  n=len(g);assert n==6
  s=dict(terminal_policy=policy,formation_hours=int(h),n_accounts=n,initial_capital=n*CAPITAL,terminal_t=int(g.terminal_t.iloc[0]),terminal_utc=utc(g.terminal_t.iloc[0]))
  for mark in ['internal','external']:
   actual=float(g['actual_'+mark+'_net'].sum());hold=float(g['frozen_'+mark+'_net'].sum())
   s.update({mark+'_actual_net':actual,mark+'_actual_return_pct':100*actual/(n*CAPITAL),mark+'_frozen_net':hold,mark+'_frozen_return_pct':100*hold/(n*CAPITAL),mark+'_advantage_pp':100*(hold-actual)/(n*CAPITAL),mark+'_accounts_ahead':int((g['frozen_'+mark+'_net']>g['actual_'+mark+'_net']).sum())})
   for mmr in (.01,.025,.05):s[mark+'_breaches_'+str(mmr)]=int(g[mark+'_breach_'+str(mmr)].sum())
  s['advantage_change_pp']=s['external_advantage_pp']-s['internal_advantage_pp'];summaries.append(s)
 spot=fills[fills.coin.str.startswith('@')].copy();spot['ending_position_from_reported_start']=spot.start_position+spot.signed_sz;spot['gross_conversion_value']=spot.sz*spot.px
 metadata=dict(input_root=str(args.root),external_prices=str(args.prices.resolve()),window_start_utc=utc(lo),official_freeze_utc=utc(hi),input_grid_terminal_utc=utc(base_end),last_completed_bar_terminal_utc=utc(external_end),ledger_label=args.ledger_label,cash_ledger='Both mark policies keep the input equity.parquet realised P&L, fees, funding and initial capital unchanged; only open-position MTM is revalued. No transfer/tip is added. Frozen book inherits its policy-consistent actual equity at freeze, then q0*(P_t-P_0); no postfreeze funding or fees and no terminal liquidation.',mark_alignment='External px is previous completed 5m Binance spot USDT close available at grid timestamp t; both actual and frozen books revalued, including freeze equity.',price_interpretation='Independent-venue spot sensitivity, not an exact Hyperliquid oracle/mark or executable quote.',spot_treatment='Exclude @ spot pairs from perpetual revaluation and margin. Existing cash/fee/funding ledger unchanged. @156 dust conversion has nonzero reported starting asset balance and ends at zero; never treat cumsum of its sell as a new perpetual short.',spot_records=spot.to_dict('records'),reference_max_abs_error=max_ref_error,coherent_endpoint_revaluation_identity_max_abs_error=endpoint_identity_max_error,reference_benchmark_script=str(args.reference_benchmark_script.resolve()) if args.reference_benchmark_script else None,limitations=['Price-only sensitivity inherits all input ledger errors or corrections; it does not repair funding timing.','Observed mark differences combine venue and spot/perpetual differences, pooled-fill staleness and completed-bar availability delay; they are not a pure basis estimate.','No post-freeze frozen-book funding, execution costs, terminal liquidation or exact venue liquidation simulation.','Maintenance-margin ratios are hypothetical common-rate screens using proxy prices, not venue account feasibility.','The extended terminal carries the last recorded positions/cash with no fills/funding events between the input terminal and the added mark.','Six wallets are not independent strategy replicates; no inferential p-values are produced.','Raw Binance and normalized prices remain separate licensed research inputs; do not redistribute them by copying this output folder.'],sources=[dict(path=str(p.resolve()),sha256=sha(p)) for p in [der/'panel.parquet',der/'equity.parquet',der/'fills.parquet',der/'funding.parquet',args.prices]])
 d.to_csv(args.out/'s1_binance_accounts.csv',index=False);pd.DataFrame(summaries).to_csv(args.out/'s1_binance_summary.csv',index=False);pd.DataFrame(position_rows).to_csv(args.out/'s1_binance_freeze_positions.csv',index=False);pd.DataFrame(price_rows).to_csv(args.out/'s1_binance_terminal_marks.csv',index=False);pd.DataFrame(path_rows).to_parquet(args.out/'s1_binance_equity_paths.parquet',index=False)
 (args.out/'s1_binance_sensitivity.json').write_text(json.dumps(clean(dict(metadata=metadata,summary=summaries)),indent=2,allow_nan=False)+'\n')
 print(pd.DataFrame(summaries).to_string(index=False));print(json.dumps(clean({'reference_max_abs_error':max_ref_error,'revaluation_identity_error':endpoint_identity_max_error,'spot_records':metadata['spot_records']})))
if __name__=='__main__':main()
