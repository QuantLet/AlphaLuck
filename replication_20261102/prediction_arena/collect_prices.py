from collect_valuations import *
import zipfile,io

def scan_prices(spec):
    label,cutoff,targets,month=spec
    file=next(f for f in json.loads((OLD/'order_filled_files.json').read_text()) if f['type']=='file' and f'year=2026/month={month}.' in f['path'])
    pf,stream=open_parquet(file['path'],file['size']);dest=RAW/('prices_'+label);dest.mkdir(exist_ok=True)
    vals=pa.array(sorted(targets));allrows=[];covered=[]
    for g in range(pf.num_row_groups):
        meta=pf.metadata.row_group(g);st=meta.column(pf.schema.names.index('timestamp')).statistics
        if st and st.has_min_max and (int(st.min)>=cutoff or int(st.max)<cutoff-86400):continue
        covered.append(g);out=dest/f'{g:05d}.json'
        if out.exists():allrows.extend(json.loads(out.read_text()));continue
        table=pf.read_row_group(g,columns=['makerAssetId','takerAssetId','timestamp'])
        ts=pc.cast(table['timestamp'],pa.int64())
        mask=pc.and_(pc.or_(pc.is_in(table['makerAssetId'],value_set=vals),pc.is_in(table['takerAssetId'],value_set=vals)),pc.and_(pc.less(ts,cutoff),pc.greater_equal(ts,cutoff-86400)))
        rows=[]
        if pc.any(mask).as_py():
            stream.prefetch_group(meta);rows=pf.read_row_group(g).filter(mask).to_pylist()
        out.write_text(json.dumps(rows));allrows.extend(rows)
        print(label,'group',g,'hits',len(rows),'MB',round(stream.bytes_read/1e6,1),flush=True)
    (dest/'coverage.json').write_text(json.dumps({'file':file['path'],'revision':REVISION,'cutoff_exclusive':cutoff,'lookback_seconds':86400,'row_groups_scanned':covered,'target_tokens':sorted(targets),'events':len(allrows)},indent=2))
    (RAW/(label+'_price_events.json')).write_text(json.dumps(allrows))
    print('PRICE COMPLETE',label,len(allrows),flush=True)

def gas_archive(month):
    url=f'https://data.binance.vision/data/spot/monthly/klines/POLUSDC/1m/POLUSDC-1m-2026-{month}.zip'
    file=RAW/f'POLUSDC-1m-2026-{month}.zip'
    if not file.exists():
        with urllib.request.urlopen(url,context=ssl.create_default_context(),timeout=60) as r:file.write_bytes(r.read())
    with zipfile.ZipFile(file) as z:assert z.testzip() is None
    (file.with_suffix('.source.json')).write_text(json.dumps({'url':url,'quote':'USDC; dollar interpretation assumes USDC parity','timestamps':'microseconds UTC from 2025 onward'}))
    print('GAS COMPLETE',month,file.stat().st_size,flush=True)

if __name__=='__main__':
    specs=[('formation',FREEZE,{t for p in POS for t in p['formation_positions_raw']},'02'),('endpoint',END,TOKENS,'03')]
    with cf.ThreadPoolExecutor(4) as pool:
        jobs=[pool.submit(scan_prices,s) for s in specs]+[pool.submit(gas_archive,m) for m in ['02','03']]
        for j in jobs:j.result()
