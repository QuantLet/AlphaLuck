"""Offline model-block sign-flip references and arm-deletion checks.
Run: python analyse_revision.py --root PROJECT --out OUTPUT
No inference over independent market paths is possible from this season.
"""
from pathlib import Path
import argparse,itertools,json,hashlib,sys
import numpy as np
import pandas as pd
ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
der=a.root/'data/derived'
d=pd.read_csv(der/'holding_vs_trading_accounts.csv').set_index('tag')
f=pd.read_csv(der/'organiser_hourly_sweep_accounts.csv');f=f[f.formation_hour.eq(24)].set_index('tag').reindex(d.index)
assert len(d)==32 and d.groupby('model').size().eq(4).all() and d.groupby('arm').size().eq(8).all()
assert np.allclose(d.actual_net,f.actual_net,atol=1e-7)
inherited=d.hold_net-d.hold_mtm-d.funding_hold
q=d[['model','arm']].copy()
q['cash']=(inherited-d.actual_net)/100
q['isolated_A']=(f.isolated_net_A-d.actual_net)/100
q['isolated_B']=(f.isolated_net_B-d.actual_net)/100
q['shared']=(d.hold_net-d.actual_net)/100
cols=['cash','isolated_A','isolated_B','shared']
rows=[]
for omit in [0,1,2,3,4]:
 g=q if omit==0 else q[q.arm.ne(omit)]
 row={'omitted_arm':omit,'accounts':len(g)}
 for col in cols:row[col+'_gap_pp']=float(g[col].mean());row[col+'_ahead']=int(g[col].gt(0).sum())
 rows.append(row)
arm=pd.DataFrame(rows);arm.to_csv(a.out/'leave_one_arm_out.csv',index=False)
means=q.groupby('model')[cols].mean();means.to_csv(a.out/'model_means.csv')
signs=np.array(list(itertools.product([-1,1],repeat=len(means))))
refs=[]
for col in cols:
 x=means[col].to_numpy();obs=abs(x.mean());null=np.abs(signs@x/len(x))
 refs.append({'benchmark':col,'gap_pp':float(x.mean()),'models_ahead':int((x>0).sum()),'two_sided_sign_flip_reference':float(np.mean(null>=obs-1e-12)),'assignments':len(signs)})
 # exact enumeration is invariant to order and global reversal
 assert np.isclose(np.mean(np.abs(signs@x[::-1]/len(x))>=obs-1e-12),refs[-1]['two_sided_sign_flip_reference'])
 assert np.isclose(np.mean(np.abs(signs@(-x)/len(x))>=obs-1e-12),refs[-1]['two_sided_sign_flip_reference'])
pd.DataFrame(refs).to_csv(a.out/'model_sign_flip_reference.csv',index=False)
# Compute formation notional from fills and the same pooled prices as the main analysis.
sys.path.insert(0,str(a.root/'src'))
import organiser_hourly as oh
import funding_hourly_sensitivity as fh
m=oh.Market(a.root);t0=m.lo+24*fh.HOUR
notional={tag:sum(abs(float(m.quantity(tag,coin,np.array([t0]))[0]))*float(m.price(coin,np.array([t0]))[0]) for coin in m.coins) for tag in d.index}
q['formation_gross_notional']=pd.Series(notional)
q['inherited_pnl']=inherited
q['actual_pnl']=d.actual_net
q.to_csv(a.out/'account_inputs_and_gaps.csv')
cost=[]
for bp in [0,2.42,10,100]:
 gaps=q.cash-q.formation_gross_notional*bp/10000/100
 cost.append({'closure_cost_bp':bp,'cash_gap_pp':float(gaps.mean()),'accounts_ahead':int(gaps.gt(0).sum())})
pd.DataFrame(cost).to_csv(a.out/'cash_closure_sensitivity.csv',index=False)
summary={'units':'percentage points of retained accounts initial capital; each account starts with USD 10000', 'model_reference':refs,'arm_deletions':rows,'cash_closure':cost,'formation_gross_times_capital':float(q.formation_gross_notional.sum()/320000),'aggregate_cash_breakeven_closure_bp':float(q.cash.sum()*100/q.formation_gross_notional.sum()*10000),'assumptions':'Sign-flip reference assumes the joint null distribution is invariant to independent sign reversals of the eight model means, preserving the four arms within a model. Common market shocks may violate this assumption. References are conditional diagnostics, not calibrated significance levels for repeated markets, causal effects, or the overlapping formation windows.'}
(a.out/'summary.json').write_text(json.dumps(summary,indent=2))
(a.out/'input_hashes.json').write_text(json.dumps({n:hashlib.sha256((der/n).read_bytes()).hexdigest() for n in ['holding_vs_trading_accounts.csv','organiser_hourly_sweep_accounts.csv','fills.parquet','panel.parquet','equity.parquet','accounts.parquet','funding.parquet']},indent=2))
print(json.dumps(summary,indent=2))
