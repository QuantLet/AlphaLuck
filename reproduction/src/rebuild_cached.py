"""Offline rebuild from cached normalized fills/funding, not from raw API files.

This route is explicit because cloud placeholders may make the raw cache
unavailable. It rebuilds roundtrips, marks, positions and equity using exactly
build.py's production functions; it does not certify raw ingestion or refresh
organiser reconciliation. The input hashes identify the cached starting point.
"""
from pathlib import Path
import hashlib,json
import pandas as pd
import build

ROOT=Path(__file__).resolve().parents[1]
DER=ROOT/'data/derived'
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    inputs={n:sha(DER/(n+'.parquet')) for n in ['fills','funding']}
    fills=pd.read_parquet(DER/'fills.parquet')
    funding=pd.read_parquet(DER/'funding.parquet')
    old=pd.read_parquet(DER/'equity.parquet')
    print('Rebuilding from normalized cached inputs:',inputs,flush=True)
    trips=build.round_trips(fills)
    panel,_=build.panel(fills)
    equity=build.equity(fills,funding,panel)
    matched=old[['tag','t','equity']].merge(equity[['tag','t','equity']],on=['tag','t'],suffixes=('_old','_new'))
    diff=matched.equity_new-matched.equity_old
    report={'mode':'normalized-cache; raw ingestion not rerun','input_sha256':inputs,
            'fills':len(fills),'funding':len(funding),'roundtrips':len(trips),
            'panel_rows':len(panel),'equity_rows':len(equity),'comparison_rows':len(matched),
            'max_abs_equity_change_usd':float(diff.abs().max()),
            'equity_rows_changed_gt_1e_8':int((diff.abs()>1e-8).sum())}
    for name,frame in [('roundtrips',trips),('panel',panel),('equity',equity)]:
        frame.to_parquet(DER/(name+'.parquet'),index=False)
    (DER/'cached_rebuild.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':main()
