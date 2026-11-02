"""Assess attribution and valuation separately; calculate no unverified returns."""
from analyze_history import *

def main():
    pos=json.loads((OUT/'positions_reconciliation.json').read_text())
    cash=json.loads((OUT/'cash_reconciliation.json').read_text())
    fills=json.loads((OUT/'fill_events_normalized.json').read_text())
    joins=json.loads((OUT/'order_linkage.json').read_text())
    red=json.loads((OUT/'redemptions_crosschecked.json').read_text())
    cond=json.loads((ROOT/'condition_mappings.json').read_text())['rows']
    resolved={}
    for c in cond:
        events=[r for r in red if r['condition'].lower()==c['id'].lower() and int(r['timestamp'])<timestamp(END)]
        if events and int(c['payoutDenominator'])>0:
            for token,num in zip(c['positionIds'],c['payoutNumerators']):
                resolved[str(token)]={'value':D(num)/D(c['payoutDenominator']),
                  'condition':c['id'],'resolution_known_no_later_than':min(int(x['timestamp']) for x in events)}
    result=[]
    for p in pos:
        model=p['model_id'];c=next(x for x in cash if x['model_id']==model)
        f=p['formation_positions_raw']; e=p['endpoint_positions_raw']
        unknown=sorted((set(f)|set(e))-set(resolved))
        unlinked=[x for x in fills if x['model_id']==model and x['operator_order_event_id'] is None]
        after=[x for x in unlinked if int(x['timestamp'])>=timestamp(FREEZE)]
        # Bounds use a common price for the same outcome in both portfolios.
        # Cash additions received after formation are also received by holding.
        ledger=json.loads((OUT/'cash_ledger.json').read_text())
        additions=sum(D(x['net_cash_raw'])/10**6 for x in ledger if x['model_id']==model and x['category'] in ['external_funding','external_withdrawal'] and timestamp(FREEZE)<=timestamp(x['time_utc'])<timestamp(END))
        holdcash=D(c['checkpoints']['formation']['USDC'])+D(c['checkpoints']['formation']['USDCE'])+additions
        endcash=D(c['checkpoints']['endpoint']['USDC'])+D(c['checkpoints']['endpoint']['USDCE'])
        low=high=endcash-holdcash
        for token in set(f)|set(e):
            dq=D(e.get(token,0)-f.get(token,0))/10**6
            if token in resolved:low+=dq*resolved[token]['value'];high+=dq*resolved[token]['value']
            else:low+=min(D(0),dq);high+=max(D(0),dq)
        mjoins=[x for x in joins if x['model_id']==model]
        result.append({'model_id':model,'cash_and_quantity_ledgers_reconciled':not p['issues'] and c['unresolved_groups']==0 and c['cross_source_cash_mismatches']==0,
          'unlinked_orders_before_formation':len(unlinked)-len(after),'unlinked_orders_after_formation':len(after),
          'unconfirmed_operator_orders':sum(not x['wallet_token_side_match'] for x in mjoins),
          'operator_numeric_discrepancy_or_missing_quantity_orders':sum(x['wallet_token_side_match'] and (x['quantity_difference'] is None or abs(x['quantity_difference'])>1e-5 or abs(x['cash_difference'] or 0)>1e-5) for x in mjoins),
          'unknown_endpoint_marks':unknown,'unknown_endpoint_mark_count':len(unknown),
          'unknown_endpoint_marks_for_formation':sorted(set(f)-set(resolved)),
          'attribution_candidate_for_primary_replication':not after,
          'returns_ready':not unknown and not after,
          'trading_minus_holding_value_bounds_before_POL_gas':{'lower_USD_at_stablecoin_parity':str(low),'upper_USD_at_stablecoin_parity':str(high),
            'assumptions':'Outcomes in [0,1], USDC and USDC.e at $1, same post-formation external cash flows, observed conversion costs retained in actual cash; no POL inventory or gas conversion; bounds, not estimated returns.'},
          'trading_return':None,'holding_return':None})
    write('replication_feasibility.json',{'models':result,'resolved_token_values_with_pre_endpoint_evidence':resolved,
      'status':'Independent cash and quantity reconstruction completed. Endpoint valuation and USD gas conversion remain; GPT also has one post-formation unlinked order.'})
    print(json.dumps([{k:x[k] for k in ['model_id','cash_and_quantity_ledgers_reconciled','unlinked_orders_after_formation','unknown_endpoint_mark_count','trading_minus_holding_value_bounds_before_POL_gas']} for x in result],indent=2))

if __name__=='__main__':main()
