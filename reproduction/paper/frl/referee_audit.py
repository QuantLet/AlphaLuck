from pathlib import Path
import sys,json,itertools
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent.parent
sys.path.insert(0,str(ROOT/'src'))
import analyse,vol_fixed_denominator as vf,sharpe_horizon as sh
D=ROOT/'data/derived'
def main():
 eq=pd.read_parquet(D/'equity.parquet');fills=pd.read_parquet(D/'fills.parquet')
 lo,hi=analyse.common_window(fills,'S15')
 e=eq.loc[eq.season.eq('S15') & eq.t.between(lo,hi)].copy();e['day']=e.t//86400000
 ends=e.sort_values('t').groupby(['tag','day']).equity.last().unstack()
 pnl=ends.diff(axis=1).iloc[:,1:]/10000
 meta=e.groupby('tag')[['model','competition_id']].first()
 def matrix(v):return meta.join(v.rename('v')).pivot(index='model',columns='competition_id',values='v').to_numpy()
 full=matrix(pnl.std(axis=1,ddof=1))
 def stats(y):return dict(F=vf.anova_icc(y)['F_model'],W=vf.kendall_w(y)['W'])
 arm=[dict(omitted_arm=a+1,**stats(np.delete(full,a,axis=1))) for a in range(4)]
 day=[dict(omitted_day=int(c),**stats(matrix(pnl.drop(columns=c).std(axis=1,ddof=1)))) for c in pnl]
 equal=ends.pct_change(axis=1).iloc[:,1:].join(meta.model).groupby('model').mean().T
 def horizon(x):
  vals=[sh.Z2*sh.lw_variance(x[a].to_numpy(),x[b].to_numpy(),1) for a,b in itertools.combinations(x.columns,2)]
  return dict(median=float(np.median(vals)),q1=float(np.quantile(vals,.25)),q3=float(np.quantile(vals,.75)))
 rec=pd.read_parquet(D/'recon.parquet');rows=[]
 for x in rec.sort_values(['season','competition_id','model']).itertuples():
  row=[x.season,str(int(x.competition_id)),x.model.replace('_',r'\_'),f'{x.pub_equity:.2f}',f'{x.recon_plus_tips:.2f}',f'{x.diff:+.2f}',f'{x.diff_pct:+.3f}']
  rows.append(' & '.join(row)+r' \\')
 head='\\begin{longtable}{rrlrrrr}\n\\caption{Selected-snapshot reconciliation. Dollar gaps include recorded tips; percentages divide by published equity.}\\label{tab:reconciliation}\\\\\n\\toprule Season & Arm & Model & Published & Rebuilt & Gap (USD) & Gap (\\%)\\\\\n\\midrule\\endfirsthead\n\\toprule Season & Arm & Model & Published & Rebuilt & Gap (USD) & Gap (\\%)\\\\\\midrule\\endhead\n'
 (HERE/'audit_reconciliation.tex').write_text(head+'\n'.join(rows)+'\n'+r'\bottomrule\end{longtable}')
 ages=[]
 for season in ('S1','S15'):
  l,h=analyse.common_window(fills,season);f=fills.loc[fills.season.eq(season)]
  for label,t in [('freeze_24h',l+86400000),('close',h)]:
   last=f.loc[f.time.le(t)].groupby('coin').time.max();age=(t-last)/60000
   ages.append(dict(season=season,point=label,n_instruments=len(last),median_minutes=float(age.median()),max_minutes=float(age.max())))
 periods=[dict(day=int(c),first_mark=str(pd.to_datetime(e.loc[e.day.eq(c),'t'].min(),unit='ms',utc=True)),last_mark=str(pd.to_datetime(e.loc[e.day.eq(c),'t'].max(),unit='ms',utc=True))) for c in ends.columns]
 out=dict(leave_one_arm=arm,leave_one_return_day=day,hac1_aggregate=horizon(sh.daily_model_returns()),hac1_equal_daily=horizon(equal),price_ages=ages,daily_mark_intervals=periods)
 (HERE/'referee_audit.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
if __name__=='__main__':main()
