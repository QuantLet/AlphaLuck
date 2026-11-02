"""Audit independently obtained wallet histories. Never impute missing ledger data."""
import collections as C
import csv, datetime as dt, json, re
from decimal import Decimal as D
from pathlib import Path
from range_reader import ROOT, WALLETS

OUT=ROOT/'results'; OUT.mkdir(exist_ok=True)
SHORT=dict(zip(WALLETS, ['glm','claude','gemini','gpt','mystery']))
BY_WALLET={v:k for k,v in WALLETS.items()}
USDC='0x3c499c542cef5e3811e1192ce70d8cc03d5c3359'
USDCE='0x2791bca1f2de4661ed88a30c99a7a9449aa84174'
CTF='0x4d97dcd97ec945f40cf65f87097ace5ea0476045'
TOKEN_NAMES={'USD Coin(USDC)':USDC,'USD Coin (PoS)(USDC.e)':USDCE}
START='2026-02-09T03:45:09.366855+00:00'
FREEZE='2026-02-10T03:45:09.366855+00:00'
END='2026-03-10T00:00:00+00:00'

def timestamp(s):
    return dt.datetime.fromisoformat(s.replace('Z','+00:00')).replace(tzinfo=dt.timezone.utc).timestamp()
def write(name, data):
    (OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2,default=str))
def csvrows(path):
    return list(csv.DictReader(path.open(encoding='utf-8-sig')))
def event_rows(entity):
    rows=[]
    for f in sorted((ROOT/'extracted').glob(entity+'__*/*.json')):
        if f.name!='manifest.json':rows.extend(json.loads(f.read_text())['rows'])
    assert len(rows)==len({r['id'] for r in rows}), f'duplicate {entity} ids'
    return sorted(rows,key=lambda x:tuple(map(int,x['id'].split('_'))))
def signed(raw, wallet):
    return int(raw['TokensTransferred'])*((raw['ToAddress'].lower()==wallet)-(raw['FromAddress'].lower()==wallet))
def display_number(s):
    s=s.replace(',','')
    # Etherscan's 0.0₅1 denotes five leading zeroes: 0.000001.
    if re.fullmatch(r'0\.0[₀-₉]+\d+',s):
        sub=re.search('[₀-₉]+',s).group(); n=int(sub.translate(str.maketrans('₀₁₂₃₄₅₆₇₈₉','0123456789')))
        return D('0.'+'0'*n+s.split(sub)[1])
    return D(s)

def main():
    orders=json.loads((ROOT/'operator_inputs/orders.json').read_text())
    source_by_hash={x['order_id'].lower():x for x in orders}
    fills=event_rows('order_filled'); red=event_rows('redemption')
    fees=event_rows('fee_refunded')
    exact_details={x['tx']:x for x in json.loads((ROOT/'polygonscan/exact_transaction_details.json').read_text())}
    manifests=[json.loads(f.read_text()) for f in (ROOT/'extracted').glob('*/manifest.json')]
    complete={x['path']:x['recorded_row_groups']==x['all_row_groups'] for x in manifests}
    trades=[]
    for r in fills:
        buy=r['makerAssetId']=='0'; sell=r['takerAssetId']=='0'
        assert buy != sell, 'unexpected trade asset pair'
        q=int(r['takerAmountFilled'] if buy else r['makerAmountFilled'])
        cash=int(r['makerAmountFilled'] if buy else r['takerAmountFilled'])
        fee=int(r['fee']); model=BY_WALLET[r['maker'].lower()]
        o=source_by_hash.get(r['orderHash'].lower())
        trades.append({**r,'model_id':model,'side':'BUY' if buy else 'SELL',
          'token_id':r['takerAssetId'] if buy else r['makerAssetId'],
          'quantity_raw':q,'gross_cash_raw':cash,'fee_raw':fee,
          'fee_asset':'outcome_token' if buy else 'USDC.e',
          'net_cash_raw':-cash if buy else cash-fee,
          'net_quantity_raw':q-fee if buy else -q,
          'operator_order_event_id':o['order_event_id'] if o else None,
          'operator_model_matches':o['model_id']==model if o else None})
    by_order=C.defaultdict(list)
    for r in trades:by_order[r['orderHash'].lower()].append(r)
    joins=[]
    for o in orders:
        matches=by_order[o['order_id'].lower()]
        size=sum(r['quantity_raw'] for r in matches)/1e6
        cash=sum((-1 if r['side']=='BUY' else 1)*r['gross_cash_raw'] for r in matches)/1e6
        joins.append({**o,'independent_fill_count':len(matches),
          'independent_tx_hashes':sorted({r['transactionHash'].lower() for r in matches}),
          'wallet_token_side_match':bool(matches) and all(r['operator_model_matches'] and r['token_id']==o['token_id'] and r['side']==o['side'] for r in matches),
          'quantity_difference':None if o['filled_size'] is None or not matches else size-o['filled_size'],
          'cash_difference':None if o['cashflow_reported'] is None or not matches else cash-o['cashflow_reported']})
    all_transfers=[]; all_gas=[]; all_redeems=[]; summary=[]; comparisons=[]; unresolved=[]
    for model,wallet in WALLETS.items():
        short=SHORT[model]; raw=csvrows(ROOT/'blockscout'/f'{short}_transfers.csv')
        bt=csvrows(ROOT/'blockscout'/f'{short}_transactions.csv'); btmap={r['TxHash'].lower():r for r in bt}
        poly=[r for f in sorted((ROOT/'polygonscan').glob(short+'_transfers_page*.csv')) for r in csvrows(f)]
        ptx=[r for f in sorted((ROOT/'polygonscan').glob(short+'_transactions_page*.csv')) for r in csvrows(f) if re.fullmatch('0x[0-9a-fA-F]{64}',r.get('Transaction Hash',''))]
        assert len(ptx)==len({r['Transaction Hash'].lower() for r in ptx})
        exact_groups=C.defaultdict(list)
        for r in raw:
            if r['TokenContractAddress'].lower() in [USDC,USDCE]:
                exact_groups[(r['TxHash'].lower(),r['TokenContractAddress'].lower(),r['FromAddress'].lower(),r['ToAddress'].lower())].append(r)
        mf=[r for r in trades if r['model_id']==model]; mr=[r for r in red if r['redeemer'].lower()==wallet]
        for r in poly:
            contract=TOKEN_NAMES.get(r['Token'])
            if not contract:continue
            tx=r['Transaction Hash'].lower(); key=(tx,contract,r['From'].lower(),r['To'].lower())
            candidates=exact_groups.get(key,[])
            shown=display_number(r['Amount']); exact=None; origin=None
            # A unique row with this transfer identity can supply precise units.
            if len(candidates)==1:
                value=D(candidates[0]['TokensTransferred'])/10**int(candidates[0]['TokenDecimals'])
                if abs(value-shown)<D('.011'):
                    exact=int(candidates[0]['TokensTransferred']);origin='blockscout_transfer'
            elif len(candidates)>1:
                eq=[x for x in candidates if D(x['TokensTransferred'])/10**int(x['TokenDecimals'])==shown]
                if len(eq)==1:exact=int(eq[0]['TokensTransferred']);origin='blockscout_transfer_exact_amount'
            sign=(r['To'].lower()==wallet)-(r['From'].lower()==wallet)
            rec={**r,'model_id':model,'contract':contract,'time_utc':r['DateTime (UTC)'],
                 'sign':sign,'exact_amount_raw':exact,'precision_source':origin,'display_amount':str(shown)}
            all_transfers.append(rec)
        pset={r['Transaction Hash'].lower() for r in poly}
        bset={r['TxHash'].lower() for r in raw}
        gas=[]
        for r in ptx:
            tx=r['Transaction Hash'].lower(); own=r['From'].lower()==wallet
            if tx in exact_details:
                amount=D(exact_details[tx]['fee_POL']);precision='polygonscan_exact_transaction_detail'
            elif tx in btmap:
                amount=D(btmap[tx]['Fee'])/10**18;precision='blockscout_wei'
            else:amount=D(r['Txn Fee'].replace(',',''));precision='polygonscan_display_8_decimals'
            g={**r,'model_id':model,'paid_by_wallet':own,'fee_POL':str(amount),'precision_source':precision}
            gas.append(g);all_gas.append(g)
        mtrans=[r for r in all_transfers if r['model_id']==model]
        # Redemptions are indexed independently; use wallet+block to find transaction hash.
        for r in mr:
            block=r['id'].split('_')[1]
            txmatches=[x for x in ptx if x['Blockno']==block]
            transfermatches=[x for x in mtrans if x['BlockNo']==block and x['contract']==USDCE and x['sign']==1]
            hashes=sorted({x['Transaction Hash'].lower() for x in txmatches+transfermatches})
            all_redeems.append({**r,'model_id':model,'transaction_hash_candidates':hashes,
                'payout_USDCE':str(D(r['payout'])/10**6)})
        checkpoints={}
        for label,cutoff in [('start',START),('formation',FREEZE),('endpoint',END)]:
            included=[x for x in mtrans if timestamp(x['time_utc'])<timestamp(cutoff)]
            checkpoints[label]={'cutoff_utc':cutoff,
              'blockscout_only_net_USDCE':str(sum(D(signed(x,wallet))/10**6 for x in raw if x['TokenContractAddress'].lower()==USDCE and timestamp(x['UnixTimestamp'])<timestamp(cutoff))),
              'blockscout_only_net_USDC':str(sum(D(signed(x,wallet))/10**6 for x in raw if x['TokenContractAddress'].lower()==USDC and timestamp(x['UnixTimestamp'])<timestamp(cutoff))),
              'polygonscan_rows_without_exact_value':sum(x['exact_amount_raw'] is None for x in included)}
        mo=[x for x in joins if x['model_id']==model]
        gperiod=[x for x in gas if x['paid_by_wallet'] and timestamp(START)<=timestamp(x['DateTime (UTC)'])<timestamp(END)]
        summary.append({'model_id':model,'wallet':wallet,'blockscout_transfer_rows':len(raw),'polygonscan_transfer_rows':len(poly),
          'polygonscan_transfer_transactions_absent_blockscout':len(pset-bset),
          'blockscout_transactions':len(bt),'polygonscan_transactions':len(ptx),
          'operator_orders':len(mo),'independent_fill_events':len(mf),'independent_unique_orders':len({x['orderHash'] for x in mf}),
          'operator_orders_found':sum(x['wallet_token_side_match'] for x in mo),
          'independent_orders_not_in_operator_log':len({x['orderHash'] for x in mf if x['operator_order_event_id'] is None}),
          'fee_nonzero_fill_events':sum(x['fee_raw']>0 for x in mf),
          'redemption_events':len(mr),'redemption_positive_events':sum(int(x['payout'])>0 for x in mr),
          'redemption_total_USDCE':str(sum(D(x['payout'])/10**6 for x in mr)),
          'wallet_paid_gas_POL_study_period':str(sum(D(x['fee_POL']) for x in gperiod)),
          'wallet_paid_transactions_study_period':len(gperiod),
          'wallet_paid_gas_rows_with_rounded_fee':sum(x['precision_source']=='polygonscan_display_8_decimals' for x in gperiod),
          'checkpoints':checkpoints})
    write('fill_events_normalized.json',trades);write('order_linkage.json',joins)
    write('transfers_crosschecked.json',all_transfers);write('network_fees.json',all_gas)
    write('redemptions_crosschecked.json',all_redeems)
    write('history_summary.json',{'period_start':START,'formation':FREEZE,'endpoint_exclusive':END,
      'archive_complete_files':complete,'fee_refunded_events':len(fees),'models':summary})
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
