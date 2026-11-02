"""Recover immutable outcome-token mappings for audited redemption conditions."""
import json
import pyarrow as pa
import pyarrow.compute as pc
from range_reader import ROOT,open_parquet

targets={r['condition'].lower() for r in json.loads((ROOT/'results/redemptions_crosschecked.json').read_text())}
f=next(x for x in json.loads((ROOT/'repo_tree.json').read_text()) if x['path']=='condition.parquet')
pf,stream=open_parquet(f['path'],f['size'])
print('condition',pf.schema_arrow.names,pf.num_row_groups,flush=True)
rows=[]
for g in range(pf.num_row_groups):
    ids=pf.read_row_group(g,columns=['id']);mask=pc.is_in(pc.utf8_lower(ids['id']),value_set=pa.array(sorted(targets)))
    if pc.any(mask).as_py():
        table=pf.read_row_group(g);rows.extend(table.filter(mask).to_pylist())
(ROOT/'condition_mappings.json').write_text(json.dumps({'note':'State at archive snapshot; position IDs immutable. Payout values alone do not establish resolution before study endpoint.','targets':len(targets),'matched':len(rows),'rows':rows},indent=2))
print('found',len(rows),'of',len(targets),flush=True)
