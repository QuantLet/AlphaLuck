"""Refresh collaborator tables from the corrected sweep, retaining their prose."""
from pathlib import Path
import json,re
import numpy as np
import pandas as pd
import organiser_hourly as oh

ROOT=Path(__file__).resolve().parents[1]
DER=ROOT/'data/derived';FRL=ROOT/'paper/frl'

def main():
    m=oh.Market(ROOT);t0=m.lo+24*oh.fh.HOUR
    a=pd.read_csv(DER/'holding_vs_trading_accounts.csv').set_index('tag')
    formed=a.hold_net-a.hold_mtm-a.funding_hold
    sw=pd.read_csv(DER/'organiser_hourly_sweep_accounts.csv')
    f=sw[sw.formation_hour.eq(24)].set_index('tag').reindex(a.index)
    ir=float(m.price('xyz:XYZ100',np.array([m.hi]))[0]/m.price('xyz:XYZ100',np.array([t0]))[0]-1)
    paths={'Realised trading':a.actual_net,'Frozen, isolated A':f.isolated_net_A,'Frozen, isolated B':f.isolated_net_B,
           'Frozen, shared collateral':a.hold_net,'Cash from formation':formed,'Index price reference':formed+(10000+formed)*ir}
    values=[]
    for name,v in paths.items():
        values.append({'path':name,'total':float(v.mean()/100),'post':float((v-formed).mean()/100),
                       'gap':float((v-a.actual_net).mean()/100),'ahead':int((v>a.actual_net).sum())})
    for file,gap in [('feedback_main_comparison.tex',True),('feedback_benchmarks.tex',False)]:
        text=(FRL/file).read_text()
        for r in values:
            nums=[f"{r['total']:.2f}",f"{r['post']:.2f}"]
            if gap:nums.append(f"{r['gap']:.2f}")
            nums.append('--' if gap and r['path']=='Realised trading' else str(r['ahead']))
            row=r['path']+' & '+' & '.join(nums)+r' \\'
            text,n=re.subn(re.escape(r['path'])+r' & [^\n]*',lambda _:row,text)
            assert n==1
        (FRL/file).write_text(text)
    org=json.loads((DER/'organiser_hourly.json').read_text())
    macros=(FRL/'feedback_numbers.tex').read_text()
    for direction,label in [('Early','earlier'),('Late','later')]:
        row=next(x for x in org['liquidation_stress']['at_24h'] if x['scenario']==f'joint, {label} trigger')
        for c in 'AB':
            data={'Return':row['actual_return_pct']+row[f'advantage_pp_{c}'],
                  'Gap':row[f'advantage_pp_{c}'],'Ahead':row[f'accounts_ahead_{c}']}
            for suffix,val in data.items():
                name=f'alFeedback{direction}{c}{suffix}';value=str(val) if suffix=='Ahead' else f'{val:.2f}'
                macros,n=re.subn(r'\\newcommand\{\\'+name+r'\}\{[^\n]+\}',lambda _: '\\newcommand{\\'+name+'}{'+value+'}',macros)
                assert n==1,name
    (FRL/'feedback_numbers.tex').write_text(macros)
    (DER/'final_revision_benchmarks.json').write_text(json.dumps(values,indent=2))
    print(json.dumps(values,indent=2))

if __name__=='__main__':main()
