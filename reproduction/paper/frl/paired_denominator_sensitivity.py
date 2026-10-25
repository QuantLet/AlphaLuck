"""Descriptive paired sensitivity to the volatility denominator, Season 1.5.

This is NOT a population-model test. There is one observed account per model
and arm. Common blocks of recorded dates reweight the same 32 accounts and
both volatility series together; they do not create new agents, independent
market histories, or economically reconstructed trading paths. Season-final
returns are held fixed. Reported quantiles are central resampling ranges, not
confidence intervals with established coverage from fourteen observations.

Run from any directory, e.g.:
  python paper/frl/paired_denominator_sensitivity.py --out DIR
All numerical inputs and existing generated results are read only.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd
from scipy.stats import rankdata, spearmanr

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
import analyse

DAY = 86400000
CAPITAL = 10000.0
SEED = 20261015


def descriptive_statistics(x: np.ndarray, outcome: np.ndarray) -> dict[str, np.ndarray]:
    """x has axes (draw, model, arm); outcome has axes (model, arm).

    F is an additive sums-of-squares ratio ONLY. No reference distribution is
    used. W is rank concordance across arms, corrected for tied ranks.
    """
    x = np.asarray(x, float)
    if x.ndim == 2:
        x = x[None, :, :]
    b, m, a = x.shape
    grand = x.mean(axis=(1, 2))
    ssm = a * ((x.mean(axis=2) - grand[:, None]) ** 2).sum(axis=1)
    ssa = m * ((x.mean(axis=1) - grand[:, None]) ** 2).sum(axis=1)
    sst = ((x - grand[:, None, None]) ** 2).sum(axis=(1, 2))
    sse = np.maximum(sst - ssm - ssa, 0)
    F = (ssm / (m - 1)) / (sse / ((m - 1) * (a - 1)))
    ranks = rankdata(x, axis=1)
    rank_sums = ranks.sum(axis=2)
    S = ((rank_sums - a * (m + 1) / 2) ** 2).sum(axis=1)
    # For each tied group of size t, summing t^2-1 over its members gives t^3-t.
    tie_counts = (ranks[:, :, None, :] == ranks[:, None, :, :]).sum(axis=2)
    tie_sum = (tie_counts ** 2 - 1).sum(axis=(1, 2))
    W = 12 * S / (a * a * (m ** 3 - m) - a * tie_sum)
    xr = ranks - ranks.mean(axis=1, keepdims=True)
    yr = rankdata(outcome, axis=0)
    yr -= yr.mean(axis=0, keepdims=True)
    rho = ((xr * yr[None, :, :]).sum(axis=1) /
           np.sqrt((xr ** 2).sum(axis=1) * (yr ** 2).sum(axis=0))).mean(axis=1)
    # Relative model sum of squares after removing the arm component; a
    # descriptive partial eta-squared, not a causal variance fraction.
    partial_ss = ssm / (ssm + sse)
    return {'F': F, 'W': W, 'rho': rho, 'partial_model_ss': partial_ss}


def evaluate(pnl: np.ndarray, ret: np.ndarray, outcome: np.ndarray) -> dict:
    """Arrays: draw x day x model x arm (or day x model x arm)."""
    if pnl.ndim == 3:
        pnl, ret = pnl[None], ret[None]
    fixed = descriptive_statistics(pnl.std(axis=1, ddof=1), outcome)
    equity = descriptive_statistics(ret.std(axis=1, ddof=1), outcome)
    out = {f'{den}_{k}': v for den, d in [('fixed', fixed), ('equity', equity)]
           for k, v in d.items()}
    out.update({f'delta_{k}': fixed[k] - equity[k] for k in fixed})
    return out


def moving_blocks(n: int, length: int, draws: int, rng: np.random.Generator):
    """Ordinary overlapping non-circular moving blocks, truncated to n dates."""
    count = (n + length - 1) // length
    starts = rng.integers(0, n - length + 1, size=(draws, count))
    return (starts[..., None] + np.arange(length)).reshape(draws, -1)[:, :n]


def scalar(d):
    return {k: float(np.asarray(v).item()) for k, v in d.items()}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def self_checks():
    """Check rank ties, ANOVA identity, and common-date block indexing."""
    x = np.array([[1., 2., 1.], [1., 3., 2.], [3., 1., 3.], [4., 4., 4.]])
    y = np.array([[4., 2., 1.], [3., 3., 2.], [2., 1., 3.], [1., 4., 4.]])
    s = scalar(descriptive_statistics(x, y))
    expected_rho = np.mean([spearmanr(x[:, i], y[:, i]).statistic for i in range(3)])
    np.testing.assert_allclose(s['rho'], expected_rho, rtol=0, atol=1e-14)
    from vol_fixed_denominator import anova_icc
    np.testing.assert_allclose(s['F'], anova_icc(x)['F_model'], atol=1e-12)
    # Direct textbook tie correction, independent from the vectorised kernel.
    ranks = np.column_stack([rankdata(x[:, i]) for i in range(3)])
    tie = sum(sum(c**3-c for c in np.unique(ranks[:, i], return_counts=True)[1])
              for i in range(3))
    direct_w = 12 * ((ranks.sum(1)-7.5)**2).sum() / (9*(4**3-4)-3*tie)
    np.testing.assert_allclose(s['W'], direct_w, atol=1e-14)
    for length in [1, 2, 3]:
        ids = moving_blocks(14, length, 5, np.random.default_rng(SEED))
        assert ids.shape == (5, 14) and ids.min() >= 0 and ids.max() < 14
        for j in range(0, 14, length):
            assert np.all(np.diff(ids[:, j:min(j+length, 14)], axis=1) == 1)
    # Resampling a constant denominator gives exactly zero paired contrast.
    a = np.random.default_rng(SEED).normal(size=(14, 4, 3))
    z = evaluate(a, a.copy(), y)
    for k in ['F', 'W', 'rho', 'partial_model_ss']:
        np.testing.assert_array_equal(z['delta_'+k], 0)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--draws', type=int, default=20000)
    args = ap.parse_args()
    if args.draws < 1000:
        raise ValueError('Use at least 1,000 sensitivity draws')
    self_checks()
    D = ROOT / 'data' / 'derived'
    source_paths = [D/'equity.parquet', D/'fills.parquet',
                    D/'i6_vol_denominator.csv', D/'i6_vol_denominator.json']
    before = {str(p.relative_to(ROOT)): sha256(p) for p in source_paths}
    eq = pd.read_parquet(D/'equity.parquet')
    fills = pd.read_parquet(D/'fills.parquet')
    lo, hi = analyse.common_window(fills, 'S15')
    e = eq.loc[eq.season.eq('S15') & eq.t.between(lo, hi)].copy()
    e['day'] = e.t // DAY
    ends = e.sort_values('t').groupby(['tag', 'day']).equity.last().unstack()
    meta = e.groupby('tag')[['model', 'competition_id']].first()
    order = meta.reset_index().sort_values(['model', 'competition_id'])
    models = sorted(meta.model.unique()); arms = sorted(meta.competition_id.unique())
    assert (len(models), len(arms), len(order)) == (8, 4, 32)
    assert not meta.duplicated(['model', 'competition_id']).any()
    ends = ends.loc[order.tag]
    assert ends.notna().all().all() and ends.gt(0).all().all()
    pnl = ends.diff(axis=1).iloc[:, 1:].to_numpy().T / CAPITAL
    ret = ends.pct_change(axis=1, fill_method=None).iloc[:, 1:].to_numpy().T
    n = pnl.shape[0]
    assert n == 14
    pnl = pnl.reshape(n, 8, 4); ret = ret.reshape(n, 8, 4)
    outcome = (ends.iloc[:, -1].to_numpy()/CAPITAL-1).reshape(8, 4)
    observed = scalar(evaluate(pnl, ret, outcome))
    prior = json.loads((D/'i6_vol_denominator.json').read_text())
    for den in ['equity', 'fixed']:
        for key, oldkey in [('F','F_model'), ('W','W'), ('rho','assoc_rho')]:
            np.testing.assert_allclose(observed[f'{den}_{key}'],
                                       prior[f'vol_{den}'][oldkey], atol=1e-13)
    # Check all per-account volatility and final-return inputs against the
    # historical result, not merely the aggregated reported statistics.
    old = pd.read_csv(D/'i6_vol_denominator.csv').set_index('tag').loc[order.tag]
    for den, a in [('fixed', pnl), ('equity', ret)]:
        np.testing.assert_allclose(a.std(axis=0, ddof=1).ravel(), old['vol_'+den],
                                   rtol=1e-12, atol=1e-14)
    np.testing.assert_allclose(outcome.ravel(), old.final_return, atol=1e-14)

    args.out.mkdir(parents=True, exist_ok=True)
    sensitivity = []
    draw_frames = []
    for length in [1, 2, 3]:
        rng = np.random.default_rng(SEED + length)
        ids = moving_blocks(n, length, args.draws, rng)
        batches = []
        for start in range(0, args.draws, 512):
            ix = ids[start:start+512]
            batches.append(pd.DataFrame(evaluate(pnl[ix], ret[ix], outcome)))
        draws = pd.concat(batches, ignore_index=True)
        assert np.isfinite(draws.to_numpy()).all()
        for stat in draws:
            q = draws[stat].quantile([.025,.5,.975])
            sensitivity.append({'block_days':length, 'statistic':stat,
                                'observed':observed[stat], 'q025':float(q.loc[.025]),
                                'median':float(q.loc[.5]), 'q975':float(q.loc[.975]),
                                'draws':args.draws})
        draws.insert(0, 'draw', np.arange(1,len(draws)+1))
        draws.insert(0, 'block_days', length)
        draw_frames.append(draws)
    pd.concat(draw_frames).to_csv(args.out/'joint_block_draws.csv.gz', index=False,
                                  compression={'method': 'gzip', 'mtime': 0})
    pd.DataFrame(sensitivity).to_csv(args.out/'joint_block_summary.csv', index=False)

    deletions = []
    dates = pd.to_datetime(ends.columns[1:]*DAY, unit='ms', utc=True)
    for i, day in enumerate(dates):
        keep = np.arange(n) != i
        deletions.append({'unit':'date', 'omitted':day.strftime('%Y-%m-%d'),
                          **scalar(evaluate(pnl[keep],ret[keep],outcome))})
    for i, model in enumerate(models):
        keep = np.arange(8) != i
        deletions.append({'unit':'model','omitted':model,
                          **scalar(evaluate(pnl[:,keep],ret[:,keep],outcome[keep]))})
    for i, arm in enumerate(arms):
        keep = np.arange(4) != i
        deletions.append({'unit':'arm','omitted':str(arm),
                          **scalar(evaluate(pnl[:,:,keep],ret[:,:,keep],outcome[:,keep]))})
    pd.DataFrame(deletions).to_csv(args.out/'paired_leave_one_out.csv', index=False)

    # Descriptive side-by-side table for all monetary measures. These other
    # measures are NOT resampled by this script.
    comparison = []
    for metric in ['vol','leverage','turnover']:
        obs = {}
        for den in ['equity','fixed']:
            vals = old[metric+'_'+den].to_numpy().reshape(8,4)
            obs[den] = scalar(descriptive_statistics(vals,outcome))
        comparison.append({'metric':metric, **{f'{den}_{k}':v for den,d in obs.items()
                                              for k,v in d.items()},
                           **{f'delta_{k}':obs['fixed'][k]-obs['equity'][k]
                              for k in obs['fixed']}})
    pd.DataFrame(comparison).to_csv(args.out/'denominator_comparison.csv', index=False)
    accounts = order.copy().reset_index(drop=True)
    accounts['vol_fixed'] = pnl.std(axis=0,ddof=1).ravel()
    accounts['vol_equity'] = ret.std(axis=0,ddof=1).ravel()
    accounts['final_return'] = outcome.ravel()
    accounts.to_csv(args.out/'account_volatility.csv', index=False)
    daily = pd.DataFrame({'date':np.repeat(dates.strftime('%Y-%m-%d'),32),
                          'tag':np.tile(order.tag.to_numpy(),n),
                          'pnl_initial_capital':pnl.reshape(-1),
                          'return_current_equity':ret.reshape(-1)})
    daily.to_csv(args.out/'paired_daily_inputs.csv', index=False)
    assert before == {str(p.relative_to(ROOT)):sha256(p) for p in source_paths}
    out = {
        'scope':'Descriptive common-date reweighting; not a test of model-population differences.',
        'n_models':8,'n_arms':4,'n_accounts':32,'n_daily_changes':n,
        'observed':observed, 'seed_base':SEED,'draws_per_block':args.draws,
        'block_lengths':[1,2,3], 'block_scheme':'Overlapping non-circular moving blocks; truncate to 14 dates.',
        'preserved':'Same date indices for all 32 accounts, both denominators; observed temporal order within each block.',
        'fixed':'The 32 observed season-final returns and account/model/arm labels.',
        'interpretation':'Quantiles are central 95% resampling ranges. No confidence-interval coverage or p-values are claimed.',
        'limitations':[
            'Fourteen observed dates cannot establish stationarity, choose block length reliably, or reveal unobserved market regimes.',
            'Dependence beyond the chosen block length is not preserved; the partial final day is treated as one observation, as in the historical analysis.',
            'Reweighted return/P&L tuples are measurements from the observed path, not a dynamically self-consistent wealth or policy replay.',
            'Holding final outcomes fixed examines sensitivity of measured risk and its association with this realised ranking; it does not estimate joint uncertainty in future risk and returns.',
            'One account per model-arm cell leaves implementation, interaction, and run variation inseparable; no random assignment or random sampling of models is introduced.',
            'Current-equity and initial-capital denominators are economically distinct legitimate estimands; the contrast is not causal evidence that losses generated an association.'
        ],
        'checks':['Vectorised F agrees with existing scalar ANOVA; rank correlation agrees with scipy including ties.',
                  'Kendall W agrees with independent explicit tie correction.',
                  'Paired contrast is identically zero for identical denominator inputs.',
                  'Block indexing preserves contiguous order within every block.',
                  'All 32 account volatilities, final returns, and F/W/rho match existing results.',
                  'All four input/result file SHA-256 values unchanged after execution.'],
        'source_sha256':before,
        'summary':sensitivity,
        'leave_one_out_ranges':{
          unit:{stat:{'min':float(pd.DataFrame(deletions).query('unit == @unit')[stat].min()),
                      'max':float(pd.DataFrame(deletions).query('unit == @unit')[stat].max())}
                for stat in observed}
          for unit in ['date','model','arm']}
    }
    (args.out/'paired_denominator_report.json').write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps({'observed':observed,'summary':[r for r in sensitivity
          if r['statistic'] in ['fixed_F','fixed_W','delta_rho']],
          'checks':out['checks']}, indent=2))

if __name__ == '__main__':
    main()
