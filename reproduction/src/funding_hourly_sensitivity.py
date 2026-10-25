"""Audit daily funding aggregates and price an hourly-funding sensitivity.

Run from a repository checkout after rebuilding its derived inputs:
    python src/funding_hourly_sensitivity.py

Defaults: data/derived/*.parquet and data/external/funding/. The external
folder contains fundingHistory_xyz_*.json and user_funding_enriched.parquet
(the latter retains the raw userFunding fields szi and nSamples). --root,
--derived, --external and --output override these paths. No network calls.

This is an oracle-price-proxy sensitivity, not an exact counterfactual:
fundingHistory supplies actual rates, but pooled account fill prices replace
historical oracle prices. Settlement is assigned to the nominal UTC hour
(floor the API timestamp), included through the freeze/close hour. Actual
positions before a settlement use fills strictly before that nominal hour.
The same deterministic pooled-print order as build.price_series is used:
time, tid, px (mergesort); one deterministic final print is retained per coin/timestamp.

Daily funding rows are validated against their constituent hourly positions
and rates. Recorded aggregate funding is removed from both inherited and
realised equity before adding the actual-path hourly proxy. After formation,
only the fixed book receives the proxy funding. Closing costs and actual
liquidation rules remain excluded; margin checks are descriptive proxies.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from scipy import stats

HOUR = 3_600_000
DAY = 86_400_000
CAPITAL = 10_000.0
POSITION_EPS = 1e-7


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path,
                        default=Path(__file__).resolve().parents[1])
    parser.add_argument('--derived', type=Path)
    parser.add_argument('--external', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    args.root = args.root.resolve()
    args.derived = args.derived or args.root / 'data' / 'derived'
    args.external = args.external or args.root / 'data' / 'external' / 'funding'
    args.output = args.output or args.derived
    return args


def at_times(times, values, queries, *, side, initial):
    """Last observation before/at each query, without backward filling."""
    index = np.searchsorted(times, queries, side=side) - 1
    return np.where(index >= 0, values[np.maximum(index, 0)], initial)


def position_path(group, hours):
    times, quantities = group
    q = at_times(times, quantities, hours, side='left', initial=0.0)
    q[np.abs(q) < POSITION_EPS] = 0.0
    return q


def finite(values, context):
    if not np.isfinite(values).all():
        raise ValueError(f'Non-finite values for an active exposure: {context}')


def load_rates(directory):
    paths = sorted(p for p in directory.glob('fundingHistory_xyz_*.json')
                   if not p.name.endswith('.meta.json'))
    if not paths:
        raise FileNotFoundError(f'No fundingHistory_xyz_*.json in {directory}')
    rows = []
    for path in paths:
        payload = json.loads(path.read_text())
        if not isinstance(payload, list):
            raise ValueError(f'Expected an API response list: {path}')
        rows.extend(payload)
    rates = pd.DataFrame(rows).drop_duplicates(['coin', 'time', 'fundingRate'])
    rates['hour'] = rates['time'] // HOUR * HOUR
    rates['rate'] = rates['fundingRate'].astype(float)
    if rates.duplicated(['coin', 'hour']).any():
        raise ValueError('Conflicting or repeated funding rates for a nominal hour')
    return rates, paths


def data_groups(fills):
    ordered = fills.sort_values(['tag', 'coin', 'time', 'tid'], kind='mergesort')
    positions = {
        key: (g['time'].to_numpy(), g['signed_sz'].cumsum().to_numpy())
        for key, g in ordered.groupby(['tag', 'coin'])
    }
    # Duplicate wallet views of one market print must not select a new mark.
    prints = (fills.sort_values(['time', 'tid', 'px'], kind='mergesort')
              .drop_duplicates(['coin', 'time'], keep='last'))
    prices = {coin: (g['time'].to_numpy(), g['px'].to_numpy())
              for coin, g in prints.groupby('coin')}
    return positions, prices


def hourly_market(coin, hours, rates, prices):
    r = rates[rates['coin'] == coin].set_index('hour')['rate'].reindex(hours)
    if r.isna().any():
        raise ValueError(f'Missing hourly funding rates: {coin}')
    times, marks = prices[coin]
    p = at_times(times, marks, hours, side='right', initial=np.nan)
    return r.to_numpy(float), p


def validate_aggregates(raw, positions, prices, rates, lo, hi):
    selected = raw[raw['tag'].str.startswith('S15__')
                   & raw['time'].between(lo, hi)].copy()
    aggregate = selected[selected['nSamples'].notna()]
    rows = []
    for row in aggregate.itertuples():
        hours = row.time + np.arange(24) * HOUR
        q = position_path(positions[(row.tag, row.coin)], hours)
        rate, price = hourly_market(row.coin, hours, rates, prices)
        active = q != 0
        finite(price[active], (row.tag, row.coin, row.time))
        predicted = -float(np.sum(q[active] * price[active] * rate[active]))
        n = int(active.sum())
        mean_q = float(q[active].mean()) if n else 0.0
        sum_q = float(q.sum())
        weighted_rate = (float(np.sum(q * rate) / sum_q)
                         if abs(sum_q) > 1e-12 else np.nan)
        rows.append({
            'tag': row.tag, 'coin': row.coin, 'time': row.time,
            'n_samples': row.nSamples, 'reconstructed_n': n,
            'recorded_szi': row.szi, 'reconstructed_szi': mean_q,
            'szi_error': mean_q - row.szi,
            'weighted_rate_error': weighted_rate - row.funding_rate,
            'actual_usdc': row.usdc, 'predicted_usdc': predicted,
            'dollar_error': predicted - row.usdc,
        })
    result = pd.DataFrame(rows)
    if result.empty:
        raise ValueError('No daily aggregate funding rows in the official window')
    exact = ((result['n_samples'] == result['reconstructed_n'])
             & (result['szi_error'].abs() < 1e-6))
    summary = {
        'funding_rows': len(selected), 'aggregate_rows': len(result),
        'accounts': int(result['tag'].nunique()),
        'hourly_samples': int(result['n_samples'].sum()),
        'position_count_and_mean_matches': int(exact.sum()),
        'max_abs_szi_error': float(result['szi_error'].abs().max()),
        'max_abs_q_weighted_rate_error':
            float(result['weighted_rate_error'].abs().max()),
        'cash_correlation': float(result['actual_usdc'].corr(result['predicted_usdc'])),
        'dollar_mae': float(result['dollar_error'].abs().mean()),
        'dollar_rmse': float(np.sqrt((result['dollar_error'] ** 2).mean())),
        'max_abs_dollar_error': float(result['dollar_error'].abs().max()),
        'actual_usdc_sum': float(result['actual_usdc'].sum()),
        'predicted_usdc_sum': float(result['predicted_usdc'].sum()),
        'net_dollar_error': float(result['dollar_error'].sum()),
    }
    if not exact.all():
        raise ValueError('Aggregate sample count/mean position does not match fills')
    return result, summary


def actual_payments(tags, coins, hours, positions, unit_payments):
    result = {}
    for tag in tags:
        pay = np.zeros(len(hours))
        for coin in coins:
            if (tag, coin) not in positions:
                continue
            q = position_path(positions[(tag, coin)], hours)
            active = q != 0
            finite(unit_payments[coin][active], (tag, coin, 'actual funding'))
            pay[active] += q[active] * unit_payments[coin][active]
        result[tag] = pay
    return result


def replace_funding(eq, hours, payments):
    frames = []
    for tag, group in eq.groupby('tag', sort=False):
        e = group.sort_values('t').copy()
        new = at_times(hours, payments[tag].cumsum(), e['t'].to_numpy(),
                       side='right', initial=0.0)
        e['equity'] = e['equity'] - e['funding'] + new
        e['funding'] = new
        frames.append(e)
    return pd.concat(frames, ignore_index=True)


def volatility_summary(eq, lo, hi, vf):
    e = eq[eq['t'].between(lo, hi)].copy()
    e['day'] = e['t'] // DAY
    dayend = e.sort_values('t').groupby(['tag', 'day'])['equity'].last().unstack()
    volatility = dayend.diff(axis=1).iloc[:, 1:].std(axis=1, ddof=1) / CAPITAL
    meta = e.groupby('tag')[['model', 'competition_id']].first()
    matrix = meta.join(volatility.rename('vol')).pivot(
        index='model', columns='competition_id', values='vol').to_numpy()
    k, arms = matrix.shape
    ranks = np.apply_along_axis(stats.rankdata, 0, matrix)
    W = (12 * ((ranks.sum(axis=1) - arms * (k + 1) / 2) ** 2).sum()
         / (arms ** 2 * (k ** 3 - k)))
    return {'F': vf.anova_icc(matrix)['F_model'], 'W': float(W)}


def benchmark_scenarios(pan, eq, accounts, hours, payments, unit_payments, lo, hi, b):
    rows, summaries = [], []
    equity_groups = {tag: e.sort_values('t') for tag, e in eq.groupby('tag')}
    for cutoff in (12, 24, 48):
        t0 = lo + cutoff * HOUR
        baseline = b.run('S15', form_hours=cutoff).set_index('tag')
        for tag, w in pan[pan['t'].between(t0, hi)].groupby('tag'):
            e = equity_groups[tag]
            freeze = e[e['t'] <= t0].iloc[-1]
            end = e[e['t'] <= hi].iloc[-1]
            actual_fund = payments[tag]
            inherited_fund = float(actual_fund[hours <= t0].sum())
            actual = (accounts.loc[tag, 'equity_change'] - end['funding']
                      + actual_fund.sum())
            grid = np.sort(w['t'].unique())
            if grid[0] != t0:
                raise ValueError(f'Freeze timestamp is absent from grid: {tag}/{cutoff}')
            q0 = w[w['t'] == t0].set_index('coin')['signed_size']
            frozen_fund = np.zeros(len(hours))
            mtm, gross = np.zeros(len(grid)), np.zeros(len(grid))
            for coin, q in q0.items():
                if q == 0:
                    continue
                later = hours > t0
                finite(unit_payments[coin][later], (tag, coin, 'frozen funding'))
                frozen_fund[later] += q * unit_payments[coin][later]
                price = w[w['coin'] == coin].sort_values('t')['px'].to_numpy()
                finite(price, (tag, coin, 'frozen mark path'))
                mtm += q * (price - price[0])
                gross += np.abs(q * price)
            new_eq0 = freeze['equity'] - freeze['funding'] + inherited_fund
            funded_path = new_eq0 + mtm + at_times(
                hours, frozen_fund.cumsum(), grid, side='right', initial=0.0)
            finite(funded_path, (tag, 'equity path'))
            baseline_path = freeze['equity'] + mtm
            row = {
                'freeze_hours': cutoff, 'tag': tag,
                'baseline_hold_net': baseline.loc[tag, 'hold_net'],
                'baseline_actual_net': accounts.loc[tag, 'equity_change'],
                'old_funding_to_freeze': freeze['funding'],
                'proxy_actual_funding_to_freeze': inherited_fund,
                'proxy_frozen_postfreeze_funding': float(frozen_fund.sum()),
                'proxy_hold_net': float(funded_path[-1] - CAPITAL),
                'proxy_actual_net': float(actual),
            }
            for rate in (0.01, 0.025, 0.05):
                row[f'baseline_breach_{rate}'] = bool((baseline_path < rate * gross).any())
                row[f'proxy_breach_{rate}'] = bool((funded_path < rate * gross).any())
            rows.append(row)
        d = pd.DataFrame(rows)
        d = d[d['freeze_hours'] == cutoff]
        book = CAPITAL * len(d)
        item = {'freeze_hours': cutoff, 'accounts': len(d)}
        for prefix in ('baseline', 'proxy'):
            hold = float(d[f'{prefix}_hold_net'].sum())
            actual = float(d[f'{prefix}_actual_net'].sum())
            item[prefix] = {
                'hold_net': hold, 'actual_net': actual,
                'hold_return_pct': 100 * hold / book,
                'actual_return_pct': 100 * actual / book,
                'advantage_dollars': hold - actual,
                'advantage_pp': 100 * (hold - actual) / book,
                'accounts_ahead': int((d[f'{prefix}_hold_net'] > d[f'{prefix}_actual_net']).sum()),
                'margin_proxy_breaches': {
                    str(rate): int(d[f'{prefix}_breach_{rate}'].sum())
                    for rate in (0.01, 0.025, 0.05)},
            }
        item['frozen_postfreeze_funding'] = float(d['proxy_frozen_postfreeze_funding'].sum())
        item['inherited_funding_adjustment'] = float(
            (d['proxy_actual_funding_to_freeze'] - d['old_funding_to_freeze']).sum())
        summaries.append(item)
    return pd.DataFrame(rows), summaries


def main():
    args = arguments()
    sys.path.insert(0, str(args.root / 'src'))
    import wallets
    import exante_benchmark as b
    import vol_fixed_denominator as vf
    b.DER = str(args.derived)
    lo, hi = wallets.S15_START_MS, wallets.S15_OFFICIAL_END_MS
    hours = np.arange(lo, hi + 1, HOUR)
    paths = [args.derived / f'{name}.parquet'
             for name in ('fills', 'panel', 'equity', 'accounts')]
    frames = [pd.read_parquet(path) for path in paths]
    fills, pan, eq, accounts = [frame[frame['season'] == 'S15'] for frame in frames]
    accounts = accounts.set_index('tag')
    raw_path = args.external / 'user_funding_enriched.parquet'
    raw = pd.read_parquet(raw_path)
    rates, rate_paths = load_rates(args.external)
    positions, prices = data_groups(fills)
    validation_rows, validation = validate_aggregates(
        raw, positions, prices, rates, lo, hi)
    unit, coverage = {}, []
    for coin in sorted(prices):
        rate, price = hourly_market(coin, hours, rates, prices)
        unit[coin] = -price * rate
        observed = np.isfinite(price)
        times, _ = prices[coin]
        latest = at_times(times, times, hours[observed], side='right', initial=np.nan)
        ages = (hours[observed] - latest) / 60_000
        coverage.append({
            'coin': coin, 'expected_hours': len(hours),
            'rate_hours': int(np.isfinite(rate).sum()),
            'initial_unpriced_hours': int((~observed).sum()),
            'median_hourly_mark_age_minutes': float(np.median(ages)),
            'max_hourly_mark_age_minutes': float(np.max(ages)),
        })
    pay = actual_payments(accounts.index, prices, hours, positions, unit)
    adjusted_eq = replace_funding(eq, hours, pay)
    account_rows, scenarios = benchmark_scenarios(
        pan, eq, accounts, hours, pay, unit, lo, hi, b)
    report = {
        'scenario': 'Hourly funding rates with pooled account prices as an oracle-price proxy',
        'limitations': 'Sensitivity, not exact valuation. Pooled prints may be stale; '
                       'historical oracle prices, actual liquidation rules, and closing '
                       'costs are not reconstructed.',
        'settlement_convention': 'Floor fundingHistory timestamps to nominal UTC hour; '
                                 'include through freeze/close hour; positions use fills '
                                 'strictly before settlement; frozen funding strictly after freeze.',
        'pooled_price_order': 'time, tid, px; mergesort; last print per coin/time',
        'opening_date_funding_proxy': float(sum(
            p[hours < ((lo // DAY + 1) * DAY)].sum() for p in pay.values())),
        'validation': validation, 'coverage': coverage, 'scenarios': scenarios,
        'volatility': {'baseline': volatility_summary(eq, lo, hi, vf),
                       'proxy': volatility_summary(adjusted_eq, lo, hi, vf)},
        'source_code_sha256': {name: hashlib.sha256((args.root / 'src' / name).read_bytes()).hexdigest()
                               for name in ('funding_hourly_sensitivity.py', 'exante_benchmark.py', 'wallets.py')},
        'input_sha256': {
            str(path.relative_to(args.root)) if path.is_relative_to(args.root) else path.name:
                hashlib.sha256(path.read_bytes()).hexdigest()
            for path in paths + [raw_path] + rate_paths},
    }
    args.output.mkdir(parents=True, exist_ok=True)
    validation_rows.to_csv(args.output / 'funding_hourly_validation.csv', index=False)
    account_rows.to_csv(args.output / 'funding_hourly_sensitivity_accounts.csv', index=False)
    (args.output / 'funding_hourly_sensitivity.json').write_text(
        json.dumps(report, indent=2, allow_nan=False) + '\n')
    # Compatibility output consumed by paper/frl/render_audit_additions.py.
    compatibility = {
        'label': report['scenario'] + '; sensitivity, not exact oracle valuation',
        'results': [{
            'freeze_h': item['freeze_hours'],
            'hold': item['proxy']['hold_net'],
            'actual': item['proxy']['actual_net'],
            'advantage': item['proxy']['advantage_dollars'],
            'better': item['proxy']['accounts_ahead'],
            'frozen_postfreeze_funding': item['frozen_postfreeze_funding'],
            'freeze_funding_adjustment': item['inherited_funding_adjustment'],
            'breaches_025': item['proxy']['margin_proxy_breaches']['0.025'],
            'breaches_05': item['proxy']['margin_proxy_breaches']['0.05'],
        } for item in scenarios],
        'volatility_F': report['volatility']['proxy']['F'],
        'volatility_W': report['volatility']['proxy']['W'],
        'actual_opening_date_funding': report['opening_date_funding_proxy'],
    }
    validation_compatibility = {
        'n': validation['aggregate_rows'],
        'q_weighted_rate_max_error': validation['max_abs_q_weighted_rate_error'],
        'correlation': validation['cash_correlation'],
        'dollar_mae': validation['dollar_mae'],
        'dollar_rmse': validation['dollar_rmse'],
        'max_abs_error': validation['max_abs_dollar_error'],
        'sum_actual': validation['actual_usdc_sum'],
        'sum_predicted': validation['predicted_usdc_sum'],
        'net_difference': validation['net_dollar_error'],
    }
    for name, payload in (
        ('hourly_funding_benchmark_sensitivity.json', compatibility),
        ('hourly_rate_aggregation_validation.json', validation_compatibility),
    ):
        (args.output / name).write_text(json.dumps(payload, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'validation': validation, 'scenarios': scenarios,
                      'volatility': report['volatility']}, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
