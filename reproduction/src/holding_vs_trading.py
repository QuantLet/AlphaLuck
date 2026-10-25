"""Holding versus trading: costs, market exposure and leaderboard ranks.

Run: python src/holding_vs_trading.py [--draws N]

Three additions to the frozen-book comparison of the letter (Section 3.2),
all on the primary specification of src/funding_hourly_sensitivity.py
(hourly funding rates, pooled trade prices as the oracle proxy, freeze after
24 hours, Season 1.5, 32 accounts):

1. Cost split. Both books inherit the same equity at formation, so the
   advantage is the difference of their post-formation results:
       hold - actual = (M - T) + F + (U_hold - U_actual),
   M the frozen book's mark-to-market gain, T the realised book's trading
   gain before fees and funding, F the fees the realised book pays after
   formation (the frozen book trades no more), U the hourly-proxy funding of
   each book after formation. M - T is the advantage before costs.

2. Exposure. The frozen and realised books carry different exposure after
   formation, so part of the advantage can be market drift.
   * gross-matched: each frozen book is scaled by k = mean realised gross
     notional / mean frozen gross notional over (t0, close] on the
     five-minute grid; its post-formation result is multiplied by k. An
     account that is flat at formation has nothing to scale and keeps 0.
     Nearly flat books get very large k, so a pooled variant applies one k,
     from the summed gross notionals, to every account;
   * index-hedged: each book is charged sum_t N_t (I_{t+1} / I_t - 1) on the
     grid, N_t its net notional and I the pooled price of xyz:XYZ100, the
     traded index perpetual. This removes a unit-beta market component from
     both books; it is not an estimated factor model;
   * the index return from formation to the close, and over the 72- and
     168-hour windows of every formation hour of
     data/derived/organiser_hourly_sweep.csv, with its rank correlation with
     the advantage over the same window (when that file is present).

3. Deviations. The advantage before costs, per account and instrument, is
       q0 (P_T - P_0) - T_c,
   T_c the realised trading result before costs in that instrument after
   formation, exact from fills: q_T P_T - q0 P_0 - sum of signed fill size
   times fill price. On the five-minute grid the realised position q_t
   differs from q0 by d_t = q_t - q0, split exactly (split_deviation) into
   a reduction towards zero, an addition beyond q0, a reversal through zero
   and, for instruments flat at formation, a new position. Each part earns
   sum_t part_t (P_{t+1} - P_t); what the grid misses -- execution away from
   the grid prices and timing within five-minute intervals, liquidation fills
   included -- is the remainder T_c minus the grid result. The per-instrument
   terms add to the account's advantage before costs up to the equity
   ledger's rounding (checked).

4. Ranks. The organiser's leaderboard aggregates a model over its four arms.
   Model return = mean over arms of final P&L on initial capital: the
   opening three hours to the first date-end, held fixed, plus the 14
   date-end changes. Common blocks of those dates (overlapping, non-circular,
   lengths 1-3, as in paper/frl/paired_denominator_sensitivity.py) are drawn
   for all 32 accounts together and the eight models re-ranked. The ranges
   are resampling ranges conditional on this market path, not confidence
   intervals with established coverage from fourteen observations.

Writes data/derived/holding_vs_trading{.json,_accounts.csv,_deviations.csv,
_ranks.csv} and
paper/frl/holding_numbers.tex.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

import funding_hourly_sensitivity as fhs  # noqa: E402
import wallets  # noqa: E402

HOUR = fhs.HOUR
DAY = fhs.DAY
CAPITAL = fhs.CAPITAL
FORM_HOURS = 24
INDEX = 'xyz:XYZ100'
SEED = 20261022
BLOCKS = (1, 2, 3)


def arguments():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', type=Path, default=ROOT)
    ap.add_argument('--draws', type=int, default=20000)
    args = ap.parse_args()
    if args.draws < 1000:
        raise ValueError('Use at least 1,000 resampling draws')
    return args


def hedge_charge(net, index):
    """sum_t N_t (I_{t+1} / I_t - 1) over consecutive grid points."""
    net, index = np.asarray(net, float), np.asarray(index, float)
    return float(np.sum(net[:-1] * (index[1:] / index[:-1] - 1)))


def gross_scale(actual_gross, frozen_gross):
    """Ratio of mean gross notionals; 1 for a book flat at formation."""
    f = float(np.mean(frozen_gross))
    return float(np.mean(actual_gross)) / f if f > 0 else 1.0


def split_deviation(q, q0):
    """Split d = q - q0 into reduction, addition, reversal and new parts."""
    q = np.asarray(q, float)
    if q0 == 0:
        z = np.zeros_like(q)
        return {'reduce': z, 'add': z, 'reverse': z, 'new': q.copy()}
    s, x0, x = np.sign(q0), abs(q0), q * np.sign(q0)
    return {'reduce': s * np.where(x >= 0, np.minimum(x, x0) - x0, -x0),
            'add': s * np.maximum(x - x0, 0.0),
            'reverse': s * np.minimum(x, 0.0),
            'new': np.zeros_like(q)}


DEV_PARTS = ('reduce', 'add', 'reverse', 'new', 'execution')


def deviations(root, d, cutoff=FORM_HOURS, step=1):
    """Advantage before costs by account, instrument and kind of deviation.

    step thins the five-minute grid to every step-th point (the close kept);
    what a coarser grid misses moves into the execution residual."""
    der = root / 'data/derived'
    lo, hi = wallets.S15_START_MS, wallets.S15_OFFICIAL_END_MS
    t0 = lo + cutoff * HOUR
    fills = pd.read_parquet(der / 'fills.parquet')
    fills = fills[(fills['season'] == 'S15') & (fills['time'] > t0) & (fills['time'] <= hi)]
    flow = (fills['signed_sz'] * fills['px']).groupby([fills['tag'], fills['coin']]).sum()
    pan = pd.read_parquet(der / 'panel.parquet')
    w = pan[(pan['season'] == 'S15') & pan['t'].between(t0, hi)]
    rows = []
    for (tag, coin), c in w.groupby(['tag', 'coin']):
        c = c.sort_values('t')
        keep = np.unique(np.r_[np.arange(0, len(c), step), len(c) - 1])
        c = c.iloc[keep]
        q, px = c['signed_size'].to_numpy(float), c['px'].to_numpy(float)
        if not (q != 0).any() and (tag, coin) not in flow.index:
            continue
        fhs.finite(px, (tag, coin, 'deviation path'))
        q0, dp = q[0], np.diff(px)
        parts = {k: -float(np.sum(v[:-1] * dp)) for k, v in split_deviation(q, q0).items()}
        realised = q[-1] * px[-1] - q0 * px[0] - float(flow.get((tag, coin), 0.0))
        frozen = q0 * (px[-1] - px[0])
        parts['execution'] = -(realised - frozen + sum(parts.values()))
        rows.append({'tag': tag, 'coin': coin, 'q0': q0, 'frozen_mtm': frozen,
                     'realised_trading': realised, 'gap': frozen - realised, **parts})
    r = pd.DataFrame(rows)
    if (r[list(DEV_PARTS)].sum(axis=1) - r['gap']).abs().max() > 1e-6:
        raise ValueError('Deviation parts do not add up')
    per = r.groupby('tag')['gap'].sum().reindex(d.index)
    residual = float((per - d['advantage_before_costs']).abs().max())
    if residual > 10.0:   # US dollars per account, ledger rounding and tips
        raise ValueError(f'Deviations do not reproduce the advantage before costs: {residual}')
    return r, residual


def summarise_deviations(r, residual, n_accounts):
    book = CAPITAL * n_accounts
    top = r['gap'].sort_values(ascending=False)
    by_coin = (100 * r.groupby('coin')['gap'].sum() / book).sort_values()
    return {
        **{f'{k}_pp': 100 * float(r[k].sum()) / book for k in DEV_PARTS},
        'total_pp': 100 * float(r['gap'].sum()) / book,
        'pairs': len(r), 'pairs_positive': int((r['gap'] > 0).sum()),
        'top10_share': float(top.head(10).sum() / r['gap'].sum()),
        'by_coin_pp': by_coin.to_dict(),
        'max_abs_residual_usd': residual,
    }


GRID_STEPS = {'15min': 3, '1h': 12, '4h': 48}


def grid_robustness(root, d):
    """Deviation parts on coarser grids, in percentage points of capital."""
    book = CAPITAL * len(d)
    out = {}
    for name, step in GRID_STEPS.items():
        r, _ = deviations(root, d, step=step)
        out[name] = {k: 100 * float(r[k].sum()) / book for k in DEV_PARTS}
    return out


def leave_one_out(d, dev_rows, root):
    """Advantage without each model (four accounts) and each instrument."""
    cols = {'advantage': d['advantage'], 'before_costs': d['advantage_before_costs']}
    sweep = root / 'data/derived/organiser_hourly_sweep_accounts.csv'
    if sweep.exists():
        a = pd.read_csv(sweep)
        a = a[a['formation_hour'] == FORM_HOURS].set_index('tag').reindex(d.index)
        for c in ('A', 'B'):
            cols[f'isolated_{c}'] = a[f'isolated_net_{c}'] - a['actual_net']
    rows = []
    for model in sorted(d['model'].unique()):
        keep = d['model'] != model
        rows.append({'drop': 'model', 'name': model, 'accounts': int(keep.sum()),
                     **{k: 100 * float(v[keep].sum()) / (CAPITAL * keep.sum())
                        for k, v in cols.items()},
                     **{f'{k}_ahead': int((v[keep] > 0).sum()) for k, v in cols.items()}})
    book = CAPITAL * len(d)
    total = dev_rows['gap'].sum()
    for coin, g in dev_rows.groupby('coin'):
        rows.append({'drop': 'instrument', 'name': coin, 'accounts': len(d),
                     'before_costs': 100 * float(total - g['gap'].sum()) / book})
    return pd.DataFrame(rows)


def moving_blocks(n, length, draws, rng):
    """Overlapping non-circular moving blocks, truncated to n dates."""
    count = (n + length - 1) // length
    starts = rng.integers(0, n - length + 1, size=(draws, count))
    return (starts[..., None] + np.arange(length)).reshape(draws, -1)[:, :n]


def model_totals(pnl, opening):
    """pnl: (..., day, model, arm), opening: (model, arm) -> model returns."""
    return (opening + pnl.sum(axis=-3)).mean(axis=-1)


def model_ranks(total):
    """Ranks along the last axis, 1 = highest return."""
    return (-total).argsort(axis=-1).argsort(axis=-1) + 1


def books(root, cutoff=FORM_HOURS):
    """Per-account post-formation components of both books."""
    der, ext = root / 'data/derived', root / 'data/external/funding'
    lo, hi = wallets.S15_START_MS, wallets.S15_OFFICIAL_END_MS
    t0 = lo + cutoff * HOUR
    hours = np.arange(lo, hi + 1, HOUR)
    frames = {n: pd.read_parquet(der / f'{n}.parquet')
              for n in ('fills', 'panel', 'equity', 'accounts')}
    fills, pan, eq, accounts = (f[f['season'] == 'S15'] for f in frames.values())
    accounts = accounts.set_index('tag')
    rates, _ = fhs.load_rates(ext)
    positions, prices = fhs.data_groups(fills)
    unit = {}
    for coin in sorted(prices):
        rate, price = fhs.hourly_market(coin, hours, rates, prices)
        unit[coin] = -price * rate
    pay = fhs.actual_payments(accounts.index, prices, hours, positions, unit)

    w = pan[pan['t'].between(t0, hi)]
    grid = np.sort(w['t'].unique())
    if grid[0] != t0:
        raise ValueError('Freeze timestamp is absent from the grid')
    index = (w[w['coin'] == INDEX].drop_duplicates('t').set_index('t')['px']
             .reindex(grid).to_numpy(float))
    fhs.finite(index, 'index path')
    later = hours > t0
    rows = []
    for tag, a in w.groupby('tag'):
        e = eq[eq['tag'] == tag].sort_values('t')
        freeze, end = e[e['t'] <= t0].iloc[-1], e[e['t'] <= hi].iloc[-1]
        eq0 = freeze['equity'] - freeze['funding'] + float(pay[tag][hours <= t0].sum())
        actual = accounts.loc[tag, 'equity_change'] - end['funding'] + pay[tag].sum()
        fees = float(fills.loc[(fills['tag'] == tag) & (fills['time'] > freeze['t'])
                               & (fills['time'] <= end['t']), 'fee'].sum())
        u_actual = float(pay[tag][later].sum())
        m = np.zeros(len(grid))
        frozen_net, frozen_gross = np.zeros(len(grid)), np.zeros(len(grid))
        u_hold = 0.0
        for coin, c in a.groupby('coin'):
            c = c.sort_values('t')
            q = float(c['signed_size'].iloc[0])
            if q == 0:
                continue
            px = c['px'].to_numpy(float)
            fhs.finite(px, (tag, coin, 'frozen mark path'))
            m += q * (px - px[0])
            frozen_net += q * px
            frozen_gross += abs(q) * px
            u_hold += float(q * unit[coin][later].sum())
        notional = a.pivot(index='t', columns='coin', values='signed_notional').fillna(0.0)
        actual_net = notional.sum(axis=1).reindex(grid).to_numpy(float)
        actual_gross = notional.abs().sum(axis=1).reindex(grid).to_numpy(float)
        post_actual = actual - (eq0 - CAPITAL)
        k = gross_scale(actual_gross, frozen_gross)
        rows.append({
            'tag': tag, 'model': a['model'].iloc[0],
            'arm': int(a['competition_id'].iloc[0]),
            'hold_net': eq0 - CAPITAL + m[-1] + u_hold, 'actual_net': actual,
            'hold_mtm': m[-1], 'actual_trading': post_actual + fees - u_actual,
            'fees_after': fees, 'funding_hold': u_hold, 'funding_actual': u_actual,
            'gross_scale': k, 'hold_net_matched': eq0 - CAPITAL + k * (m[-1] + u_hold),
            'hedge_hold': hedge_charge(frozen_net, index),
            'hedge_actual': hedge_charge(actual_net, index),
            'mean_gross_hold': float(frozen_gross.mean()),
            'mean_gross_actual': float(actual_gross.mean()),
            'mean_net_hold': float(frozen_net.mean()),
            'mean_net_actual': float(actual_net.mean()),
        })
    d = pd.DataFrame(rows).set_index('tag')
    d['advantage'] = d['hold_net'] - d['actual_net']
    d['advantage_before_costs'] = d['hold_mtm'] - d['actual_trading']
    d['advantage_matched'] = d['hold_net_matched'] - d['actual_net']
    d['advantage_hedged'] = d['advantage'] - d['hedge_hold'] + d['hedge_actual']
    gap = (d['advantage_before_costs'] + d['fees_after']
           + d['funding_hold'] - d['funding_actual'] - d['advantage'])
    if gap.abs().max() > 1e-6:
        raise ValueError(f'Cost split does not add up: {gap.abs().max()}')
    return d, float(index[-1] / index[0] - 1)


def index_windows(root):
    """Index return over each sweep window, against the advantage there."""
    sweep_path = root / 'data/derived/organiser_hourly_sweep.csv'
    if not sweep_path.exists():
        return None
    from scipy import stats
    pan = pd.read_parquet(root / 'data/derived/panel.parquet')
    i = (pan[(pan['season'] == 'S15') & (pan['coin'] == INDEX)]
         .drop_duplicates('t').set_index('t')['px'].sort_index().ffill())
    lo = wallets.S15_START_MS
    sweep = pd.read_csv(sweep_path)
    out = {}
    for h in (72, 168):
        s = sweep.dropna(subset=[f'advantage_pp_{h}h'])
        start = lo + s['formation_hour'].to_numpy() * HOUR
        r = 100 * (i.reindex(start + h * HOUR).to_numpy() / i.reindex(start).to_numpy() - 1)
        rho = stats.spearmanr(r, s[f'advantage_pp_{h}h']).statistic
        out[f'{h}h'] = {'formations': len(s), 'index_median_pct': float(np.median(r)),
                        'index_min_pct': float(r.min()), 'index_max_pct': float(r.max()),
                        'index_negative': int((r < 0).sum()),
                        'spearman_with_advantage': float(rho)}
    return out


def ranks(root, draws):
    der = root / 'data/derived'
    lo, hi = wallets.S15_START_MS, wallets.S15_OFFICIAL_END_MS
    eq = pd.read_parquet(der / 'equity.parquet')
    e = eq[(eq['season'] == 'S15') & eq['t'].between(lo, hi)].copy()
    e['day'] = e['t'] // DAY
    ends = e.sort_values('t').groupby(['tag', 'day'])['equity'].last().unstack()
    meta = e.groupby('tag')[['model', 'competition_id']].first()
    order = meta.reset_index().sort_values(['model', 'competition_id'])
    models = sorted(meta['model'].unique())
    ends = ends.loc[order['tag']]
    pnl = ends.diff(axis=1).iloc[:, 1:].to_numpy().T / CAPITAL
    n = pnl.shape[0]
    pnl = pnl.reshape(n, len(models), 4)
    opening = (ends.iloc[:, 0].to_numpy() / CAPITAL - 1).reshape(len(models), 4)
    final = (ends.iloc[:, -1].to_numpy() / CAPITAL - 1).reshape(len(models), 4)
    np.testing.assert_allclose(opening + pnl.sum(axis=0), final, atol=1e-12)
    observed = model_ranks(model_totals(pnl, opening))
    rows, pairs = [], {}
    for length in BLOCKS:
        ids = moving_blocks(n, length, draws, np.random.default_rng(SEED + length))
        total = model_totals(pnl[ids], opening)
        r = model_ranks(total)
        for j, model in enumerate(models):
            rows.append({'block_days': length, 'model': model,
                         'return_pct': 100 * final[j].mean(), 'rank': int(observed[j]),
                         'rank_lo': float(np.quantile(r[:, j], .025, method='inverted_cdf')),
                         'rank_hi': float(np.quantile(r[:, j], .975, method='inverted_cdf')),
                         'p_first': float((r[:, j] == 1).mean()),
                         'p_positive': float((total[:, j] > 0).mean())})
        wins = total[:, :, None] > total[:, None, :]
        beats = wins.mean(axis=0)
        sep = [(a, b) for a in range(len(models))
               for b in range(len(models)) if a != b and beats[a, b] >= .975]
        # share of draws in which every individually separated pair holds at
        # once: the individual 97.5% thresholds carry no joint guarantee
        joint = float(np.all([wins[:, a, b] for a, b in sep], axis=0).mean()) if sep else None
        pairs[length] = {'separated_pairs': len(sep),
                         'pairs': [(models[a], models[b]) for a, b in sep],
                         'joint_frequency': joint,
                         'beats': pd.DataFrame(beats, index=models, columns=models)}
    return pd.DataFrame(rows), pairs


def summarise(d, index_close):
    book = CAPITAL * len(d)
    pp = lambda x: 100 * float(x.sum()) / book  # noqa: E731
    pooled = float(d['mean_gross_actual'].sum() / d['mean_gross_hold'].sum())
    return {
        'accounts': len(d), 'freeze_hours': FORM_HOURS,
        'hold_pct': pp(d['hold_net']), 'actual_pct': pp(d['actual_net']),
        'advantage_pp': pp(d['advantage']),
        'fees_after_pp': pp(d['fees_after']),
        'funding_diff_pp': pp(d['funding_hold'] - d['funding_actual']),
        'advantage_before_costs_pp': pp(d['advantage_before_costs']),
        'ahead': int((d['advantage'] > 0).sum()),
        'ahead_before_costs': int((d['advantage_before_costs'] > 0).sum()),
        'gross_scale_median': float(d['gross_scale'].median()),
        'mean_gross_hold_pct': pp(d['mean_gross_hold']),
        'mean_gross_actual_pct': pp(d['mean_gross_actual']),
        'mean_net_hold_pct': pp(d['mean_net_hold']),
        'mean_net_actual_pct': pp(d['mean_net_actual']),
        'hold_matched_pct': pp(d['hold_net_matched']),
        'gross_scale_max': float(d['gross_scale'].max()),
        'gross_scale_pooled': pooled,
        'advantage_matched_pooled_pp': pp(
            d['advantage'] + (pooled - 1) * (d['hold_mtm'] + d['funding_hold'])),
        'advantage_matched_pp': pp(d['advantage_matched']),
        'ahead_matched': int((d['advantage_matched'] > 0).sum()),
        'hedge_hold_pp': pp(d['hedge_hold']), 'hedge_actual_pp': pp(d['hedge_actual']),
        'advantage_hedged_pp': pp(d['advantage_hedged']),
        'ahead_hedged': int((d['advantage_hedged'] > 0).sum()),
        'index_return_pct': 100 * index_close,
    }


def fmt(x, d=1):
    s = f'{x:,.{d}f}'.replace(',', '{,}')
    return r'\ensuremath{-}' + s[1:] if s.startswith('-') else s


def write_rank_table(root, p):
    """Pairwise frequencies, two-day blocks: row model beats column model."""
    b = p['beats']
    order = b.mean(axis=1).sort_values(ascending=False).index
    b = b.loc[order, order]
    short = {m: m.split('-')[0].replace('deepseek', 'DeepSeek').replace('claude', 'Claude')
             .replace('gemini', 'Gemini').replace('grok', 'Grok').replace('kimi', 'Kimi')
             .replace('qwen3', 'Qwen3').replace('gpt', 'GPT-5.1').replace('typhoon', 'Typhoon')
             for m in order}
    lines = ['% Generated by src/holding_vs_trading.py',
             r'\begin{tabular}{l' + 'r' * len(order) + '}', r'\toprule',
             ' & ' + ' & '.join(short[m] for m in order) + r' \\', r'\midrule']
    for a in order:
        cells = []
        for c in order:
            if a == c:
                cells.append('--')
                continue
            v = f'{100 * b.loc[a, c]:.0f}'
            cells.append(rf'\textbf{{{v}}}' if b.loc[a, c] >= .975 else v)
        lines.append(short[a] + ' & ' + ' & '.join(cells) + r' \\')
    lines += [r'\bottomrule', r'\end{tabular}']
    (root / 'paper/frl/rank_pairs.tex').write_text('\n'.join(lines) + '\n')


def write_tex(root, s, windows, rk, pairs, dev, robust):
    names = {'15min': 'Fifteen', '1h': 'Hour', '4h': 'Four'}
    m = {
        **{f'HvtGrid{names[g]}{k.title()}': fmt(v[k]) for g, v in
           robust['deviation_grids_pp'].items() for k in DEV_PARTS},
        **{f'HvtLoo{k.replace("_", " ").title().replace(" ", "")}{e.title()}': fmt(v)
           for e in ('min', 'max') for k, v in robust[f'leave_one_model_{e}'].items()},
        'HvtLooPltr': fmt(robust['leave_one_instrument_before_costs']['xyz:PLTR']),
        'HvtLooInstrMin': fmt(min(robust['leave_one_instrument_before_costs'].values())),
        'HvtRankJointTwo': fmt(100 * pairs[2]['joint_frequency'], 0),
        'HvtDevReduce': fmt(dev['reduce_pp']), 'HvtDevAdd': fmt(dev['add_pp']),
        'HvtDevReverse': fmt(dev['reverse_pp']), 'HvtDevNew': fmt(dev['new_pp']),
        'HvtDevExec': fmt(dev['execution_pp']), 'HvtDevTotal': fmt(dev['total_pp']),
        'HvtDevPairs': str(dev['pairs']), 'HvtDevPairsPositive': str(dev['pairs_positive']),
        'HvtDevTopTen': fmt(100 * dev['top10_share'], 0),
        **{f"HvtDevCoin{''.join(ch for ch in coin.split(':')[-1] if ch.isalpha()).title()}": fmt(v)
           for coin, v in dev['by_coin_pp'].items()},
        'HvtLoss': fmt(-s['actual_pct']), 'HvtAdv': fmt(s['advantage_pp']), 'HvtFees': fmt(s['fees_after_pp']),
        'HvtFundDiff': fmt(s['funding_diff_pp']),
        'HvtBeforeCosts': fmt(s['advantage_before_costs_pp']),
        'HvtFeeShare': fmt(100 * s['fees_after_pp'] / s['advantage_pp'], 0),
        'HvtAhead': str(s['ahead']), 'HvtAheadBefore': str(s['ahead_before_costs']),
        'HvtGrossHold': fmt(s['mean_gross_hold_pct'] / 100, 2),
        'HvtGrossActual': fmt(s['mean_gross_actual_pct'] / 100, 2),
        'HvtNetHold': fmt(s['mean_net_hold_pct'] / 100, 2),
        'HvtNetActual': fmt(s['mean_net_actual_pct'] / 100, 2),
        'HvtScaleMedian': fmt(s['gross_scale_median'], 2),
        'HvtMatched': fmt(s['advantage_matched_pp']),
        'HvtAheadMatched': str(s['ahead_matched']),
        'HvtScaleMax': fmt(s['gross_scale_max'], 0),
        'HvtScalePooled': fmt(s['gross_scale_pooled'], 2),
        'HvtMatchedPooled': fmt(s['advantage_matched_pooled_pp']),
        'HvtHedged': fmt(s['advantage_hedged_pp']),
        'HvtAheadHedged': str(s['ahead_hedged']),
        'HvtIndex': fmt(s['index_return_pct']),
    }
    if windows:
        for h, name in (('72h', 'Three'), ('168h', 'Week')):
            w = windows[h]
            m[f'HvtIndex{name}Median'] = fmt(w['index_median_pct'])
            m[f'HvtIndex{name}Min'] = fmt(w['index_min_pct'])
            m[f'HvtIndex{name}Max'] = fmt(w['index_max_pct'])
            m[f'HvtIndex{name}Rho'] = fmt(w['spearman_with_advantage'], 2)
    words = {1: 'One', 2: 'Two', 3: 'Three'}
    for length, p in pairs.items():
        m[f'HvtRankPairs{words[length]}'] = str(p['separated_pairs'])
    two = rk[rk['block_days'] == 2].set_index('model')
    for model, r in two.iterrows():
        key = ''.join(ch for ch in model.title() if ch.isalpha())
        m[f'HvtRank{key}Lo'] = f"{r['rank_lo']:.0f}"
        m[f'HvtRank{key}Hi'] = f"{r['rank_hi']:.0f}"
        m[f'HvtRank{key}First'] = fmt(100 * r['p_first'], 0)
    lines = ['% Generated by src/holding_vs_trading.py']
    lines += [rf'\newcommand{{\al{k}}}{{{v}}}' for k, v in m.items()]
    (root / 'paper/frl/holding_numbers.tex').write_text('\n'.join(lines) + '\n')


def main():
    args = arguments()
    root = args.root.resolve()
    d, index_close = books(root)
    ref = pd.read_csv(root / 'data/derived/funding_hourly_sensitivity_accounts.csv')
    ref = ref[ref['freeze_hours'] == FORM_HOURS].set_index('tag').loc[d.index]
    np.testing.assert_allclose(d['hold_net'], ref['proxy_hold_net'], atol=1e-6)
    np.testing.assert_allclose(d['actual_net'], ref['proxy_actual_net'], atol=1e-6)
    s = summarise(d, index_close)
    dev_rows, residual = deviations(root, d)
    dev = summarise_deviations(dev_rows, residual, len(d))
    grid = grid_robustness(root, d)
    loo = leave_one_out(d, dev_rows, root)
    windows = index_windows(root)
    rk, pairs = ranks(root, args.draws)
    der = root / 'data/derived'
    d.to_csv(der / 'holding_vs_trading_accounts.csv')
    dev_rows.to_csv(der / 'holding_vs_trading_deviations.csv', index=False)
    rk.to_csv(der / 'holding_vs_trading_ranks.csv', index=False)
    loo.to_csv(der / 'holding_vs_trading_leave_one_out.csv', index=False)
    pairs[2]['beats'].to_csv(der / 'holding_vs_trading_rank_pairs.csv')
    model_loo = loo[loo['drop'] == 'model']
    robust = {'deviation_grids_pp': grid,
              'leave_one_model_min': {k: float(model_loo[k].min()) for k in model_loo
                                      if k in ('advantage', 'before_costs', 'isolated_A', 'isolated_B')},
              'leave_one_model_max': {k: float(model_loo[k].max()) for k in model_loo
                                      if k in ('advantage', 'before_costs', 'isolated_A', 'isolated_B')},
              'leave_one_instrument_before_costs': loo[loo['drop'] == 'instrument']
              .set_index('name')['before_costs'].to_dict()}
    result = {'benchmark': s, 'deviations': dev, 'robustness': robust,
              'index_windows': windows,
              'rank_pairs': {str(k): {**v, 'beats': v['beats'].round(4).to_dict()}
                             for k, v in pairs.items()},
              'draws': args.draws, 'seed': SEED,
              'block_scheme': 'Overlapping non-circular moving blocks of common dates; '
                              'truncate to 14 dates; central 95% ranges.'}
    (der / 'holding_vs_trading.json').write_text(json.dumps(result, indent=1) + '\n')
    write_tex(root, s, windows, rk, pairs, dev, robust)
    write_rank_table(root, pairs[2])
    print(json.dumps(result, indent=1))
    print(rk[rk['block_days'] == 2].to_string(index=False))


if __name__ == '__main__':
    main()
