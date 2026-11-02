"""Extract independently indexed on-chain events for five known public wallets."""
import concurrent.futures as cf
import datetime as dt
import json,pathlib,ssl,urllib.request
import pyarrow as pa
import pyarrow.compute as pc
from range_reader import ROOT,REVISION,WALLETS,open_parquet

RAW=ROOT/'extracted';RAW.mkdir(exist_ok=True)
START=int(dt.datetime(2026,2,1,tzinfo=dt.timezone.utc).timestamp())
END=int(dt.datetime(2026,3,10,tzinfo=dt.timezone.utc).timestamp())
OWNERS={'order_filled':'maker','fee_refunded':'refundee','redemption':'redeemer','split':'stakeholder','merge':'stakeholder','neg_risk_conversion':'stakeholder','wallet':'id'}
VALUES=pa.array(list(WALLETS.values()))

def files_for(entity):
    if entity=='wallet':
        return [x for x in json.loads((ROOT/'repo_tree.json').read_text()) if x['path']=='wallet.parquet']
    dest=ROOT/(entity+'_files.json')
    if dest.exists():rows=json.loads(dest.read_text())
    else:
        url=f'https://huggingface.co/api/datasets/moose-code/polymarket-onchain-v1/tree/{REVISION}/{entity}?recursive=true&limit=1000'
        with urllib.request.urlopen(url,context=ssl.create_default_context(),timeout=60) as r:rows=json.loads(r.read())
        dest.write_text(json.dumps(rows,indent=2))
    return [x for x in rows if x['type']=='file' and ('year=2026/month=02.' in x['path'] or 'year=2026/month=03.' in x['path'])]

def scan_file(entity,file):
    pf,stream=open_parquet(file['path'],file['size'])
    dest=RAW/(file['path'].replace('/','__').replace('.parquet',''));dest.mkdir(exist_ok=True)
    pf.metadata.write_metadata_file(dest/'metadata.parquet')
    names=pf.schema_arrow.names;owner=OWNERS[entity]
    if owner not in names:raise ValueError((entity,names,owner))
    print('START',file['path'],'groups',pf.num_row_groups,'rows',pf.metadata.num_rows,'columns',names,flush=True)
    for g in range(pf.num_row_groups):
        outfile=dest/f'{g:05d}.json'
        if outfile.exists():continue
        meta=pf.metadata.row_group(g)
        if 'timestamp' in names:
            st=meta.column(pf.schema.names.index('timestamp')).statistics
            if st and st.has_min_max and (int(st.max)<START or int(st.min)>=END):
                outfile.write_text(json.dumps({'group':g,'skipped':'outside_time_window','rows':[]}));continue
        byte_start=stream.bytes_read
        owners=pf.read_row_group(g,columns=[owner])
        mask=pc.is_in(pc.utf8_lower(owners[owner]),value_set=VALUES)
        hits=pc.sum(pc.cast(mask,pa.int64())).as_py()
        rows=[]
        if hits:
            stream.prefetch_group(meta)
            table=pf.read_row_group(g)
            table=table.filter(mask)
            if 'timestamp' in names:
                ts=pc.cast(table['timestamp'],pa.int64());table=table.filter(pc.and_(pc.greater_equal(ts,START),pc.less(ts,END)))
            rows=table.to_pylist()
        outfile.write_text(json.dumps({'group':g,'group_rows':meta.num_rows,'owner_matches_before_time_filter':hits,
          'bytes_read':stream.bytes_read-byte_start,'rows':rows},indent=2))
        if rows or g%20==0:print(entity,file['path'].split('/')[-1],g,'hits',len(rows),'MB',round(stream.bytes_read/1e6,1),flush=True)
    manifests=[json.loads(f.read_text()) for f in sorted(dest.glob('*.json')) if f.name!='manifest.json']
    (dest/'manifest.json').write_text(json.dumps({'path':file['path'],'file_size':file['size'],'revision':REVISION,'owner_column':owner,
      'all_row_groups':pf.num_row_groups,'recorded_row_groups':len(manifests),'rows_extracted':sum(len(x['rows']) for x in manifests),
      'row_groups_with_matches':sum(bool(x['rows']) for x in manifests),'range_bytes_read_this_run':stream.bytes_read,
      'period_start':START,'period_end_exclusive':END},indent=2))
    return entity,sum(len(x['rows']) for x in manifests)

if __name__=='__main__':
    import sys
    entities=sys.argv[1:] or list(OWNERS)
    tasks=[(entity,f) for entity in entities for f in files_for(entity)]
    with cf.ThreadPoolExecutor(3) as pool:
        for result in pool.map(lambda args:scan_file(*args),tasks):print('COMPLETE',result,flush=True)
