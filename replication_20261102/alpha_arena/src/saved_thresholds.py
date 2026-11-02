"""Replay from derived formation thresholds, without raw organiser snapshots."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import organiser_hourly as oh

class SavedThresholdSweep(oh.Sweep):
    def __init__(self,m,records,rates,threshold_policy='nearest',align_funding=True):
        empty=pd.DataFrame(columns=['tag','coin','t','q_org','liquidation_price'])
        super().__init__(m,empty,rates,threshold_policy,align_funding)
        self.saved={(r['formation_hour'],r['tag'],r['coin']):r for r in records}

    def threshold(self,tag,coin,q0,t0):
        hour=int((t0-self.m.lo)/oh.fh.HOUR)
        row=self.saved[(hour,tag,coin)]
        if abs(row['quantity']-q0)>oh.EPS:raise ValueError('Saved threshold quantity differs')
        value=row[self.threshold_policy]
        if value is None:return None
        timestamp=t0+value['offset_minutes']*60000
        L=value['funding_aligned_threshold']
        if not self.align_funding:
            # Funding events are on exact hours; rounding offsets back to the
            # nearest millisecond recovers the underlying event convention.
            timestamp=round(timestamp)
            between=(self.m.hours>min(timestamp,t0))&(self.m.hours<=max(timestamp,t0))
            paid=-q0*self.m.unit[coin][between].sum()*np.sign(t0-timestamp)
            L-=paid/(q0-self.rates[coin]*abs(q0))
        return timestamp,L

def export(root):
    root=Path(root);der=root/'data/derived';m=oh.Market(root)
    cells=pd.read_csv(der/'organiser_hourly/position_cells.csv')
    rates=json.loads((der/'organiser_hourly.json').read_text())['maintenance_rates']
    sweeps={p:oh.Sweep(m,cells,rates,threshold_policy=p) for p in ['nearest','prior']}
    rows=[]
    for hour in range(1,int((m.hi-m.lo)//oh.fh.HOUR)):
        t0=m.lo+hour*oh.fh.HOUR;i=np.searchsorted(sweeps['nearest'].grid,t0)
        for (tag,coin),quantity in sweeps['nearest'].q.items():
            q=quantity[i]
            if q==0:continue
            row={'formation_hour':hour,'tag':tag,'coin':coin,'quantity':float(q)}
            for policy,sweep in sweeps.items():
                result=sweep.threshold(tag,coin,q,t0)
                row[policy]=None if result is None else {'offset_minutes':float((result[0]-t0)/60000),'funding_aligned_threshold':float(result[1])}
            rows.append(row)
    (der/'formation_threshold_inputs.json').write_text(json.dumps(rows,allow_nan=False))
    print('Derived formation thresholds:',len(rows))

if __name__=='__main__':export(Path(__file__).resolve().parents[1])
