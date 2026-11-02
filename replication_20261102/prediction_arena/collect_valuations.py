import sys,json,pathlib,datetime as dt,concurrent.futures as cf,urllib.request,ssl
import pyarrow as pa
import pyarrow.compute as pc
ROOT=pathlib.Path(__file__).resolve().parent
OLD=ROOT/'independent_inputs' if (ROOT/'independent_inputs').exists() else ROOT.parent/'predictionarena_independent_20261101'
sys.path.insert(0,str(OLD))
from range_reader import open_parquet,REVISION
RAW=ROOT/'raw';RAW.mkdir(exist_ok=True)
POS=json.loads((OLD/'results/positions_reconciliation.json').read_text())
TOKENS={t for p in POS for k in ['formation_positions_raw','endpoint_positions_raw'] for t in p[k]}
FREEZE=1770695109.366855
END=1773100800

def conditions():
    out=RAW/'target_conditions.json'
    if out.exists():return json.loads(out.read_text())
    f=next(x for x in json.loads((OLD/'repo_tree.json').read_text()) if x['path']=='condition.parquet')
    pf,stream=open_parquet(f['path'],f['size']);rows=[]
    for g in range(pf.num_row_groups):
        table=pf.read_row_group(g,columns=['id','positionIds'])
        flags=[bool(set(map(str,x))&TOKENS) for x in table['positionIds'].to_pylist()]
        full=pf.read_row_group(g).filter(pa.array(flags));rows.extend(full.to_pylist())
        print('conditions group',g,'matches',len(full),'MB',round(stream.bytes_read/1e6,1),flush=True)
    out.write_text(json.dumps(rows,indent=2));return rows

def scan_redemptions(file,targets):
    pf,stream=open_parquet(file['path'],file['size'])
    dest=RAW/('global_'+file['path'].replace('/','__').replace('.parquet',''));dest.mkdir(exist_ok=True)
    allrows=[]
    for g in range(pf.num_row_groups):
        out=dest/f'{g:05d}.json'
        if out.exists():allrows.extend(json.loads(out.read_text()));continue
        meta=pf.metadata.row_group(g);st=meta.column(pf.schema.names.index('timestamp')).statistics
        if st and st.has_min_max and int(st.min)>=END:out.write_text('[]');continue
        table=pf.read_row_group(g,columns=['condition','timestamp'])
        mask=pc.and_(pc.is_in(table['condition'],value_set=pa.array(sorted(targets))),pc.less(pc.cast(table['timestamp'],pa.int64()),END))
        rows=[]
        if pc.any(mask).as_py():
            stream.prefetch_group(meta);rows=pf.read_row_group(g).filter(mask).to_pylist()
        out.write_text(json.dumps(rows));allrows.extend(rows)
        if g%10==0:print('redemption',file['path'],g,'/',pf.num_row_groups,'hits',len(allrows),flush=True)
    (dest/'coverage.json').write_text(json.dumps({'file':file['path'],'row_groups':pf.num_row_groups,'matched_events':len(allrows),'revision':REVISION}))
    return allrows

if __name__=='__main__':
    cond=conditions();mapped={str(t) for c in cond for t in c['positionIds']}
    print('mapped tokens',len(TOKENS&mapped),'/',len(TOKENS),flush=True)
    targets={c['id'] for c in cond if int(c['payoutDenominator'])>0}
    files=[f for f in json.loads((OLD/'redemption_files.json').read_text()) if f['type']=='file' and ('year=2026/month=02.' in f['path'] or 'year=2026/month=03.' in f['path'])]
    with cf.ThreadPoolExecutor(2) as pool:
        rows=sum(list(pool.map(lambda f:scan_redemptions(f,targets),files)),[])
    (RAW/'global_redemptions.json').write_text(json.dumps(rows,indent=2))
    print('COMPLETE',len(rows),'redemptions',len({x['condition'] for x in rows}),'conditions',flush=True)
