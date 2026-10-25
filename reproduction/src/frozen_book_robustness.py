"""Exposure-based sensitivity of the Season 1.5 frozen-book accounting comparison.

Run: python src/frozen_book_robustness.py --output PATH
Requires the existing derived inputs and data/external/funding; no network.
Does not alter existing analytical outputs. The primary specification replaces
daily-booked funding on BOTH paths by hourly rates times pooled fill prices.
Prices are proxies for historical oracle/mark prices. This is an accounting
mark-to-market comparison conditional on observed prices, not an executable
strategy simulation: isolated collateral, exact margin rules, intervening
liquidations, and order-book impact are not reconstructed.

Stress scenarios are deliberately hypothetical, not probability statements:
* closing friction c times each terminal gross notional, both symmetrically
  and (conservatively) on the frozen book alone;
* endpoint-price perturbations bounded by d per asset, applied to BOTH books;
  the paired gap exposure is (q_frozen-q_actual)*P, not frozen gross alone;
* bounded hourly oracle-price error applied to the funding-gap exposures;
* aggregate equity/gross screens on the observed five-minute grid, including
  hourly funding. An account-level pass does not establish isolated solvency.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import funding_hourly_sensitivity as fh
import wallets


def finite_scalar(value):
    return float(value) if np.isfinite(value) else None


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=HERE.parent)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root, out = args.root.resolve(), args.output.resolve()
    der, ext = root/'data/derived', root/'data/external/funding'
    paths = [der/f'{name}.parquet' for name in ('fills','panel','equity','accounts')]
    frames = [pd.read_parquet(p) for p in paths]
    fills, panel, equity, accounts = [d[d.season.eq('S15')].copy() for d in frames]
    accounts = accounts.set_index('tag')
    lo, hi = wallets.S15_START_MS, wallets.S15_OFFICIAL_END_MS
    hours = np.arange(lo, hi+1, fh.HOUR)
    rates, rate_paths = fh.load_rates(ext)
    positions, prices = fh.data_groups(fills)
    coins = sorted(prices)
    unit = {}
    for coin in coins:
        r, p = fh.hourly_market(coin, hours, rates, prices)
        unit[coin] = -r*p
    actual_payments = fh.actual_payments(accounts.index, coins, hours, positions, unit)
    eqgroups = {tag:e.sort_values('t') for tag,e in equity.groupby('tag')}
    existing = pd.read_csv(der/'funding_hourly_sensitivity_accounts.csv')
    account_rows, position_rows, scenarios, margins, summaries = [], [], [], [], []
    cost_bps = (0, 1, 5, 10, 25, 50, 100, 250, 500, 1000)
    shock_pcts = (0, .1, .5, 1, 2, 5, 10, 20)
    mmrs = (.01, .025, .05, .075, .10, 1/6, .25, .50)
    for cutoff in (12,24,48):
        t0 = lo+cutoff*fh.HOUR
        cut_rows, cut_paths, endpoint_vectors, funding_vectors = [], [], [], []
        after = hours>t0
        for tag,w in panel[panel.t.between(t0,hi)].groupby('tag'):
            grid = np.sort(w.t.unique())
            assert grid[0] == t0 and grid[-1] == hi
            e = eqgroups[tag]
            freeze = e[e.t.le(t0)].iloc[-1]
            end = e[e.t.le(hi)].iloc[-1]
            inherited = float(actual_payments[tag][hours<=t0].sum())
            start_eq = float(freeze.equity-freeze.funding+inherited)
            actual = float(accounts.loc[tag,'equity_change']-end.funding+actual_payments[tag].sum())
            mtm, gross, frozen_funding = np.zeros(len(grid)), np.zeros(len(grid)), np.zeros(len(hours))
            qf, qa, pt, funding_gap = [], [], [], []
            for coin in coins:
                cg = w[w.coin.eq(coin)].sort_values('t')
                assert np.array_equal(cg.t.to_numpy(),grid)
                q0, qend = float(cg.signed_size.iloc[0]), float(cg.signed_size.iloc[-1])
                p = cg.px.to_numpy(float)
                if q0 != 0:
                    fh.finite(p,(tag,coin,'frozen path'))
                    mtm += q0*(p-p[0]); gross += np.abs(q0*p)
                    frozen_funding[after] += q0*unit[coin][after]
                fh.finite(p[-1:],(tag,coin,'terminal price'))
                qf.append(q0); qa.append(qend); pt.append(p[-1])
                qpath = fh.position_path(positions[(tag,coin)],hours) if (tag,coin) in positions else np.zeros(len(hours))
                # Both paths agree before formation, so inherited funding cancels.
                funding_gap.append((q0-qpath[after])*unit[coin][after])
                position_rows.append(dict(freeze_hours=cutoff,tag=tag,coin=coin,
                    frozen_quantity=q0,actual_terminal_quantity=qend,terminal_price=p[-1],
                    frozen_signed_notional=q0*p[-1],actual_signed_notional=qend*p[-1],
                    differential_signed_notional=(q0-qend)*p[-1]))
            funded = start_eq+mtm+fh.at_times(hours,frozen_funding.cumsum(),grid,side='right',initial=0.)
            fh.finite(funded,(tag,'funded path'))
            qf,qa,pt = np.array(qf),np.array(qa),np.array(pt)
            diffvector = (qf-qa)*pt
            fundvector = np.array(funding_gap)
            held = float(funded[-1]-fh.CAPITAL)
            prev = existing[(existing.freeze_hours==cutoff)&(existing.tag==tag)].iloc[0]
            assert abs(held-prev.proxy_hold_net)<1e-6
            assert abs(actual-prev.proxy_actual_net)<1e-6
            ratio = np.divide(funded,gross,out=np.full_like(gross,np.inf),where=gross>0)
            row = dict(freeze_hours=cutoff,tag=tag,model=accounts.loc[tag,'model'],
                arm=int(accounts.loc[tag,'competition_id']),frozen_net=held,actual_net=actual,
                gap_dollars=held-actual,frozen_gross_terminal=float(np.abs(qf*pt).sum()),
                actual_gross_terminal=float(np.abs(qa*pt).sum()),
                endpoint_error_gap_l1=float(np.abs(diffvector).sum()),
                funding_error_gap_l1=float(np.abs(fundvector).sum()),
                min_aggregate_equity_to_gross=finite_scalar(ratio.min()),
                max_gross_notional=float(gross.max()),
                minimum_account_equity=float(funded.min()),
                grid_points=len(grid))
            cut_rows.append(row); cut_paths.append((funded,gross))
            endpoint_vectors.append(diffvector); funding_vectors.append(fundvector)
        d = pd.DataFrame(cut_rows)
        account_rows.extend(cut_rows)
        book = len(d)*fh.CAPITAL
        gap = float(d.gap_dollars.sum())
        total_frozen = float(d.frozen_gross_terminal.sum())
        total_actual = float(d.actual_gross_terminal.sum())
        ep = np.array(endpoint_vectors)
        fv = np.array(funding_vectors)
        # One common price perturbation per asset, adverse to aggregate gap.
        common_ep_direction = -np.sign(ep.sum(axis=0))
        common_ep_loss = float(np.abs(ep.sum(axis=0)).sum())
        common_fund_loss = float(np.abs(fv.sum(axis=0)).sum())
        separate_ep_loss = float(np.abs(ep).sum())
        separate_fund_loss = float(np.abs(fv).sum())
        for bps in cost_bps:
            for convention in ('frozen_only','both_books'):
                c=bps/10000
                frozen = d.frozen_net-c*d.frozen_gross_terminal
                actual = d.actual_net-(c*d.actual_gross_terminal if convention=='both_books' else 0)
                scenarios.append(dict(freeze_hours=cutoff,scenario='terminal_friction',
                    convention=convention,stress_bps=bps,stress_pct=None,
                    frozen_return_pct=100*float(frozen.sum())/book,
                    actual_return_pct=100*float(actual.sum())/book,
                    advantage_pp=100*float((frozen-actual).sum())/book,
                    accounts_ahead=int((frozen>actual).sum())))
        for pct in shock_pcts:
            delta=pct/100
            common_loss = -(ep*common_ep_direction).sum(axis=1)*delta
            independent_loss=d.endpoint_error_gap_l1*delta
            for convention,loss in (('common_market_adverse',common_loss),('accountwise_lower_bounds',independent_loss)):
                gapvec=d.gap_dollars-loss
                scenarios.append(dict(freeze_hours=cutoff,scenario='endpoint_price_error',
                    convention=convention,stress_bps=None,stress_pct=pct,
                    frozen_return_pct=None,actual_return_pct=None,
                    advantage_pp=100*float(gapvec.sum())/book,
                    accounts_ahead=int((gapvec>0).sum())))
            for mmr in mmrs:
                breaches=0
                for funded,gross in cut_paths:
                    # Conservative bound for any <=delta proportional price
                    # perturbation at a grid point: equity >= E-delta*N,
                    # gross <= (1+delta)*N. This is a sufficient aggregate
                    # collateral buffer screen, not an isolated margin replay.
                    breaches += bool(((funded-delta*gross)<mmr*(1+delta)*gross).any())
                margins.append(dict(freeze_hours=cutoff,price_error_bound_pct=pct,
                    assumed_aggregate_mmr=mmr,accounts_failing_buffer_screen=breaches,
                    accounts=len(d)))
        summaries.append(dict(freeze_hours=cutoff,accounts=len(d),
            frozen_return_pct=100*float(d.frozen_net.sum())/book,
            actual_return_pct=100*float(d.actual_net.sum())/book,
            gap_dollars=gap,advantage_pp=100*gap/book,
            accounts_ahead=int((d.gap_dollars>0).sum()),
            frozen_terminal_gross=total_frozen,actual_terminal_gross=total_actual,
            frozen_only_break_even_friction_bps=10000*gap/total_frozen,
            symmetric_break_even_friction_bps=10000*gap/(total_frozen-total_actual)
                if total_frozen>total_actual else None,
            endpoint_error_common_market_l1=common_ep_loss,
            endpoint_error_accountwise_l1=separate_ep_loss,
            endpoint_common_market_break_even_pct=100*gap/common_ep_loss,
            endpoint_accountwise_bound_break_even_pct=100*gap/separate_ep_loss,
            funding_error_common_market_l1=common_fund_loss,
            funding_error_accountwise_l1=separate_fund_loss,
            funding_oracle_10pct_common_error_gap_lower_bound_pp=100*(gap-.1*common_fund_loss)/book,
            funding_oracle_10pct_accountwise_error_gap_lower_bound_pp=100*(gap-.1*separate_fund_loss)/book,
            minimum_aggregate_equity_to_gross=float(d.min_aggregate_equity_to_gross.min()),
            positive_gap_accounts_with_zero_frozen_exposure=int(((d.gap_dollars>0)&d.frozen_gross_terminal.eq(0)).sum())))
    f=fills[fills.time.between(lo,hi)]
    fill_bps=10000*f.fee/(f.px*f.sz)
    empirical_fees=dict(recorded_fees=float(f.fee.sum()),traded_notional=float((f.px*f.sz).sum()),
        notional_weighted_fee_bps=float(10000*f.fee.sum()/(f.px*f.sz).sum()),
        fill_fee_bps_quantiles={str(q):float(fill_bps.quantile(q)) for q in (0,.25,.5,.75,.95,1)},
        interpretation='Observed fees only; excludes spread, impact and hypothetical closing liquidity.')
    terminal_price_coverage=[]
    for coin,(times,values) in prices.items():
        idx=np.searchsorted(times,hi,side='right')-1
        terminal_price_coverage.append(dict(coin=coin,terminal_pooled_price=float(values[idx]),
            last_fill_timestamp_ms=int(times[idx]),age_minutes=float((hi-times[idx])/60000)))
    report=dict(specification='Hourly-funding pooled-price-proxy accounting comparison, Season 1.5',
        freeze_hours=[12,24,48],primary_freeze_hours=24,
        numerical_reproduction='All 96 frozen/actual endpoint pairs match existing hourly-funding output within 1e-6 USD.',
        definitions=dict(terminal_friction='c times gross terminal notional; frozen_only leaves actual marked, both_books charges both.',
            endpoint_price_error='Revalue both terminal books by the same per-asset price perturbation. Common-market direction minimizes aggregate paired gap; accountwise bounds allow different worst directions and need not be simultaneously attainable.',
            funding_price_error='Keep recorded hourly rates fixed; bound changes in funding-gap cash flows from proportional errors in oracle proxy. Pre-formation contributions cancel.',
            margin_screen='Minimum hourly-funded account equity / frozen gross on five-minute pooled-print grid; conservative bounded-price-error version. No isolated collateral or actual tier schedule.'),
        limitations=['This is not a tested trading strategy or a causal effect of trading.',
            'The formation choices are retrospective; 32 accounts share one market path.',
            'Funding uses actual rates but pooled fills in place of historical oracle prices.',
            'Terminal prices and grid marks are pooled fills, possibly stale.',
            'No complete historical mark/oracle series, margin-mode changes, isolated collateral allocations or order-book replay is present.',
            'Current API documentation illustrates strict-isolated XYZ markets; account-wide equity cannot certify per-position isolated solvency.',
            'No margin screen here establishes executable performance or excludes intra-grid liquidation.',
            'Stress magnitudes are hypothetical; thresholds are conditional break-even amounts, not confidence intervals.'],
        empirical_fee_context=empirical_fees,terminal_price_coverage=terminal_price_coverage,summaries=summaries,
        input_sha256={str(p.relative_to(root)):digest(p) for p in paths+rate_paths+[der/'funding_hourly_sensitivity_accounts.csv']},
        source_sha256={str(p.relative_to(root)):digest(p) for p in [Path(__file__),HERE/'funding_hourly_sensitivity.py',HERE/'wallets.py']})
    out.mkdir(parents=True,exist_ok=True)
    for name,rows in [('accounts',account_rows),('positions',position_rows),('scenarios',scenarios),('margin_screens',margins)]:
        pd.DataFrame(rows).to_csv(out/f'frozen_book_robustness_{name}.csv',index=False)
    (out/'frozen_book_robustness.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(summaries=summaries,empirical_fee_context=empirical_fees),indent=2))


if __name__=='__main__':
    main()
