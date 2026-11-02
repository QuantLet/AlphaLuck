"""Read public Parquet byte ranges; never download an entire remote table."""
import io, json, pathlib, ssl, time, urllib.request

ROOT=pathlib.Path(__file__).resolve().parent
REVISION='7eeb860dea5b79d5c74f3182b70bd08c85c8f833'
BASE='https://huggingface.co/datasets/moose-code/polymarket-onchain-v1/resolve/'+REVISION+'/'
WALLETS={
 'glm-4.7':'0x12148aa1a8f2f8f36ba38bc48db86cb08c092bda',
 'claude-opus-4-5-20251101':'0xc93ecb0aa64635ee352db9602f5424e8006596d5',
 'gemini-3-pro-preview':'0xb16582e1de16d044567db61a4216f4aa48f1d9ff',
 'gpt-5.2':'0xf2327959aabfa0c1cff3b2dbfb942cd6efac42ab',
 'mystery-model-alpha':'0xba272f27074326a6d3f112280ef46eb178aca7f2'}

class RemoteParquet(io.RawIOBase):
    def __init__(self,path,size):
        self.path=path;self.size=size;self.pos=0;self.bytes_read=0;self.requests=0;self.cache_start=0;self.cache_data=b''
    def readable(self):return True
    def seekable(self):return True
    def tell(self):return self.pos
    def seek(self,offset,whence=0):
        self.pos=offset if whence==0 else self.pos+offset if whence==1 else self.size+offset
        return self.pos
    def prefetch_group(self,meta):
        self.cache_data=b''
        starts=[c.dictionary_page_offset if c.has_dictionary_page else c.data_page_offset for c in (meta.column(i) for i in range(meta.num_columns))]
        ends=[starts[i]+meta.column(i).total_compressed_size for i in range(meta.num_columns)]
        start=min(starts);end=max(ends);self.seek(start);data=self.read(end-start)
        self.cache_start=start;self.cache_data=data
    def read(self,n=-1):
        if n<0:n=self.size-self.pos
        if n==0:return b''
        n=min(n,self.size-self.pos)
        if n>100_000_000:raise RuntimeError('Unexpected large range')
        start=self.pos;end=start+n-1
        if self.cache_start<=start and end<self.cache_start+len(self.cache_data):
            data=self.cache_data[start-self.cache_start:end-self.cache_start+1];self.pos+=n;return data
        for attempt in range(3):
            try:
                req=urllib.request.Request(BASE+self.path,headers={'Range':f'bytes={start}-{end}'})
                with urllib.request.urlopen(req,context=ssl.create_default_context(),timeout=60) as r:
                    if r.status!=206 or r.headers.get('Content-Range')!=f'bytes {start}-{end}/{self.size}':
                        raise RuntimeError('Server did not honor exact byte range')
                    data=r.read(n+1)
                    if len(data)!=n:raise RuntimeError('Truncated byte range')
                self.pos+=n;self.bytes_read+=n;self.requests+=1
                return data
            except Exception:
                if attempt==2:raise
                time.sleep(1+attempt)

def open_parquet(path,size):
    import pyarrow.parquet as pq
    stream=RemoteParquet(path,size)
    return pq.ParquetFile(stream),stream

def tree_file(entity,path):
    tree=json.loads((ROOT/(entity+'_tree.txt')).read_text())
    return next(x for x in tree if x['path']==path)
