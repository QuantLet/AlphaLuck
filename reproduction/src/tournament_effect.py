"""Descriptive tournament-effect test: interim standing and later risk-taking.

Run: python src/tournament_effect.py [--archive PATH]

Question. Brown et al. (1996) and Chevalier and Ellison (1997) find that fund
managers who are behind at an interim date raise risk. In Season 1.5 only
arm 3 (Situational Awareness) shows the models the leaderboard: own rank and
the other models' account value, return and positions. Arms 1, 2 and 4 run
the same eight models without it. If standing moves risk-taking through the
prompt, the within-account relation between being behind and the next
window's change in exposure should be stronger in arm 3 than in the other
arms for the same model.

Design (on-chain reconstruction, complete for all 32 accounts):

* hours t_k = official start + k hours; formation hours k = 1 .. 337 - H so
  that the window (t_k, t_k + H] ends inside the official season;
* standing: rank of equity within the account's arm (1 = leader), scaled to
  behind = (rank - 1) / 7 in [0, 1]; alternative: gap to the arm median,
  (median_arm E - E) / C in per cent of initial capital;
* risk (the paper's gross-exposure definition, gross notional = sum of
  |signed notional| on the five-minute grid): change in exposure
      D_k = (mean_{t in (t_k, t_k + H]} G_t - G_{t_k}) / E_{t_k},
  measured on formation-hour equity so that later losses cannot raise it
  arithmetically (the C / E_t channel of src/exposure_mechanics.py);
  variants on initial capital C and as the level mean G_t / E_{t_k};
* per account: Spearman rho_i(behind_k, D_k) over formation hours;
* contrast (difference in differences, within model):
      DiD = mean_m [ rho_{m,3} - mean_{a in O} rho_{m,a} ],
  O = {1, 2, 4} or {1, 2} (arm 4 forces maximum leverage).

Inference, conditional on this panel and market path:

* label test: which of a model's accounts is called "arm 3" is permuted
  within model, standings kept as computed in each account's own arm;
  all 4^8 = 65,536 (or 3^8 = 6,561) assignments are enumerated, exact;
* overall relation (does behind predict more risk anywhere): mean rho over
  accounts against a common circular shift of every D series by s hours,
  H <= s <= n - H, all shifts enumerated (keeps the cross-account dependence
  of one market path; hours overlap);
* cross-sectional variant: Spearman across the eight models within each
  arm-hour, arm 3 minus the others, with arm labels permuted within model
  (Monte Carlo).

Organiser snapshots (data/raw/nof1_hourly) are used twice: the organiser's
equity gives the rank only at markers where all eight accounts of an arm are
present (the paged export misses accounts in markers 2-28 and 118-143), which
is compared with the on-chain rank; and the snapshot positions give a second
risk measure, gross = sum |q| x current_price, and the notional-weighted
declared leverage. The 25 arm-3 prompts of data/raw/nof1/conversations.json
(6 December 2025, post-season) print the standings the models saw; they are
compared with the organiser and on-chain ranks at the same time.

One run per model-arm cell confounds model and configuration, formation hours
overlap and share one market path, and the arms differ in more than the
leaderboard; the test is descriptive.

Writes data/derived/tournament_{panel,accounts,conversations}.csv,
data/derived/tournament_effect.json, paper/frl/tournament_table.tex and
paper/frl/tournament_numbers.tex.
"""
from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path
import re
import sys

import numpy as np
import pandas as pd
from scipy import stats

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import wallets  # noqa: E402

HOUR = 3_600_000
C = 10_000.0
N_HOURS = (wallets.S15_OFFICIAL_END_MS - wallets.S15_START_MS) // HOUR   # 337
ARMS = (1, 2, 3, 4)
TREATED = 3
HORIZONS = (4, 24, 72)
PRIMARY_H = 24
N_MC = 20_000
SEED = 20261021
ORG_NAMES = {'mystery-model': 'typhoon', 'gemini-3-pro': 'gemini-3-pro-preview'}


def arguments():
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--root', type=Path, default=HERE.parent)
    p.add_argument('--archive', type=Path)
    a = p.parse_args()
    a.root = a.root.resolve()
    a.archive = a.archive or a.root / 'data/raw/nof1_hourly/account_totals_hourly.zip'
    return a


# ----------------------------------------------------------------- primitives
def rank_rows(x):
    """Average ranks along the last axis (NaN-free input)."""
    return stats.rankdata(x, axis=-1)


def spearman_rows(x, y):
    """Spearman correlation along the last axis, ignoring NaN pairs."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    out = np.full(x.shape[:-1], np.nan)
    flat_x, flat_y = x.reshape(-1, x.shape[-1]), y.reshape(-1, y.shape[-1])
    o = out.reshape(-1)
    for i in range(len(o)):
        ok = np.isfinite(flat_x[i]) & np.isfinite(flat_y[i])
        if ok.sum() < 3 or np.ptp(flat_x[i][ok]) == 0 or np.ptp(flat_y[i][ok]) == 0:
            continue
        o[i] = stats.spearmanr(flat_x[i][ok], flat_y[i][ok]).statistic
    return out


def behind_score(equity):
    """(rank - 1) / (n - 1) within arm along axis 0 (models); 1 = last."""
    n = equity.shape[0]
    r = stats.rankdata(-equity, axis=0)          # 1 = highest equity
    return (r - 1) / (n - 1)


def did(rho, treated=TREATED, others=(1, 2, 4)):
    """mean over models of rho[m, treated] - mean_{a in others} rho[m, a].

    rho: DataFrame indexed by model with arm columns.
    """
    rho = rho[[treated, *others]].dropna()
    return float((rho[treated] - rho[list(others)].mean(axis=1)).mean())


def label_test(rho, others=(1, 2, 4)):
    """Exact within-model relabelling of which account is the treated arm."""
    arms = [TREATED] + list(others)
    rho = rho[arms].dropna()                      # models with a defined rho in every arm
    R = rho.to_numpy(float)                       # models x arms
    k = R.shape[1]
    # contrast if arm j of model m were the treated one
    d = (k * R - R.sum(axis=1, keepdims=True)) / (k - 1)
    obs = float(d[:, 0].mean())
    idx = np.array(list(itertools.product(range(k), repeat=R.shape[0])))
    vals = d[np.arange(R.shape[0]), idx].mean(axis=1)
    tol = 1e-12
    return {'obs': obs, 'n_models': int(R.shape[0]), 'n_assignments': int(len(vals)),
            'p_one_sided_greater': float(np.mean(vals >= obs - tol)),
            'p_one_sided_less': float(np.mean(vals <= obs + tol)),
            'p_two_sided': float(np.mean(np.abs(vals) >= abs(obs) - tol))}


def shift_test(behind, delta, lag):
    """Mean within-account Spearman against common circular shifts of delta.

    behind, delta: accounts x hours.  Shifts lag .. n - lag, all enumerated.
    """
    n = behind.shape[1]
    obs = float(np.nanmean(spearman_rows(behind, delta)))
    rb = rank_rows(behind)
    sd = rb.std(1, keepdims=True)
    rb = np.where(sd > 0, (rb - rb.mean(1, keepdims=True)) / np.where(sd > 0, sd, 1), np.nan)
    vals = []
    for s in range(lag, n - lag + 1):
        rd = rank_rows(np.roll(delta, s, axis=1))
        rd = (rd - rd.mean(1, keepdims=True)) / rd.std(1, keepdims=True)
        vals.append(float(np.nanmean((rb * rd).mean(1))))
    vals = np.array(vals)
    return {'obs': obs, 'n_shifts': int(len(vals)),
            'p_two_sided': float((np.sum(np.abs(vals) >= abs(obs) - 1e-12) + 1) / (len(vals) + 1)),
            'p_one_sided_greater': float((np.sum(vals >= obs - 1e-12) + 1) / (len(vals) + 1))}


def cross_section_test(behind, delta, others=(1, 2, 4), n_mc=N_MC, seed=SEED):
    """Arm-hour cross-sectional Spearman, arm 3 minus others; MC relabelling.

    behind, delta: models x arms(1..4) x hours.  Standings stay as computed in
    each account's own arm; relabelling regroups accounts into pseudo-arms.
    """
    use = [TREATED] + list(others)
    cols = [ARMS.index(a) for a in use]
    B, D = behind[:, cols, :], delta[:, cols, :]
    rb = stats.rankdata(B, axis=0)
    rd = stats.rankdata(D, axis=0)

    def stat(rb, rd):
        zb = rb - rb.mean(0, keepdims=True)
        zd = rd - rd.mean(0, keepdims=True)
        r = (zb * zd).sum(0) / np.sqrt((zb ** 2).sum(0) * (zd ** 2).sum(0))
        r = r.mean(-1)                              # arms (and leading batch)
        return r[..., 0] - r[..., 1:].mean(-1)

    obs = float(stat(rb, rd))
    rng = np.random.default_rng(seed)
    n_m, k = B.shape[0], B.shape[1]
    vals = np.empty(n_mc)
    batch = 500
    for start in range(0, n_mc, batch):
        size = min(batch, n_mc - start)
        perm = np.argsort(rng.random((size, n_m, k)), axis=2)
        Bp = B[np.arange(n_m)[None, :, None], perm]          # size x m x k x hours
        Dp = D[np.arange(n_m)[None, :, None], perm]
        rbp = stats.rankdata(Bp, axis=1)
        rdp = stats.rankdata(Dp, axis=1)
        zb = rbp - rbp.mean(1, keepdims=True)
        zd = rdp - rdp.mean(1, keepdims=True)
        r = (zb * zd).sum(1) / np.sqrt((zb ** 2).sum(1) * (zd ** 2).sum(1))
        r = r.mean(-1)
        vals[start:start + size] = r[:, 0] - r[:, 1:].mean(-1)
    return {'obs': obs, 'n_mc': int(n_mc),
            'p_two_sided': float((np.sum(np.abs(vals) >= abs(obs) - 1e-12) + 1) / (n_mc + 1)),
            'p_one_sided_greater': float((np.sum(vals >= obs - 1e-12) + 1) / (n_mc + 1))}


# ----------------------------------------------------------------- chain data
def chain_grid(root):
    """Equity and gross on the five-minute grid, models x arms x grid points."""
    der = root / 'data/derived'
    eq = pd.read_parquet(der / 'equity.parquet')
    eq = eq[eq.season.eq('S15')]
    pan = pd.read_parquet(der / 'panel.parquet', columns=['season', 'tag', 't', 'signed_notional'])
    pan = pan[pan.season.eq('S15')]
    lo, hi = wallets.S15_START_MS, wallets.S15_OFFICIAL_END_MS
    grid = np.arange(lo, hi + 1, 300_000)
    meta = eq.groupby('tag')[['model', 'competition_id']].first()
    models = sorted(meta.model.unique())
    E = eq.pivot(index='tag', columns='t', values='equity')
    E = E.reindex(columns=np.union1d(grid, E.columns)).ffill(axis=1).bfill(axis=1)[grid]
    G = (pan.assign(a=pan.signed_notional.abs()).groupby(['tag', 't']).a.sum()
         .unstack().reindex(columns=grid).fillna(0.0))
    shape = (len(models), len(ARMS), len(grid))
    Ea, Ga = np.empty(shape), np.empty(shape)
    for tag, r in meta.iterrows():
        i, j = models.index(r.model), ARMS.index(int(r.competition_id))
        Ea[i, j], Ga[i, j] = E.loc[tag].to_numpy(), G.loc[tag].to_numpy()
    if not np.isfinite(Ea).all() or not np.isfinite(Ga).all():
        raise ValueError('Equity or gross missing on the grid')
    return models, grid, Ea, Ga


def chain_measures(Ea, Ga, H):
    """Standing and risk at formation hours 1 .. N_HOURS - H."""
    step = HOUR // 300_000                         # 12 grid points per hour
    ks = np.arange(1, N_HOURS - H + 1)
    at = ks * step
    E = Ea[..., at]
    G = Ga[..., at]
    csum = np.concatenate([np.zeros(Ga.shape[:-1] + (1,)), Ga.cumsum(-1)], axis=-1)
    # mean over grid points at+1 .. at+H*step
    future = (csum[..., at + H * step + 1] - csum[..., at + 1]) / (H * step)
    out = {
        'hours': ks,
        'equity': E,
        'behind': behind_score(E),
        'gap_pct': 100 * (np.median(E, axis=0, keepdims=True) - E) / C,
        'gross_eq_now': G / E,
        'd_gross_eqk': (future - G) / E,
        'd_gross_c': (future - G) / C,
        'lvl_gross_eqk': future / E,
    }
    return out


def per_account(models, measures, x='behind', y='d_gross_eqk', start=None):
    hours = measures['hours']
    keep = slice(None) if start is None else hours >= start
    rho = spearman_rows(measures[x][..., keep], measures[y][..., keep])
    return pd.DataFrame(rho, index=models, columns=list(ARMS))


# ------------------------------------------------------------ organiser data
def organiser(root, archive, models, grid, Ea):
    sys.path.insert(0, str(HERE))
    import organiser_hourly as oh
    acc, pos, _ = oh.load_archive(archive, root)
    meta = acc.tag.str.extract(r'S15__c(\d)__(.+)')
    acc['arm'], acc['model'] = meta[0].astype(int), meta[1]
    acc = acc[acc.t.le(wallets.S15_OFFICIAL_END_MS)]
    acc['k'] = acc.since_inception_hourly_marker.astype(int)
    pos = pos.assign(notional=pos.quantity.abs() * pos.current_price)
    pos['lev_x_notional'] = pos.notional * pos.leverage
    pg = pos.groupby(['tag', 't'])[['notional', 'lev_x_notional']].sum().reset_index()
    acc = acc.merge(pg, on=['tag', 't'], how='left').fillna({'notional': 0.0, 'lev_x_notional': 0.0})
    acc['declared_leverage'] = np.where(acc.notional > 0, acc.lev_x_notional / acc.notional.where(acc.notional > 0), np.nan)
    # on-chain equity at the snapshot timestamp (previous five-minute point)
    tag_index = {(m, a): (models.index(m), ARMS.index(a)) for m in models for a in ARMS}
    pos_grid = np.searchsorted(grid, acc.t.to_numpy(), side='right') - 1
    acc['chain_equity'] = [Ea[tag_index[(m, a)]][max(g, 0)]
                           for m, a, g in zip(acc.model, acc.arm, pos_grid)]
    n_in_arm = acc.groupby(['arm', 'k']).tag.transform('nunique')
    acc['arm_complete'] = n_in_arm.eq(len(models))
    full = acc[acc.arm_complete].copy()
    full['rank_org'] = full.groupby(['arm', 'k']).dollar_equity.rank(ascending=False)
    full['rank_chain'] = full.groupby(['arm', 'k']).chain_equity.rank(ascending=False)
    agree = {
        'account_markers_in_season': int(len(acc)),
        'arm_markers_complete': int(full.groupby(['arm', 'k']).ngroups),
        'arm_markers_total': int(acc.groupby(['arm', 'k']).ngroups),
        'account_markers_ranked': int(len(full)),
        'rank_identical_share': float((full.rank_org == full.rank_chain).mean()),
        'rank_abs_diff_max': float((full.rank_org - full.rank_chain).abs().max()),
        'rank_identical_share_arm3': float(
            (full[full.arm.eq(3)].rank_org == full[full.arm.eq(3)].rank_chain).mean()),
    }
    return acc, full, agree


def organiser_measures(acc, full, models, H=PRIMARY_H):
    """Risk change over (k, k + H] from organiser snapshots; standing only at
    complete arm-markers.  The window mean needs at least H / 2 snapshots."""
    ks = np.arange(1, N_HOURS - H + 1)
    shape = (len(models), len(ARMS), len(ks))
    behind = np.full(shape, np.nan)
    d_gross = np.full(shape, np.nan)
    d_lev = np.full(shape, np.nan)
    full = full.assign(behind=(full.rank_org - 1) / (len(models) - 1))
    for (m, a), g in acc.groupby(['model', 'arm']):
        i, j = models.index(m), ARMS.index(a)
        s = g.set_index('k').sort_index()
        s = s[~s.index.duplicated()]
        gross = s.notional.reindex(range(N_HOURS + 1))
        lev = s.declared_leverage.reindex(range(N_HOURS + 1))
        eq = s.dollar_equity.reindex(range(N_HOURS + 1))
        b = full[full.model.eq(m) & full.arm.eq(a)].set_index('k').behind
        for n, k in enumerate(ks):
            w = gross.loc[k + 1:k + H]
            if np.isnan(eq.loc[k]) or w.notna().sum() < H / 2:
                continue
            d_gross[i, j, n] = (w.mean() - gross.loc[k]) / eq.loc[k]
            lw = lev.loc[k + 1:k + H]
            if np.isfinite(lev.loc[k]) and lw.notna().sum() >= H / 4:
                d_lev[i, j, n] = lw.mean() - lev.loc[k]
            behind[i, j, n] = b.get(k, np.nan)
    return {'hours': ks, 'behind': behind, 'd_gross_eqk': d_gross, 'd_declared_leverage': d_lev}


# -------------------------------------------------------------- conversations
STANDING = re.compile(r'^\s*(\d+)\.\s+(.+?)\s+-\s+Total Account Value:\s*([-\d.]+)', re.M)


def parse_standings(prompt):
    block = prompt.split('CURRENT STATE OF COMPETITION', 1)
    if len(block) < 2:
        return None
    rows = STANDING.findall(block[1].split('CURRENT AVAILABLE CAPITAL', 1)[0])
    return [(int(r), name.strip(), float(v)) for r, name, v in rows]


def conversation_check(root, acc_all, models, grid_full, E_full):
    conv = json.loads((root / 'data/raw/nof1/conversations.json').read_text())['conversations']
    rows = []
    has_block = {a: 0 for a in ARMS}
    for r in conv:
        a = int(r['competition_id'])
        st = parse_standings(r['user_prompt'])
        has_block[a] += st is not None
        if st is None:
            continue
        me = ORG_NAMES.get(r['run_name'], r['run_name'])
        t = int(round(float(r['timestamp']) * 1000))
        shown = {}
        for rank, name, value in st:
            name = me if '**YOU**' in name else ORG_NAMES.get(name, name)
            shown[name] = (rank, value)
        # organiser: each account's latest snapshot at or before the prompt
        snap = acc_all[acc_all.arm.eq(a) & acc_all.t.le(t)].sort_values('t').groupby('model').last()
        org_rank = snap.dollar_equity.rank(ascending=False)
        g = np.searchsorted(grid_full, t, side='right') - 1
        chain = pd.Series(E_full[:, ARMS.index(a), g], index=models)
        chain_rank = chain.rank(ascending=False)
        values_sorted = all(st[i][2] >= st[i + 1][2] for i in range(len(st) - 1))
        rows.append({
            'id': r['id'], 'arm': a, 'model': me, 'utc': str(pd.to_datetime(t, unit='ms')),
            'n_listed': len(st), 'listed_sorted_by_value': values_sorted,
            'shown_rank': shown[me][0], 'shown_value': shown[me][1],
            'organiser_rank': float(org_rank.get(me, np.nan)),
            'organiser_value': float(snap.dollar_equity.get(me, np.nan)),
            'organiser_snapshot_age_min': float((t - snap.t.get(me, np.nan)) / 60_000),
            'chain_rank': float(chain_rank[me]), 'chain_value': float(chain[me]),
            'all_ranks_match_organiser': all(org_rank.get(n, -1) == v[0] for n, v in shown.items()),
            'all_ranks_match_chain': all(chain_rank.get(n, -1) == v[0] for n, v in shown.items()),
            'max_abs_value_gap_organiser_pct': float(max(
                abs(v[1] / snap.dollar_equity[n] - 1) for n, v in shown.items()) * 100),
        })
    return pd.DataFrame(rows), has_block


# ---------------------------------------------------------------------- main
def fmt(x, d=2):
    s = f'{x:.{d}f}'
    return s.replace('-', '\\ensuremath{-}') if s.startswith('-') else s


def fmt_p(p):
    return f'{p:.3f}' if p >= 0.001 else '<0.001'


def word(n):
    return {4: 'Four', 24: 'TwentyFour', 72: 'SeventyTwo'}[n]


def main():
    args = arguments()
    der = args.root / 'data/derived'
    models, grid, Ea, Ga = chain_grid(args.root)
    if len(models) != 8 or Ea.shape[:2] != (8, 4):
        raise ValueError('Expected eight models in four arms')

    result = {'design': {
        'formation_hours': f'1..{N_HOURS} - H', 'horizons_h': list(HORIZONS),
        'primary_horizon_h': PRIMARY_H, 'standing': 'behind = (rank - 1) / 7 within arm',
        'risk': '(mean gross over (k, k+H] - gross_k) / equity_k',
        'statistic': 'within-account Spearman; DiD = mean_m rho_m3 - mean others',
    }}
    acct_rows, table = [], []
    m24 = None
    for H in HORIZONS:
        meas = chain_measures(Ea, Ga, H)
        if H == PRIMARY_H:
            m24 = meas
        specs = [('behind', 'd_gross_eqk', None), ('behind', 'd_gross_c', None),
                 ('gap_pct', 'd_gross_eqk', None), ('behind', 'lvl_gross_eqk', None),
                 ('behind', 'd_gross_eqk', 24)]
        if H != PRIMARY_H:
            specs = specs[:1]
        for x, y, start in specs:
            rho = per_account(models, meas, x, y, start)
            key = f'H{H}_{x}_{y}' + (f'_from{start}' if start else '')
            item = {'arm_mean_rho': {str(a): float(rho[a].mean()) for a in ARMS},
                    'all_arms_mean_rho': float(np.nanmean(rho.to_numpy())),
                    'accounts_undefined': [f'{m} arm {a}' for m in models for a in ARMS
                                           if not np.isfinite(rho.loc[m, a])]}
            for label, others in (('vs124', (1, 2, 4)), ('vs12', (1, 2))):
                item[label] = label_test(rho, others)
                item[label]['did'] = did(rho, others=others)
                item[label]['loo_range'] = [
                    float(min(did(rho.drop(m), others=others) for m in models)),
                    float(max(did(rho.drop(m), others=others) for m in models))]
            keep = np.ones(len(meas['hours']), bool) if start is None else meas['hours'] >= start
            flatB = meas[x][..., keep].reshape(32, -1)
            flatD = meas[y][..., keep].reshape(32, -1)
            item['overall_shift'] = shift_test(flatB, flatD, H)
            item['arm_shift'] = {str(a): shift_test(meas[x][:, j][..., keep], meas[y][:, j][..., keep], H)
                                 for j, a in enumerate(ARMS)}
            item['arm3_shift'] = item['arm_shift'][str(TREATED)]
            result[key] = item
            table.append((H, x, y, start, item))
            for m in models:
                for a in ARMS:
                    acct_rows.append({'spec': key, 'model': m, 'arm': a, 'rho': float(rho.loc[m, a])})
    # cross-sectional variant at the primary horizon
    for label, others in (('vs124', (1, 2, 4)), ('vs12', (1, 2))):
        result[f'H{PRIMARY_H}_cross_section_{label}'] = cross_section_test(
            m24['behind'], m24['d_gross_eqk'], others)

    # descriptive: does standing persist, and do accounts move
    hrs = m24['hours']
    changes = (np.abs(np.diff(m24['behind'], axis=-1)) > 0).sum(-1)       # models x arms
    after = m24['behind'][..., hrs >= 24]
    result['standing_changes'] = {
        'rank_changes_median_by_arm': {str(a): float(np.median(changes[:, j]))
                                       for j, a in enumerate(ARMS)},
        'within_account_sd_behind_mean_by_arm': {str(a): float(m24['behind'][:, j].std(-1).mean())
                                                 for j, a in enumerate(ARMS)},
        'constant_rank_from_hour_24': [f'{m} arm {a} rank {int(round(7 * after[i, j, 0])) + 1}'
                                       for i, m in enumerate(models) for j, a in enumerate(ARMS)
                                       if np.ptp(after[i, j]) == 0],
    }

    # organiser snapshots
    acc, full, agree = organiser(args.root, args.archive, models, grid, Ea)
    result['organiser_rank_agreement'] = agree
    om = organiser_measures(acc, full, models)
    for y in ('d_gross_eqk', 'd_declared_leverage'):
        rho = pd.DataFrame(spearman_rows(om['behind'], om[y]), index=models, columns=list(ARMS))
        item = {'arm_mean_rho': {str(a): float(rho[a].mean()) for a in ARMS},
                'n_pairs_per_account_median': float(np.median(
                    (np.isfinite(om['behind']) & np.isfinite(om[y])).sum(-1)))}
        for label, others in (('vs124', (1, 2, 4)), ('vs12', (1, 2))):
            item[label] = label_test(rho, others)
        result[f'organiser_H{PRIMARY_H}_behind_{y}'] = item
        table.append((PRIMARY_H, 'organiser', y, None, item))
        for m in models:
            for a in ARMS:
                acct_rows.append({'spec': f'organiser_H{PRIMARY_H}_behind_{y}', 'model': m,
                                  'arm': a, 'rho': float(rho.loc[m, a])})
    # organiser behind vs chain behind on the hour grid
    ob, cb = om['behind'], m24['behind']
    ok = np.isfinite(ob)
    result['organiser_vs_chain_behind_hourgrid'] = {
        'cells': int(ok.sum()), 'identical_share': float(np.mean(ob[ok] == cb[ok])),
        'spearman': float(stats.spearmanr(ob[ok], cb[ok]).statistic)}

    # conversations: rank seen vs computed (full on-chain grid)
    eq = pd.read_parquet(der / 'equity.parquet')
    eq = eq[eq.season.eq('S15')]
    gfull = np.sort(eq.t.unique())
    Efull = np.empty((8, 4, len(gfull)))
    piv = eq.pivot(index='tag', columns='t', values='equity').reindex(columns=gfull).ffill(axis=1)
    for tag, r in eq.groupby('tag')[['model', 'competition_id']].first().iterrows():
        Efull[models.index(r.model), ARMS.index(int(r.competition_id))] = piv.loc[tag].to_numpy()
    from organiser_hourly import load_archive
    acc_all, _, _ = load_archive(args.archive, args.root)
    mm = acc_all.tag.str.extract(r'S15__c(\d)__(.+)')
    acc_all['arm'], acc_all['model'] = mm[0].astype(int), mm[1]
    conv, has_block = conversation_check(args.root, acc_all, models, gfull, Efull)
    result['conversations'] = {
        'prompts_with_standings_by_arm': {str(a): int(v) for a, v in has_block.items()},
        'arm3_prompts': int(len(conv)),
        'utc_range': [conv.utc.min(), conv.utc.max()],
        'listed_eight_and_sorted': int((conv.n_listed.eq(8) & conv.listed_sorted_by_value).sum()),
        'own_rank_matches_organiser': int((conv.shown_rank == conv.organiser_rank).sum()),
        'own_rank_matches_chain': int((conv.shown_rank == conv.chain_rank).sum()),
        'all_ranks_match_organiser': int(conv.all_ranks_match_organiser.sum()),
        'all_ranks_match_chain': int(conv.all_ranks_match_chain.sum()),
        'max_abs_value_gap_organiser_pct': float(conv.max_abs_value_gap_organiser_pct.max()),
        'median_snapshot_age_min': float(conv.organiser_snapshot_age_min.median()),
    }

    # panel export (primary horizon)
    rows = []
    for i, m in enumerate(models):
        for j, a in enumerate(ARMS):
            for n, k in enumerate(hrs):
                rows.append({'model': m, 'arm': a, 'hour': int(k),
                             'equity': m24['equity'][i, j, n], 'behind': m24['behind'][i, j, n],
                             'gap_pct': m24['gap_pct'][i, j, n],
                             'gross_over_equity': m24['gross_eq_now'][i, j, n],
                             'd_gross_eqk_24h': m24['d_gross_eqk'][i, j, n],
                             'organiser_behind': om['behind'][i, j, n],
                             'organiser_d_gross_eqk_24h': om['d_gross_eqk'][i, j, n],
                             'organiser_d_declared_leverage_24h': om['d_declared_leverage'][i, j, n]})
    (der / 'organiser_hourly').mkdir(exist_ok=True)
    pd.DataFrame(rows).to_csv(der / 'organiser_hourly' / 'tournament_panel.csv', index=False)
    pd.DataFrame(acct_rows).to_csv(der / 'tournament_accounts.csv', index=False)
    conv.to_csv(der / 'organiser_hourly' / 'tournament_conversations.csv', index=False)
    (der / 'tournament_effect.json').write_text(json.dumps(result, indent=1, default=float))
    write_tex(args.root, result, table)
    p = result[f'H{PRIMARY_H}_behind_d_gross_eqk']
    print(f"arm means rho: {p['arm_mean_rho']}")
    print(f"DiD vs 1,2,4 = {p['vs124']['did']:+.3f} p2 = {p['vs124']['p_two_sided']:.3f}; "
          f"vs 1,2 = {p['vs12']['did']:+.3f} p2 = {p['vs12']['p_two_sided']:.3f}")


def write_tex(root, r, table):
    P = r[f'H{PRIMARY_H}_behind_d_gross_eqk']
    cs = r[f'H{PRIMARY_H}_cross_section_vs124']
    cs12 = r[f'H{PRIMARY_H}_cross_section_vs12']
    ag, cv = r['organiser_rank_agreement'], r['conversations']
    og = r[f'organiser_H{PRIMARY_H}_behind_d_gross_eqk']
    ol = r[f'organiser_H{PRIMARY_H}_behind_d_declared_leverage']
    mac = {
        'TourHours': str(N_HOURS - PRIMARY_H),
        'TourRhoArmOne': fmt(P['arm_mean_rho']['1']), 'TourRhoArmTwo': fmt(P['arm_mean_rho']['2']),
        'TourRhoArmThree': fmt(P['arm_mean_rho']['3']), 'TourRhoArmFour': fmt(P['arm_mean_rho']['4']),
        'TourRhoAll': fmt(P['all_arms_mean_rho']),
        'TourRhoAllP': fmt_p(P['overall_shift']['p_two_sided']),
        'TourRhoThreeP': fmt_p(P['arm3_shift']['p_two_sided']),
        'TourShifts': str(P['overall_shift']['n_shifts']),
        'TourDiD': fmt(P['vs124']['did']), 'TourDiDP': fmt_p(P['vs124']['p_two_sided']),
        'TourDiDPone': fmt_p(P['vs124']['p_one_sided_greater']),
        'TourDiDLooLo': fmt(P['vs124']['loo_range'][0]), 'TourDiDLooHi': fmt(P['vs124']['loo_range'][1]),
        'TourDiDNoFour': fmt(P['vs12']['did']), 'TourDiDNoFourP': fmt_p(P['vs12']['p_two_sided']),
        'TourDiDNoFourPone': fmt_p(P['vs12']['p_one_sided_greater']),
        'TourAssign': f"{P['vs124']['n_assignments']:,}".replace(',', '{,}'),
        'TourAssignNoFour': f"{P['vs12']['n_assignments']:,}".replace(',', '{,}'),
        'TourCross': fmt(cs['obs']), 'TourCrossP': fmt_p(cs['p_two_sided']),
        'TourCrossNoFour': fmt(cs12['obs']), 'TourCrossNoFourP': fmt_p(cs12['p_two_sided']),
        'TourOrgArmMarkers': str(ag['arm_markers_complete']),
        'TourOrgArmMarkersAll': str(ag['arm_markers_total']),
        'TourOrgRankSame': fmt(100 * ag['rank_identical_share'], 1),
        'TourOrgRankMaxDiff': str(int(ag['rank_abs_diff_max'])),
        'TourOrgDiD': fmt(og['vs124']['obs']), 'TourOrgDiDP': fmt_p(og['vs124']['p_two_sided']),
        'TourOrgModels': str(og['vs124']['n_models']),
        'TourLevDiDNoFour': fmt(ol['vs12']['obs']), 'TourLevDiDNoFourP': fmt_p(ol['vs12']['p_two_sided']),
        'TourLevModels': str(ol['vs12']['n_models']),
        'TourShiftPArmOne': fmt_p(P['arm_shift']['1']['p_two_sided']),
        'TourShiftPArmTwo': fmt_p(P['arm_shift']['2']['p_two_sided']),
        'TourShiftPArmThree': fmt_p(P['arm_shift']['3']['p_two_sided']),
        'TourShiftPArmFour': fmt_p(P['arm_shift']['4']['p_two_sided']),
        'TourFixedDiD': fmt(r[f'H{PRIMARY_H}_behind_d_gross_c']['vs124']['did']),
        'TourFixedDiDP': fmt_p(r[f'H{PRIMARY_H}_behind_d_gross_c']['vs124']['p_two_sided']),
        'TourGapDiD': fmt(r[f'H{PRIMARY_H}_gap_pct_d_gross_eqk']['vs124']['did']),
        'TourGapDiDP': fmt_p(r[f'H{PRIMARY_H}_gap_pct_d_gross_eqk']['vs124']['p_two_sided']),
        'TourConstantRank': str(len(r['standing_changes']['constant_rank_from_hour_24'])),
        'TourConvPrompts': str(cv['arm3_prompts']),
        'TourConvOwnRankOrg': str(cv['own_rank_matches_organiser']),
        'TourConvAllRankOrg': str(cv['all_ranks_match_organiser']),
        'TourConvOwnRankChain': str(cv['own_rank_matches_chain']),
        'TourConvAllRankChain': str(cv['all_ranks_match_chain']),
        'TourConvValueGap': fmt(cv['max_abs_value_gap_organiser_pct'], 2),
    }
    for H in HORIZONS:
        if H == PRIMARY_H:
            continue
        q = r[f'H{H}_behind_d_gross_eqk']
        mac[f'TourDiD{word(H)}'] = fmt(q['vs124']['did'])
        mac[f'TourDiD{word(H)}P'] = fmt_p(q['vs124']['p_two_sided'])
    lines = ['% Generated by src/tournament_effect.py']
    lines += [f'\\newcommand{{\\al{k}}}{{{v}}}' for k, v in mac.items()]
    (root / 'paper/frl/tournament_numbers.tex').write_text('\n'.join(lines) + '\n')

    label = {('behind', 'd_gross_eqk'): 'Rank, $\\Delta G/E_k$',
             ('behind', 'd_gross_c'): 'Rank, $\\Delta G/C$',
             ('gap_pct', 'd_gross_eqk'): 'Gap, $\\Delta G/E_k$',
             ('behind', 'lvl_gross_eqk'): 'Rank, level $\\bar G/E_k$',
             ('organiser', 'd_gross_eqk'): 'Organiser, $\\Delta G/E_k$',
             ('organiser', 'd_declared_leverage'): 'Organiser, $\\Delta$ declared lev.'}
    body, dropped = [], {}
    for H, x, y, start, it in table:
        name = label[(x, y)] + (f', $k\\ge{start}$' if start else '')
        n = it['vs124']['n_models']
        if n < 8:
            dropped[n] = it.get('accounts_undefined') or []
            name += f'$^{{{n}}}$'
        a = it['arm_mean_rho']
        body.append(
            f"{name} & {H} & {fmt(a['1'])} & {fmt(a['2'])} & {fmt(a['3'])} & {fmt(a['4'])} & "
            f"{fmt(it['vs124']['obs'])} & {fmt_p(it['vs124']['p_two_sided'])} & "
            f"{fmt(it['vs12']['obs'])} & {fmt_p(it['vs12']['p_two_sided'])} \\\\")
    note = ' '.join(f'$^{{{n}}}$DiD over the {n} models whose standing varies in every arm.'
                    for n in sorted(dropped))
    tex = r"""%% Generated by src/tournament_effect.py
\begin{table}[htbp]
\centering
\caption{Interim standing and the following change in gross exposure, Season~1.5.
Columns 1--4: mean over the eight models of the within-account Spearman
correlation between being behind (rank within arm scaled to $[0,1]$, 1 = last;
or the gap to the arm median in per cent of $C$) at formation hour $k$ and the
change in gross exposure over the next $H$ hours, on formation-hour equity
$E_k$ unless stated. DiD: arm~3 (leaderboard in the prompt) minus the mean of
the other arms, within model, averaged over models; $p$: two-sided, exact over
all within-model relabellings of the arm-3 account (%s or %s). Formation
hours overlap and share one market path; one run per cell. Gap: arm-median
equity minus own, per cent of $C$. Organiser: ranks from snapshot equity at
markers where all eight accounts of the arm are present, risk from snapshot
positions. %s Descriptive.}
\label{tab:tournament}
\footnotesize
\setlength{\tabcolsep}{4pt}
\begin{tabular}{lrrrrrrrrr}
\toprule
 & & \multicolumn{4}{c}{Mean $\rho$ by arm} & \multicolumn{2}{c}{vs arms 1, 2, 4} & \multicolumn{2}{c}{vs arms 1, 2} \\
\cmidrule(lr){3-6}\cmidrule(lr){7-8}\cmidrule(lr){9-10}
Standing; risk & $H$ & 1 & 2 & 3 & 4 & DiD & $p$ & DiD & $p$ \\
\midrule
%s
\bottomrule
\end{tabular}
\end{table}
""" % (mac['TourAssign'], mac['TourAssignNoFour'], note, '\n'.join(body))
    (root / 'paper/frl/tournament_table.tex').write_text(tex)


if __name__ == '__main__':
    main()
