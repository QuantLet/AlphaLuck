from calculate_replication import *

def main():
    base=read(OUT/'replication_results.json');states=read(RAW/'funding_checkpoints.json');pos=read(OLD/'results/positions_reconciliation.json');cash=read(OLD/'results/cash_ledger.json');gasrows=read(OUT/'gas_valued.json');values=[];allmarks={}
    for r in base['models']:
        model=r['model_id'];s=next(s for s in states if s['model_id']==model);p=next(x for x in pos if x['model_id']==model);cut=ts(s['funding']['time_utc'])
        f={t:D(q)/10**6 for t,q in p['formation_positions_raw'].items()};q={t:D(q)/10**6 for t,q in s['before_funding_positions_raw'].items()}
        m=marks('funding',cut,set(f)|set(q));allmarks[model]={'cutoff_exclusive':cut,'marks':m}
        # Ledger begins before these wallets' first observed funding; cash is a
        # signed sum of all authentic stablecoin transfers before the checkpoint.
        beforecash=sum((D(x['net_cash_raw'])/10**6 for x in cash if x['model_id']==model and ts(x['time_utc'])<cut),D(0))
        pregas=sum((D(x['gas_USDC']) for x in gasrows if x['model_id']==model and FREEZE<=D(x['timestamp'])<cut),D(0))
        av=beforecash+sum(qty*m[t]['price'] for t,qty in q.items())-pregas
        hv=D(r['formation_cash'])+sum(qty*m[t]['price'] for t,qty in f.items())
        flow=D(s['funding']['net_cash_raw'])/10**6;v0=D(r['formation_wealth_marked'])
        assert av>0 and hv>0 and flow==D(r['net_external_cash_flows'])
        atwr=(av/v0*D(r['actual_terminal_wealth_net_gas'])/(av+flow)-1)*100
        htwr=(hv/v0*D(r['holding_terminal_wealth'])/(hv+flow)-1)*100
        values.append({'model_id':model,'primary_attribution_candidate':r['primary_attribution_candidate'],'funding_time':s['funding']['time_utc'],'funding_amount':flow,'actual_cash_before_funding':beforecash,'actual_wealth_before_funding_net_gas':av,'holding_wealth_before_funding':hv,'gas_before_funding_USDC':pregas,'funding_mark_max_age_seconds':max([v.get('age_seconds',D(0)) for v in m.values()] or [D(0)]),'trading_TWR_pct_transaction_marks':atwr,'holding_TWR_pct_transaction_marks':htwr,'TWR_difference_pp':atwr-htwr,'terminal_wealth_difference_USDC':r['trading_minus_holding_USDC_net_gas']})
    save('funding_valuation_marks.json',allmarks);save('time_weighted_returns.json',{'models':values,'method':'Two subperiods split immediately before the single external deposit; geometric linkage. Values estimated from prior on-chain trades or proven settlements. Gas charged as cumulative expense in the stablecoin/outcome sleeve; no native POL investment return.','formula':'R = (V_before_flow / V_formation) * (V_end / (V_before_flow + flow)) - 1. Wealth differences and TWR differences answer different questions with intermediate funding.'})
    fields=list(values[0])
    with (OUT/'time_weighted_returns.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(values)
    print(json.dumps(values,default=str,indent=2))

if __name__=='__main__':main()
