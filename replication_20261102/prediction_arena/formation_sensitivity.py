"""Offline 12/24/48-hour comparison, replaying independently reconciled ledgers.

Terminal dollar differences do not require a formation-time price. All new
formation holdings have endpoint values in the previously collected archive.
No intermediate returns or unobserved execution prices are invented.
"""
from calculate_replication import *

def positions_at(ledger, model, cutoff):
    q=collections.defaultdict(int)
    for event in ledger:
        if event['model_id']==model and ts(event['time_utc'])<cutoff:
            for x in event['changes']:
                q[x['token_id']]+=x['quantity_raw']
    assert all(v>=0 for v in q.values())
    return {k:D(v)/10**6 for k,v in q.items() if v}

def evaluate(hour):
    cutoff=START+D(hour)*3600
    pl=read(OLD/'results/positions_ledger.json');cl=read(OLD/'results/cash_ledger.json')
    executions=read(OLD/'results/fill_events_normalized.json')
    em=read(OUT/'valuation_marks.json')['endpoint'];fees=read(OUT/'gas_valued.json')
    models=sorted({p['model_id'] for p in pl});rows=[]
    for model in models:
        f=positions_at(pl,model,cutoff);e=positions_at(pl,model,END)
        assert (set(f)|set(e))<=em.keys()
        for token in sorted(set(f)|set(e)):
            assert D(em[token]['evidence_time'])<END
        ml=[x for x in cl if x['model_id']==model]
        fc=sum((D(x['net_cash_raw'])/10**6 for x in ml if ts(x['time_utc'])<cutoff),D(0))
        ec=sum((D(x['net_cash_raw'])/10**6 for x in ml if ts(x['time_utc'])<END),D(0))
        flows=sum((D(x['net_cash_raw'])/10**6 for x in ml if cutoff<=ts(x['time_utc'])<END and x['category'] in ['external_funding','external_withdrawal']),D(0))
        gas=sum((D(x['gas_USDC']) for x in fees if x['model_id']==model and cutoff<=D(x['timestamp'])<END),D(0))
        actual=ec+sum(q*D(em[t]['price']) for t,q in e.items())-gas
        hold=fc+flows+sum(q*D(em[t]['price']) for t,q in f.items())
        unlinked=[x for x in executions if x['model_id']==model and x['operator_order_event_id'] is None and cutoff<=D(x['timestamp'])<END]
        bounds={}
        for name,age in [('settlement_only',None),('max_trade_age_1h',D(3600))]:
            lo=hi=ec-fc-flows-gas
            for t in sorted(set(f)|set(e)):
                dq=e.get(t,D(0))-f.get(t,D(0));mark=em[t]
                known=mark['method']=='contractual_payout' or (age is not None and D(mark['age_seconds'])<=age)
                if known:lo+=dq*D(mark['price']);hi+=dq*D(mark['price'])
                else:lo+=min(D(0),dq);hi+=max(D(0),dq)
            bounds[name]={'lower':lo,'upper':hi}
        rows.append({'formation_hour':hour,'model_id':model,'formation_time':str(cutoff),
            'formation_positions':len(f),'formation_positions_raw':{t:int(q*10**6) for t,q in f.items()},
            'formation_cash':fc,'post_formation_external_funding':flows,'post_formation_gas':gas,
            'trading_terminal_net':actual,'holding_terminal':hold,'trading_minus_holding':actual-hold,
            'unlinked_orders_after_formation':len(unlinked),'eligible':not unlinked,
            'cash_only':not f,'bounds':bounds})
    return rows

def main():
    rows=sum((evaluate(h) for h in [12,24,48]),[])
    old={r['model_id']:r for r in read(OUT/'replication_results.json')['models']}
    for r in rows:
        if r['formation_hour']==24:
            assert abs(r['trading_minus_holding']-D(old[r['model_id']]['trading_minus_holding_USDC_net_gas']))<D('1e-20')
    summaries=[]
    for h in [12,24,48]:
        r=[x for x in rows if x['formation_hour']==h and x['eligible']]
        active=[x for x in r if not x['cash_only']]
        summaries.append({'formation_hour':h,'eligible':len(r),'holding_ahead':sum(x['trading_minus_holding']<0 for x in r),
                          'with_positions':len(active),'holding_ahead_with_positions':sum(x['trading_minus_holding']<0 for x in active)})
    save('formation_sensitivity.json',{'method':'Same common endpoint, identical external funding, terminal dollar comparison; no formation valuation needed.', 'rows':rows,'summary':summaries})
    columns=[k for k in rows[0] if k not in ['bounds','formation_positions_raw']]
    with (OUT/'formation_sensitivity.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=columns);writer.writeheader();writer.writerows([{k:r[k] for k in columns} for r in rows])
    print(json.dumps({'summary':summaries,'results':[{k:r[k] for k in ['formation_hour','model_id','trading_minus_holding','eligible','cash_only','bounds']} for r in rows]},indent=2,default=str))

if __name__=='__main__':main()
