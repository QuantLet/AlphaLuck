"""Reproduce the additional checks from the archived account-level inputs.
Run python replay_checks.py from this directory. Only Python standard library.
Formation notionals are derived from reconstructed fills and pooled prices;
rebuilding those inputs from the full project uses analyse_revision.py.
"""
from pathlib import Path
import csv,itertools,json,math
B=Path(__file__).resolve().parent
rows=list(csv.DictReader((B/'account_inputs_and_gaps.csv').open()))
cols=['cash','isolated_A','isolated_B','shared']
for r in rows:
 for k in cols+['formation_gross_notional','inherited_pnl','actual_pnl']:r[k]=float(r[k])
 r['arm']=int(r['arm'])
 assert math.isclose(r['cash'],(r['inherited_pnl']-r['actual_pnl'])/100,abs_tol=1e-10)
assert len(rows)==32 and len({r['tag'] for r in rows})==32
models=sorted({r['model'] for r in rows});assert len(models)==8
assert all(sum(r['model']==m for r in rows)==4 for m in models)
expected=json.loads((B/'summary.json').read_text())
for e in expected['arm_deletions']:
 rr=[r for r in rows if r['arm']!=e['omitted_arm']];assert len(rr)==e['accounts']
 for k in cols:
  assert math.isclose(sum(r[k] for r in rr)/len(rr),e[k+'_gap_pp'],abs_tol=1e-10)
  assert sum(r[k]>0 for r in rr)==e[k+'_ahead']
for e in expected['model_reference']:
 k=e['benchmark'];v=[sum(r[k] for r in rows if r['model']==m)/4 for m in models];obs=abs(sum(v)/8)
 vals=[abs(sum(a*b for a,b in zip(s,v))/8) for s in itertools.product([-1,1],repeat=8)]
 assert sum(z>=obs-1e-12 for z in vals)/256==e['two_sided_sign_flip_reference']
 assert sum(z>0 for z in v)==e['models_ahead']
for e in expected['cash_closure']:
 gaps=[r['cash']-r['formation_gross_notional']*e['closure_cost_bp']/1000000 for r in rows]
 assert math.isclose(sum(gaps)/32,e['cash_gap_pp'],abs_tol=1e-10)
 assert sum(g>0 for g in gaps)==e['accounts_ahead']
result={'passed':True,'accounts':32,'model_blocks':8,'arm_deletion_scenarios':5,'sign_assignments_per_benchmark':256,'cash_cost_scenarios':4,'inference_limitation':expected['assumptions']}
(B/'replay_validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
