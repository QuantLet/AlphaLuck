"""Refresh comparison against cached published targets without raw organiser I/O.

The cache retains every prior-grid timestamp consistent with the previously
reported reconstructed equity. Refresh is permitted only when all candidates
map to the same new equity. This recovers the comparison value, not the exact
published timestamp, and does not claim new organiser data were fetched.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
DER=ROOT/'data/derived'
REFERENCE=ROOT/'data/external/reconciliation/cached_reference.json'

def main():
    ref=json.loads(REFERENCE.read_text());eq=pd.read_parquet(DER/'equity.parquet')
    out=[];evidence=[]
    for item in ref['accounts']:
        row=item['cached_comparison'].copy()
        candidates=item['candidate_grid_ms']
        matches=eq[(eq.tag==row['tag'])&eq.t.isin(candidates)].sort_values('t')
        if len(matches)!=len(candidates) or not np.isfinite(matches.equity).all():
            raise ValueError('Missing or nonfinite comparison candidates: '+row['tag'])
        spread=float(matches.equity.max()-matches.equity.min())
        if spread>1e-8:
            raise ValueError('Cached comparison timestamp ambiguous after rebuild: '+row['tag'])
        equity=float(matches.equity.iloc[-1]);plus=equity+row['tips']
        diff=plus-row['pub_equity'];pct=100*diff/row['pub_equity']
        row.update(recon_equity=equity,recon_plus_tips=plus,diff=diff,diff_pct=pct,
                   status='RECONCILED' if abs(pct)<=5 else 'UNVERIFIED')
        out.append(row);evidence.append({'tag':row['tag'],'n_candidate_grid_points':len(candidates),
                                        'new_candidate_equity_range_usd':spread})
    pd.DataFrame(out).to_parquet(DER/'recon.parquet',index=False)
    report={'method':__doc__,'reference':str(REFERENCE.relative_to(ROOT)),
            'reference_input_sha256':ref['source_sha256'],'accounts':evidence,
            'max_abs_relative_pct':max(abs(r['diff_pct']) for r in out),
            'median_abs_relative_pct':float(np.median([abs(r['diff_pct']) for r in out]))}
    (DER/'cached_reconciliation.json').write_text(json.dumps(report,indent=2))
    print('Refreshed cached comparisons:',len(out),'; maximum absolute gap',report['max_abs_relative_pct'],
          '; median',report['median_abs_relative_pct'])

if __name__=='__main__':main()
