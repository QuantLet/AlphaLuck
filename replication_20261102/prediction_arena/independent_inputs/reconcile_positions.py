"""Reconstruct actual outcome quantities, independently of operator state snapshots."""
from analyze_history import *

def main():
    fills=json.loads((OUT/'fill_events_normalized.json').read_text())
    red=json.loads((OUT/'redemptions_crosschecked.json').read_text())
    conditions={x['id'].lower():x for x in json.loads((ROOT/'condition_mappings.json').read_text())['rows']}
    ledgers=[]; summaries=[]
    for model,wallet in WALLETS.items():
        short=SHORT[model]; rows=[r for f in sorted((ROOT/'polygonscan').glob(short+'_positions_page*.csv')) for r in csvrows(f) if timestamp(r['DateTime (UTC)'])<timestamp(END)]
        groups=C.defaultdict(list)
        for r in rows:groups[r['Transaction Hash'].lower()].append(r)
        ftx=C.defaultdict(list)
        for r in fills:
            if r['model_id']==model:ftx[r['transactionHash'].lower()].append(r)
        rtx=C.defaultdict(list)
        for r in red:
            if r['model_id']==model and len(r['transaction_hash_candidates'])==1:
                rtx[r['transaction_hash_candidates'][0]].append(r)
        balance=C.defaultdict(int); events=[]; issues=[]; formation=None
        for tx,rr in sorted(groups.items(),key=lambda kv:(int(kv[1][0]['BlockNo']),kv[0])):
            time=rr[0]['DateTime (UTC)']
            if formation is None and timestamp(time)>=timestamp(FREEZE):formation={k:v for k,v in balance.items() if v}
            changes=[];payout_check=None
            if tx in ftx:
                ff=ftx[tx];assets={x['token_id'] for x in ff}
                if len(assets)!=1:issues.append({'tx':tx,'issue':'multiple traded tokens'});continue
                token=next(iter(assets));q=sum(int(x['Quantity'])*((x['To'].lower()==wallet)-(x['From'].lower()==wallet)) for x in rr)
                expected=sum(x['net_quantity_raw'] for x in ff)
                if q!=expected:issues.append({'tx':tx,'issue':'quantity difference','observed':q,'event':expected})
                balance[token]+=q;changes=[{'token_id':token,'quantity_raw':q,'source':'ERC1155 quantity; token identified by matching independent OrderFilled transaction'}]
            elif tx in rtx:
                conds=[conditions[x['condition'].lower()] for x in rtx[tx]]
                candidates={str(token) for c in conds for token in c['positionIds']}
                payout=0; used=set()
                for x in rr:
                    q=int(x['Quantity'])
                    if x['From'].lower()!=wallet or int(x['To'],16)!=0:issues.append({'tx':tx,'issue':'redemption row is not a burn'});continue
                    match=[t for t in candidates if balance[t]==q and t not in used]
                    if len(match)!=1:issues.append({'tx':tx,'issue':'ambiguous burn asset','quantity_raw':q,'candidate_tokens':match});continue
                    token=match[0];used.add(token);balance[token]-=q
                    changes.append({'token_id':token,'quantity_raw':-q,'source':'unique quantity match within redeemed condition position IDs; not directly exported token ID'})
                    c=next(c for c in conds if token in c['positionIds']);idx=c['positionIds'].index(token)
                    den=int(c['payoutDenominator']);payout+=q*int(c['payoutNumerators'][idx])//den
                expected=sum(int(x['payout']) for x in rtx[tx]);payout_check={'reconstructed_raw':payout,'recorded_raw':expected,'matches':payout==expected}
                if payout!=expected:issues.append({'tx':tx,'issue':'redemption payout difference','reconstructed':payout,'recorded':expected})
            else:issues.append({'tx':tx,'issue':'unmatched position transfer','methods':sorted({x['Method'] for x in rr})})
            if any(x<0 for x in balance.values()):issues.append({'tx':tx,'issue':'negative position balance'})
            events.append({'model_id':model,'transaction_hash':tx,'block':int(rr[0]['BlockNo']),'time_utc':time,'changes':changes,'payout_check':payout_check})
        if formation is None:formation={k:v for k,v in balance.items() if v}
        summaries.append({'model_id':model,'position_transfer_rows_before_endpoint':len(rows),
          'trade_transaction_groups':sum(tx in ftx for tx in groups),
          'redemption_transaction_groups':sum(tx in rtx for tx in groups),
          'formation_positions_raw':formation,'endpoint_positions_raw':{k:v for k,v in balance.items() if v},
          'issues':issues,'position_ledger_reconciled':not issues})
        ledgers.extend(events)
    write('positions_ledger.json',ledgers);write('positions_reconciliation.json',summaries)
    print(json.dumps([{'model':x['model_id'],'formation_assets':len(x['formation_positions_raw']),'endpoint_assets_including_dust':len(x['endpoint_positions_raw']),'issues':x['issues']} for x in summaries],indent=2))

if __name__=='__main__':main()
