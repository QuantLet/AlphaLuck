"""Check the independent exposure algebra of the generated stress scenarios.

Generate data first with src/frozen_book_robustness.py --output DIR, then run
python tests/test_frozen_book_robustness.py DIR. No network or random tests.
"""
from pathlib import Path
from itertools import product
import json
import sys
import numpy as np
import pandas as pd


def main():
    out=Path(sys.argv[1])
    report=json.loads((out/'frozen_book_robustness.json').read_text())
    positions=pd.read_csv(out/'frozen_book_robustness_positions.csv')
    accounts=pd.read_csv(out/'frozen_book_robustness_accounts.csv')
    scenarios=pd.read_csv(out/'frozen_book_robustness_scenarios.csv')
    margins=pd.read_csv(out/'frozen_book_robustness_margin_screens.csv')
    assert len(accounts)==96 and not accounts.duplicated(['freeze_hours','tag']).any()
    for item in report['summaries']:
        cut=item['freeze_hours']
        p=positions[positions.freeze_hours.eq(cut)]
        a=accounts[accounts.freeze_hours.eq(cut)]
        s=scenarios[scenarios.freeze_hours.eq(cut)]
        x=p.groupby('coin').differential_signed_notional.sum().to_numpy()
        # Enumerate ALL common-market vertices; independently verify the
        # sign and tightness of the adverse common-price endpoint bound.
        brute_min=min(float(x@np.array(v)) for v in product((-1,1),repeat=len(x)))
        assert np.isclose(-brute_min,item['endpoint_error_common_market_l1'])
        assert np.isclose(item['gap_dollars']+.01*item['endpoint_common_market_break_even_pct']*brute_min,0,atol=1e-7)
        for row in s[s.scenario.eq('terminal_friction')].itertuples():
            # Independently price each terminal instrument's closing fee.
            fees=(p.frozen_quantity.abs()*p.terminal_price).sum()*row.stress_bps/10000
            actual_fees=0 if row.convention=='frozen_only' else (p.actual_terminal_quantity.abs()*p.terminal_price).sum()*row.stress_bps/10000
            expected=100*(item['gap_dollars']-fees+actual_fees)/(len(a)*10000)
            assert np.isclose(row.advantage_pp,expected,atol=1e-10)
        e=s[s.scenario.eq('endpoint_price_error')].pivot(index='stress_pct',columns='convention',values='advantage_pp')
        assert (e.accountwise_lower_bounds<=e.common_market_adverse+1e-10).all()
        m=margins[margins.freeze_hours.eq(cut)]
        for _,g in m.groupby('assumed_aggregate_mmr'):
            assert (g.sort_values('price_error_bound_pct').accounts_failing_buffer_screen.diff().dropna()>=0).all()
        for _,g in m.groupby('price_error_bound_pct'):
            assert (g.sort_values('assumed_aggregate_mmr').accounts_failing_buffer_screen.diff().dropna()>=0).all()
    print('PASS: 96 account rows; 384 endpoint-bound vertices; every fee scenario; bound ordering and margin-screen monotonicity.')


if __name__=='__main__':
    main()
