"""Offline reproduction of the corrected sweeps and threshold-timing checks.

Uses derived thresholds; it does not independently re-establish the source
organiser's margin observations. Run from any directory with Python 3 and
numpy, pandas and pyarrow installed. Results go to data/derived/reproduction.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import organiser_hourly as oh
from saved_thresholds import SavedThresholdSweep

def main():
    root=Path(__file__).resolve().parents[1];der=root/'data/derived'
    expected=json.loads((der/'organiser_hourly.json').read_text())
    records=json.loads((der/'formation_threshold_inputs.json').read_text());m=oh.Market(root)
    rates=expected['maintenance_rates'];s=SavedThresholdSweep(m,records,rates)
    rows=[s.run(h)[1] for h in range(1,int((m.hi-m.lo)//oh.fh.HOUR))]
    computed=pd.DataFrame(rows).set_index('formation_hour')
    published=pd.read_csv(der/'organiser_hourly_sweep.csv').set_index('formation_hour')
    keys=['advantage_pp','isolated_A_advantage_pp','isolated_B_advantage_pp','isolated_A_accounts_ahead','isolated_B_accounts_ahead','isolated_positions_unscreened']
    for horizon in oh.HORIZONS:
        keys += [f'isolated_{c}_advantage_pp_{horizon}h' for c in 'AB']
    errors=[]
    for key in keys:
        assert computed[key].isna().equals(published[key].isna()),key
        errors.append(float((computed[key]-published[key]).abs().max()))
    for label,stress in oh.STRESSES:
        r=s.run(24,stress=stress)[1]
        p=next(x for x in expected['liquidation_stress']['at_24h'] if x['scenario']==label)
        for c in 'AB':errors.append(abs(r[f'isolated_{c}_advantage_pp']-p[f'advantage_pp_{c}']))
    published_stress=pd.read_csv(der/'organiser_hourly_stress_sweep.csv').set_index(['trigger','formation_hour'])
    for label,stress in [('earlier',{**oh.HARSH,'buffer':.01}),('later',oh.HARSH)]:
        calculated=pd.DataFrame([s.run(h,stress=stress)[1] for h in range(1,int((m.hi-m.lo)//oh.fh.HOUR))]).set_index('formation_hour')
        for c in 'AB':
            for suffix in ['advantage_pp','advantage_pp_168h','accounts_ahead']:
                key=f'isolated_{c}_{suffix}'
                errors.append(float((calculated[key]-published_stress.loc[label,key]).abs().max()))
    audit=json.loads((der/'formation_timing_audit.json').read_text())
    for p in audit['results']:
        label=p['scenario'];policy='prior' if label.startswith('Prior') else 'nearest'
        replay=SavedThresholdSweep(m,records,rates,policy,align_funding='unaligned' not in label)
        stress=None
        if 'worst observed' in label:stress={'worst_unscreened':True}
        if 'joint earlier' in label:stress={**oh.HARSH,'buffer':.01}
        if 'joint later' in label:stress=oh.HARSH
        r=replay.run(p['formation_hour'],stress=stress)[1]
        for c in 'AB':errors.append(abs(r[f'isolated_{c}_advantage_pp']-p[f'isolated_{c}_advantage_pp']))
        assert r['isolated_positions_unscreened']==p['isolated_positions_unscreened']
    assert max(errors)<1e-8,max(errors)
    dest=der/'reproduction';dest.mkdir(exist_ok=True)
    computed.to_csv(dest/'corrected_sweep.csv')
    result={'formation_hours':len(rows),'threshold_timing_scenarios':len(audit['results']),'maximum_absolute_difference_pp':max(errors),'status':'passed'}
    (dest/'validation.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))

if __name__=='__main__':main()
