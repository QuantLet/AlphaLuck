"""Frozen-portfolio comparison with public transaction marks and cash-flow adjustment."""
import pathlib,json,datetime as dt,csv,zipfile,io,collections
from decimal import Decimal as D
ROOT=pathlib.Path(__file__).resolve().parent;OLD=ROOT/'independent_inputs' if (ROOT/'independent_inputs').exists() else ROOT.parent/'predictionarena_independent_20261101';RAW=ROOT/'raw';OUT=ROOT/'results';OUT.mkdir(exist_ok=True)
START=D('1770608709.366855');FREEZE=D('1770695109.366855');END=D('1773100800')
EXCHANGES={'0x4bfb41d5b3570defd03c39a9a4d8de6bd8b8982e','0xc5d563a36ae78145c45a50134d48a1215220f80a'}
def read(path):return json.loads(path.read_text())
def save(name,data):(OUT/name).write_text(json.dumps(data,indent=2,ensure_ascii=False,default=str))
def ts(s):return D(str(dt.datetime.fromisoformat(s.replace('Z','+00:00')).replace(tzinfo=dt.timezone.utc).timestamp()))
def eventkey(x):return tuple(map(int,x['id'].split('_')))

def marks(label,cutoff,tokens):
    condmap={c['id']:c for c in read(OLD/'condition_mappings.json')['rows']}
    condmap.update({c['id']:c for c in read(RAW/'target_conditions.json')})
    cond=list(condmap.values());red=read(RAW/'global_redemptions.json')+read(OLD/'results/redemptions_crosschecked.json');earliest={}
    for r in red:
        if D(r['timestamp'])<cutoff and (r['condition'] not in earliest or eventkey(r)<eventkey(earliest[r['condition']])):earliest[r['condition']]=r
    values={}
    for c in cond:
        if c['id'] in earliest and D(c['payoutDenominator'])>0:
            for t,n in zip(c['positionIds'],c['payoutNumerators']):
                if t in tokens:values[t]={'price':D(n)/D(c['payoutDenominator']),'method':'contractual_payout','condition':c['id'],'evidence_time':earliest[c['id']]['timestamp'],'evidence_event_id':earliest[c['id']]['id']}
    groups=collections.defaultdict(list)
    for r in read(RAW/(label+'_price_events.json')):
        if D(r['timestamp'])>=cutoff:continue
        if (r['makerAssetId']=='0')==(r['takerAssetId']=='0'):continue
        token=r['takerAssetId'] if r['makerAssetId']=='0' else r['makerAssetId']
        if token in tokens:groups[(token,r['transactionHash'])].append(r)
    candidates=collections.defaultdict(list)
    for (token,tx),rows in groups.items():
        # Maker-side fills are the underlying matches. Exclude the taker summary
        # when those fills exist for this same token/transaction, avoiding double
        # counting. Complementary-token matches can leave only a summary for a token.
        components=[r for r in rows if r['taker'].lower() not in EXCHANGES]
        selected=components or rows
        last=max(rows,key=eventkey)
        rows=selected
        qty=sum(int(r['takerAmountFilled'] if r['makerAssetId']=='0' else r['makerAmountFilled']) for r in rows)
        cash=sum(int(r['makerAmountFilled'] if r['makerAssetId']=='0' else r['takerAmountFilled']) for r in rows)
        if not qty:continue
        price=D(cash)/D(qty)
        assert 0<=price<=1,(token,tx,price)
        candidates[token].append((eventkey(last),{'price':price,'method':'last_transaction_VWAP','transaction_hash':tx,'evidence_time':last['timestamp'],'age_seconds':cutoff-D(last['timestamp']),'quantity':D(qty)/10**6,'cash_USDCE':D(cash)/10**6,'fill_selection':'maker_components' if components else 'taker_summary','fill_event_ids':[r['id'] for r in rows]}))
    for token in sorted(tokens-values.keys()):
        if candidates[token]:values[token]=max(candidates[token],key=lambda x:x[0])[1]
    assert not tokens-values.keys(),('missing marks',tokens-values.keys())
    return values

def gas():
    candles={}
    for file in sorted(RAW.glob('POLUSDC-1m-*.zip')):
        with zipfile.ZipFile(file) as z:
            for row in csv.reader(io.StringIO(z.read(z.namelist()[0]).decode())):
                candles[int(row[0])//10**6]={'close':D(row[4]),'low':D(row[3]),'high':D(row[2]),'close_time_us':int(row[6]),'source_file':file.name}
    rows=[]
    for f in read(OLD/'results/network_fees.json'):
        t=ts(f['DateTime (UTC)'])
        if not f['paid_by_wallet'] or not START<=t<END:continue
        minute=(int(t)//60-1)*60;bar=candles[minute]
        assert D(bar['close_time_us'])/10**6<t
        fee=D(f['fee_POL']);rows.append({'model_id':f['model_id'],'transaction_hash':f['Transaction Hash'],'time':f['DateTime (UTC)'],'timestamp':t,'after_formation':t>=FREEZE,'fee_POL':fee,'fee_precision':f['precision_source'],'POL_USDC_asof':bar['close'],'quote_minute_open':minute,'quote_close_time_us':bar['close_time_us'],'gas_USDC':fee*bar['close'],'gas_USDC_previous_minute_low':fee*bar['low'],'gas_USDC_previous_minute_high':fee*bar['high'],'source_file':bar['source_file']})
    return rows

def main():
    positions=read(OLD/'results/positions_reconciliation.json');cash=read(OLD/'results/cash_reconciliation.json');ledger=read(OLD/'results/cash_ledger.json');attr=read(OLD/'results/replication_feasibility.json')['models']
    ft={t for p in positions for t in p['formation_positions_raw']};et=ft|{t for p in positions for t in p['endpoint_positions_raw']}
    fm=marks('formation',FREEZE,ft);em=marks('endpoint',END,et);fees=gas()
    save('valuation_marks.json',{'formation_time':FREEZE,'endpoint_time_exclusive':END,'formation':fm,'endpoint':em})
    save('gas_valued.json',fees)
    results=[]
    for p in positions:
        model=p['model_id'];c=next(x for x in cash if x['model_id']==model);a=next(x for x in attr if x['model_id']==model)
        f={t:D(q)/10**6 for t,q in p['formation_positions_raw'].items()};e={t:D(q)/10**6 for t,q in p['endpoint_positions_raw'].items()}
        fc=sum(D(c['checkpoints']['formation'][k]) for k in ['USDC','USDCE']);ec=sum(D(c['checkpoints']['endpoint'][k]) for k in ['USDC','USDCE'])
        v0=fc+sum(q*fm[t]['price'] for t,q in f.items())
        flows=[x for x in ledger if x['model_id']==model and x['category'] in ['external_funding','external_withdrawal'] and FREEZE<=ts(x['time_utc'])<END]
        netflows=sum((D(x['net_cash_raw'])/10**6 for x in flows),D(0));weighted=sum((D(x['net_cash_raw'])/10**6*(END-ts(x['time_utc']))/(END-FREEZE) for x in flows),D(0))
        denom=v0+weighted;assert denom>0
        actual=ec+sum(q*em[t]['price'] for t,q in e.items());hold=fc+netflows+sum(q*em[t]['price'] for t,q in f.items())
        gascost=sum((x['gas_USDC'] for x in fees if x['model_id']==model and x['after_formation']),D(0));net=actual-gascost;delta=net-hold
        # Hold retains settlement claims at contractual value, with no forced redemption.
        # Its no-trade path has zero post-formation gas; deposits arrive identically.
        bounds={}
        for name,age in [('settlement_only',None),('max_trade_age_1h',D(3600))]:
            lo=hi=ec-fc-netflows-gascost;unknown=[]
            for t in sorted(set(f)|set(e)):
                dq=e.get(t,D(0))-f.get(t,D(0));m=em[t]
                known=m['method']=='contractual_payout' or (age is not None and m['age_seconds']<=age)
                if known:lo+=dq*m['price'];hi+=dq*m['price']
                else:lo+=min(D(0),dq);hi+=max(D(0),dq);unknown.append(t)
            bounds[name]={'lower_USDC':lo,'upper_USDC':hi,'uncertain_tokens':unknown,'positive':lo>0,'negative':hi<0}
        results.append({'model_id':model,'primary_attribution_candidate':a['attribution_candidate_for_primary_replication'],'formation_cash':fc,'formation_wealth_marked':v0,'net_external_cash_flows':netflows,'time_weighted_external_cash_flows':weighted,'modified_dietz_denominator':denom,'actual_terminal_wealth_before_gas':actual,'post_formation_gas_USDC':gascost,'actual_terminal_wealth_net_gas':net,'holding_terminal_wealth':hold,'trading_minus_holding_USDC_net_gas':delta,'trading_modified_dietz_pct':(net-v0-netflows)/denom*100,'holding_modified_dietz_pct':(hold-v0-netflows)/denom*100,'trading_minus_holding_pp':delta/denom*100,'holding_gas_assumption':0,'formation_price_max_age_seconds':max([fm[t].get('age_seconds',D(0)) for t in f] or [D(0)]),'endpoint_price_max_age_seconds':max([em[t].get('age_seconds',D(0)) for t in set(f)|set(e)] or [D(0)]),'value_difference_bounds_net_gas':bounds})
    save('replication_results.json',{'models':results,'return_method':'Modified Dietz, post-formation; transaction-price valuation proxy; not exact TWR or executable liquidation value.','stablecoin_assumption':'USDC = USDC.e = USD 1. POL/USDC minute prices for gas. Native POL investment PnL excluded.','freeze_time_utc':str(dt.datetime.fromtimestamp(float(FREEZE),dt.timezone.utc)),'endpoint_time_utc':'2026-03-10T00:00:00Z'})
    fields=[k for k in results[0] if k!='value_difference_bounds_net_gas']
    with (OUT/'replication_summary.csv').open('w') as stream:
        w=csv.DictWriter(stream,fieldnames=fields);w.writeheader();w.writerows([{k:r[k] for k in fields} for r in results])
    print(json.dumps([{k:v for k,v in r.items() if k in ['model_id','formation_wealth_marked','trading_minus_holding_USDC_net_gas','post_formation_gas_USDC','trading_modified_dietz_pct','holding_modified_dietz_pct','value_difference_bounds_net_gas']} for r in results],default=str,indent=2))

if __name__=='__main__':main()
