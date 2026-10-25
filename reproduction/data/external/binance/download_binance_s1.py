"""Optional licensed market-data acquisition; stdlib only; never part of make checks.

Run with --output-dir outside any release tree if desired. The default output
PROJECT/data/raw/binance is gitignored. No explicit click-through acceptance,
credentials, trading actions or paid endpoints are used. Review current dataset
terms before running; stored acquisition metadata is not a licence grant.
"""
from pathlib import Path
import concurrent.futures,csv,datetime,hashlib,io,json,time,urllib.request,urllib.error,zipfile
ROOT = None  # Set only by the command-line entry point; imports perform no I/O.
def iso(ms): return datetime.datetime.fromtimestamp(ms/1000,datetime.timezone.utc).isoformat()
def ms(d): return int(datetime.datetime.fromisoformat(d).replace(tzinfo=datetime.timezone.utc).timestamp()*1000)
def request(url,save,payload=None,cap=5000000):
 sidecar=save.with_name(save.name+'.meta.json')
 if save.exists():
  b=save.read_bytes()
  meta=json.loads(sidecar.read_text()) if sidecar.exists() else {'url':url,'request_payload':payload,'fetched_at_utc':datetime.datetime.fromtimestamp(save.stat().st_mtime,datetime.timezone.utc).isoformat(),'timestamp_source':'filesystem mtime after completed response write','status':200,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'path':str(save)}
  # Verify the bytes read now, rather than trusting a stale sidecar digest.
  if meta.get('url')!=url:raise ValueError('Cached source URL mismatch '+str(save))
  meta.update(bytes=len(b),sha256=hashlib.sha256(b).hexdigest(),path=str(save))
  sidecar.write_text(json.dumps(meta,indent=2))
  return b,meta
 for attempt in range(3):
  req=urllib.request.Request(url,data=json.dumps(payload).encode() if payload else None,headers={'Content-Type':'application/json','User-Agent':'AlphaLuck research audit'})
  stamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
  try:
   with urllib.request.urlopen(req,timeout=15) as resp:
    b=resp.read(cap+1)
    if len(b)>cap: raise ValueError('bounded download exceeded cap')
    meta={'url':url,'request_payload':payload,'fetched_at_utc':stamp,'timestamp_source':'request start','status':resp.status,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'etag':resp.headers.get('ETag'),'last_modified':resp.headers.get('Last-Modified'),'path':str(save)}
   save.write_bytes(b);sidecar.write_text(json.dumps(meta,indent=2))
   return b,meta
  except urllib.error.HTTPError:
   raise
  except (urllib.error.URLError,TimeoutError) as exc:
   if attempt==2:raise
   print(json.dumps({'retry_network_transport':save.name,'attempt':attempt+1,'error':str(exc)}),flush=True)

def prices():
 out=ROOT/'archives';out.mkdir(parents=True,exist_ok=True)
 jobs=[(c,m) for c in ['BTC','ETH','SOL','BNB','DOGE','XRP'] for m in ['10','11']]
 def one(job):
  coin,month=job;fn=f'{coin}USDT-5m-2025-{month}.zip';url=f'https://data.binance.vision/data/spot/monthly/klines/{coin}USDT/5m/{fn}'
  cb,cm=request(url+'.CHECKSUM',out/(fn+'.CHECKSUM'),cap=1000)
  expected=cb.decode().split()[0]
  b,meta=request(url,out/fn)
  if meta['sha256']!=expected:raise ValueError('SHA256 mismatch '+fn)
  meta.update(checksum_verified=True,expected_sha256=expected,checksum=cm,coin=coin,symbol=coin+'USDT',month='2025-'+month)
  parsed=[]
  with zipfile.ZipFile(io.BytesIO(b)) as z:
   names=z.namelist()
   if len(names)!=1:raise ValueError('Unexpected ZIP members')
   for row in csv.reader(io.TextIOWrapper(z.open(names[0]),encoding='utf-8')):
    if len(row)!=12:raise ValueError('Unexpected field count')
    ot,ct=int(row[0]),int(row[6])
    if not (10**15<ot<10**16 and 10**15<ct<10**16):raise ValueError('Expected 2025 microsecond timestamps')
    parsed.append({'coin':coin,'symbol':coin+'USDT','open_time_ms':ot//1000,'close_time_ms':ct//1000,'available_time_ms':(ct+1)//1000,'open':float(row[1]),'high':float(row[2]),'low':float(row[3]),'close':float(row[4]),'volume':float(row[5]),'quote_volume':float(row[7]),'n_trades':int(row[8]),'source_archive':fn})
  meta['row_count']=len(parsed)
  print(json.dumps({'archive':fn,'bytes':len(b),'rows':len(parsed),'sha256_verified':True}),flush=True)
  return parsed,meta
 with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool: batches=list(pool.map(one,jobs))
 rows=sorted([r for a,_ in batches for r in a],key=lambda r:(r['coin'],r['open_time_ms']))
 start,end=ms('2025-10-17T22:00:00'),ms('2025-11-04T00:00:00')
 window=[r for r in rows if start<=r['open_time_ms']<end]
 expected=set(range(start,end,300000));coverage=[];marks=[]
 for coin in ['BTC','ETH','SOL','BNB','DOGE','XRP']:
  a=[r for r in window if r['coin']==coin];ts=[r['open_time_ms'] for r in a]
  missing=sorted(expected-set(ts));dupes=len(ts)-len(set(ts))
  invalid=[r for r in a if r['available_time_ms']!=r['open_time_ms']+300000 or r['close_time_ms']!=r['available_time_ms']-1 or r['low']>min(r['open'],r['close']) or r['high']<max(r['open'],r['close']) or r['low']<=0 or r['volume']<0]
  coverage.append({'coin':coin,'expected_bars':len(expected),'actual_bars':len(a),'missing_bars':len(missing),'missing_open_times_ms':missing,'duplicate_bars':dupes,'invalid_ohlc_or_time_rows':len(invalid),'zero_volume_bars':sum(r['volume']==0 for r in a),'first_open_utc':iso(min(ts)),'last_open_utc':iso(max(ts)),'last_close_utc':iso(max(r['close_time_ms'] for r in a))})
  byavailable={r['available_time_ms']:r for r in rows if r['coin']==coin}
  for t in sorted(expected):
   source=byavailable.get(t)
   if not source:raise ValueError('missing no-lookahead mark '+str((coin,t)))
   marks.append({'coin':coin,'t':t,'time_utc':iso(t),'px':source['close'],'price_kind':'previous_completed_5m_close','source_open_time_ms':source['open_time_ms'],'source_close_time_ms':source['close_time_ms'],'source_archive':source['source_archive']})
 def save_csv(name,data):
  with (ROOT/name).open('w',newline='') as f:
   w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
 save_csv('binance_octnov_2025_5m.csv',rows);save_csv('binance_s1_5m_bars.csv',window);save_csv('binance_s1_5m_marks_no_lookahead.csv',marks)
 summary={'window_start_ms':start,'window_start_utc':iso(start),'window_end_exclusive_ms':end,'window_end_exclusive_utc':iso(end),'official_freeze_ms':1762214399000,'official_freeze_utc':iso(1762214399000),'full_rows':len(rows),'window_rows':len(window),'mark_rows':len(marks),'coverage':coverage,'mark_alignment':'t in [start,end) every five minutes; px is close of the preceding completed bar, available at t; never use contemporaneous future bar close','original_timestamp_unit':'microseconds; converted to milliseconds by exact integer operations','source_license_terms_url':'https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md','use':'Internal academic sensitivity analysis only; raw archives and price panels are not published or copied into original project','limitations':['Binance spot USDT is a separate venue/instrument from Hyperliquid perpetual marks.','Checksum authenticates downloaded bytes; it does not guarantee economic correctness.','Bars starting before end_exclusive include a final close 999 ms after the official freeze timestamp; no-lookahead grid marks stop at 23:55 and do not use that close.']}
 (ROOT/'binance_coverage.json').write_text(json.dumps(summary,indent=2))
 (ROOT/'binance_provenance.json').write_text(json.dumps({'sources':[m for _,m in batches],'normalized_files':[{ 'path':str(ROOT/name),'sha256':hashlib.sha256((ROOT/name).read_bytes()).hexdigest()} for name in ['binance_octnov_2025_5m.csv','binance_s1_5m_bars.csv','binance_s1_5m_marks_no_lookahead.csv']]},indent=2))
 print(json.dumps({'summary':summary}),flush=True)
if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser(description='Download 12 public Binance S1 price archives, verify SHA256, and create no-lookahead marks. Research inputs are licensed separately; no uploads or payments occur.')
 parser.add_argument('--output-dir',type=Path,default=Path(__file__).resolve().parents[3]/'data/raw/binance',help='Private local output directory; default PROJECT/data/raw/binance (gitignored).')
 args=parser.parse_args()
 ROOT=args.output_dir.expanduser().resolve(); ROOT.mkdir(parents=True,exist_ok=True)
 prices()
