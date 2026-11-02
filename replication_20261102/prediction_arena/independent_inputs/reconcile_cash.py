"""Transaction-level cash reconciliation; no rounding used as an exact quantity."""
from analyze_history import *

def main():
    transfers=json.loads((OUT/'transfers_crosschecked.json').read_text())
    fills=json.loads((OUT/'fill_events_normalized.json').read_text())
    redeems=json.loads((OUT/'redemptions_crosschecked.json').read_text())
    details=json.loads((ROOT/'polygonscan/exact_transaction_details.json').read_text())
    txdetail={(x['model_short'],x['tx']):x for x in details}
    ledger=[]; stats=[]
    for model,wallet in WALLETS.items():
        short=SHORT[model]; groups=C.defaultdict(list)
        for x in transfers:
            if x['model_id']==model and timestamp(x['time_utc'])<timestamp(END):
                groups[(x['Transaction Hash'].lower(),x['contract'])].append(x)
        mf=[x for x in fills if x['model_id']==model]
        ftx=C.defaultdict(list)
        for x in mf:ftx[x['transactionHash'].lower()].append(x)
        rtx=C.defaultdict(list)
        for x in redeems:
            if x['model_id']==model and len(x['transaction_hash_candidates'])==1:
                rtx[x['transaction_hash_candidates'][0]].append(x)
        for (tx,contract),rows in groups.items():
            value=None;source=None;category='other_transfer'
            rounding_refund=0
            if contract==USDCE and tx in ftx and all(x['side']=='BUY' for x in ftx[tx]):
                incoming=[x for x in rows if x['sign']==1]
                for x in incoming:
                    if x['exact_amount_raw'] is not None and x['exact_amount_raw']<=10:
                        rounding_refund+=x['exact_amount_raw']
                    elif D(x['display_amount'])==D('.000001'):
                        # The displayed 0.0₅1 is exactly one smallest USDC unit.
                        rounding_refund+=1
                    else:raise ValueError(('Unexplained BUY cash inflow',model,tx,x))
            if (short,tx) in txdetail:
                d=txdetail[(short,tx)];value=d['net_USDC_raw'] if contract==USDC else d['net_USDCE_raw'];source='polygonscan_exact_transaction_details'
                category='conversion' if d['net_USDC_raw']<0 else 'external_funding'
            elif all(x['exact_amount_raw'] is not None for x in rows):
                value=sum(x['sign']*x['exact_amount_raw'] for x in rows);source='blockscout_transfers_crosschecked_with_polygonscan'
            elif contract==USDCE and tx in ftx:
                value=sum(x['net_cash_raw'] for x in ftx[tx])+rounding_refund;source='independent_order_filled_events_plus_observed_rounding_refunds'
            elif contract==USDCE and tx in rtx:
                value=sum(int(x['payout']) for x in rtx[tx]);source='independent_redemption_events'
            if contract==USDCE and tx in ftx:category='trading'
            elif contract==USDCE and tx in rtx:category='redemption'
            elif any('MetaSwap' in (x['From_Nametag']+x['To_Nametag']) for x in rows):category='conversion'
            elif category=='other_transfer':category='external_funding' if all(x['sign']==1 for x in rows) else 'external_withdrawal'
            shown=sum(D(x['display_amount'])*x['sign'] for x in rows)
            diff=None if value is None else D(value)/10**6-shown
            within=None if diff is None else abs(diff)<D('.011')*len(rows)
            if value is not None and not within:raise ValueError(('cash vs display mismatch',model,tx,value,shown))
            # Where both exact sources exist, ensure wallet cash agrees at raw-unit precision.
            independent=None
            if contract==USDCE and tx in ftx:independent=sum(x['net_cash_raw'] for x in ftx[tx])+rounding_refund
            elif contract==USDCE and tx in rtx:independent=sum(int(x['payout']) for x in rtx[tx])
            ledger.append({'model_id':model,'wallet':wallet,'transaction_hash':tx,'contract':contract,
              'block':int(rows[0]['BlockNo']),'time_utc':rows[0]['time_utc'],'category':category,
              'transfer_rows':len(rows),'net_cash_raw':value,'precision_source':source,
              'polygonscan_display_net':str(shown),'within_display_rounding':within,
              'observed_rounding_refund_raw':rounding_refund,
              'independent_event_cash_raw':independent,
              'exact_cross_source_difference_raw':None if independent is None or value is None else value-independent})
        ml=[x for x in ledger if x['model_id']==model]
        checkpoints={}
        for label,cutoff in [('start',START),('formation',FREEZE),('endpoint',END)]:
            before=[x for x in ml if timestamp(x['time_utc'])<timestamp(cutoff)]
            missing=[x for x in before if x['net_cash_raw'] is None]
            checkpoints[label]={'cutoff_utc':cutoff,'unresolved_transaction_contract_groups':len(missing)}
            for contract,name in [(USDC,'USDC'),(USDCE,'USDCE')]:
                checkpoints[label][name]=None if any(x['contract']==contract for x in missing) else str(sum(D(x['net_cash_raw'])/10**6 for x in before if x['contract']==contract))
        running=C.defaultdict(int);negative=[]
        for x in sorted(ml,key=lambda x:(x['block'],x['transaction_hash'])):
            if x['net_cash_raw'] is not None:
                running[x['contract']]+=x['net_cash_raw']
                if running[x['contract']]<0:negative.append(x['transaction_hash'])
        period=[x for x in ml if timestamp(START)<=timestamp(x['time_utc'])<timestamp(END)]
        stats.append({'model_id':model,'transaction_contract_groups':len(ml),
          'unresolved_groups':sum(x['net_cash_raw'] is None for x in ml),
          'negative_partial_balance_transactions':len(negative),'checkpoints':checkpoints,
          'cross_source_cash_mismatches':sum(x['exact_cross_source_difference_raw'] not in [None,0] for x in ml),
          'external_funding_since_start':str(sum(D(x['net_cash_raw'])/10**6 for x in period if x['category']=='external_funding' and x['net_cash_raw'] is not None)),
          'external_withdrawals_since_start':str(sum(D(x['net_cash_raw'])/10**6 for x in period if x['category']=='external_withdrawal' and x['net_cash_raw'] is not None)),
          'conversion_cash_change_since_start':str(sum(D(x['net_cash_raw'])/10**6 for x in period if x['category']=='conversion' and x['net_cash_raw'] is not None))})
    write('cash_ledger.json',ledger);write('cash_reconciliation.json',stats)
    print(json.dumps(stats,indent=2))

if __name__=='__main__':main()
