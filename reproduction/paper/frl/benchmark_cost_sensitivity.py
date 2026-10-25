"""Reproduce the terminal-cost sensitivity; no funding or liquidation simulation."""
from pathlib import Path
import sys, json
import pandas as pd
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent.parent
sys.path.insert(0,str(ROOT/'src'))
import exante_benchmark as eb

def main():
    a=pd.read_parquet(ROOT/'data/derived/accounts.parquet')
    a=a.loc[a.season.eq('S15'),['tag','equity_change']]
    d=eb.run('S15',form_hours=24,mmr=.025).merge(a,on='tag',validate='one_to_one')
    assert len(d)==32
    book=len(d)*eb.INITIAL_CAPITAL
    hold=float(d.hold_net.sum()); actual=float(d.equity_change.sum())
    rows=[dict(debit_pp=c, frozen_return_pct=100*hold/book-c,
               advantage_pp=100*(hold-actual)/book-c,
               accounts_ahead=int((d.hold_net-c*eb.INITIAL_CAPITAL/100>d.equity_change).sum()))
          for c in (0,1,5,10,20)]
    result=dict(initial_capital=book, frozen_profit=hold, realised_profit=actual,
                advantage_dollars=hold-actual, scenarios=rows,
                limitation='Terminal adjustment only; no new margin test.')
    (HERE/'benchmark_cost_sensitivity.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':
    main()
