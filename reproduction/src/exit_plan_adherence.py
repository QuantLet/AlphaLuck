"""Do the models follow their own declared exit plans? Season 1.5.

Run: python src/exit_plan_adherence.py [--archive PATH] [--output PATH]

Inputs
  * Organiser hourly snapshots, data/raw/nof1_hourly/account_totals_hourly.zip
    (positions.csv): per account-hour-position the declared stop_loss,
    profit_target and invalidation_condition. Loaded and mapped to accounts
    with src/organiser_hourly.py. A zero level ("N/A - no position") or a
    missing one is treated as undeclared.
  * Complete on-chain fills (data/derived/fills.parquet, from
    data/raw/hl/userFillsByTime) and the own-account liquidation flags in the
    raw fill pages (organiser_hourly.liquidation_events).
  * Prices: pooled trade prints of all Season 1.5 accounts (primary, the
    trigger the frozen-book analysis uses); the five-minute last-print grid
    (data/derived/panel.parquet); the organiser's current_price at its
    snapshots; and Hyperliquid four-hour candles (data/raw/hl/candles4h),
    whose venue-wide highs and lows bound crossings that pooled prints miss.
    Five-minute candles are not served for this period
    (data/derived/candle_probe.json).

Episodes
  A position episode is a flat -> non-flat -> flat cycle in one account and
  instrument, from fills inside the official window. A fill that reverses
  the position is split: the part that flattens closes one episode and the
  rest opens the next, with the fee shared pro rata. Episodes still open at
  the official close are marked at the last pooled print at the close, as in
  src/pnl_decomposition.py; fills after the close are ignored. Organiser
  snapshots are assigned to the episode open at their timestamp in the same
  instrument and direction. A snapshot row is linked to the episode when
  its entry_time lies between LINK_MIN minutes before the first fill and
  the snapshot. Rows with entry_time 0 are not linked: most repeat exactly
  the levels of an earlier episode in the same instrument and about a
  quarter put the stop or target on the wrong side of the entry, so they
  are stale. Primary results use linked rows only; including them is a
  sensitivity ("unlinked").

Declared plan
  The plan in force at time t is the stop and target of the latest snapshot
  at or before t (a step function). Primary: only times from the first
  snapshot onward are tested, so every tested level was observed at or
  before the time it is applied ("observed"). Sensitivities: the first
  snapshot's plan applied from the open ("backfill"), and the first plan
  held fixed for the whole episode ("entry plan").

Classification (closed episodes with an observed plan)
  tau is the first price at or beyond either level, with an optional buffer
  (a crossing needs price beyond the level by BUFFER of the level), using
  prices strictly before the closing fill.
    liquidation    the closing fill is an own-account liquidation
    missed_sl/tp   a level was crossed and the position stayed open for
                   more than GRACE minutes after tau (open episodes too,
                   against the close)
    sl/tp          crossed and closed within GRACE minutes, or closed
                   without a crossing at a price within NEAR of the level
    discretionary  closed before either level was touched and away from both
    open_no_cross  open at the season close, no crossing
    no_plan        no snapshot with a declared level during the episode

Plan-follow counterfactual
  Exit the whole remaining position at tau, at the crossing price (primary;
  a stop that triggers on the print and fills there) or exactly at the level
  (sensitivity); fills after tau are dropped; otherwise the episode is
  unchanged. Other episodes are kept as they happened, so this is a
  partial counterfactual: the position and decisions that followed are held
  fixed. Gross P&L excludes fees and funding; a fee-adjusted version charges
  the plan exit at the account's average fee rate and saves the fees of the
  dropped fills. Funding is not adjusted.

Inference
  Descriptive. One run per model-arm cell confounds model and configuration.
  The two association checks permute accounts within arm (20,000 draws,
  two-sided on the mean within-arm Spearman correlation), the convention of
  src/inference_audit.py, and are conditional on this panel and price path.

Writes data/derived/exit_plan_adherence.json, exit_plan_episodes.csv (no
organiser levels or text), exit_plan_accounts.csv, exit_plan_sensitivity.csv,
exit_plan_cells.csv, and paper/frl/exitplan_numbers.tex, exitplan_table.tex.
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

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import organiser_hourly as oh
import wallets

CAPITAL = 10_000.0
FLAT = 1e-7
MIN = 60_000
NEAR = (0.001, 0.0025, 0.005, 0.01)
MAIN_NEAR = 0.0025
GRACE = (5, 15, 60)
MAIN_GRACE = 15
BUFFER = (0.0, 0.001, 0.0025)
MAIN_BUFFER = 0.0
SOURCES = ('prints', 'grid5m', 'organiser')
VARIANTS = ('observed', 'backfill', 'entry', 'unlinked')
LINK_MIN = 10          # entry_time may precede the first fill by up to this, minutes
CLASSES = ('sl', 'tp', 'discretionary', 'missed_sl', 'missed_tp', 'liquidation',
           'open_no_cross')
N_PERM = 20_000
SEED = 20261021
ARMS = {1: 'New Baseline', 2: 'Monk Mode', 3: 'Situational Awareness', 4: 'Max Leverage'}


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=HERE.parent)
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--paper', type=Path)
    args = parser.parse_args()
    args.root = args.root.resolve()
    args.archive = args.archive or args.root / 'data/raw/nof1_hourly/account_totals_hourly.zip'
    args.output = args.output or args.root / 'data/derived'
    args.paper = args.paper or args.root / 'paper/frl'
    return args


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ----------------------------------------------------------------- episodes
def build_episodes(fills, lo, hi, liq_tids=frozenset(), close_px=None):
    """Flat -> non-flat -> flat cycles per (tag, coin) inside [lo, hi].

    Returns (episodes, legs). A reversing fill is split into a closing leg
    and an opening leg. close_px maps coin -> price at hi for open episodes.
    """
    f = fills[(fills.time >= lo) & (fills.time <= hi)].sort_values(
        ['tag', 'coin', 'time', 'tid'], kind='mergesort')
    legs, eps = [], []
    for (tag, coin), g in f.groupby(['tag', 'coin'], sort=True):
        pos, cur = 0.0, None
        for r in g.itertuples(index=False):
            s = float(r.signed_sz)
            new = pos + s
            if pos != 0 and abs(new) > FLAT and np.sign(new) != np.sign(pos):
                parts = [-pos, new]
            else:
                parts = [s]
            for part in parts:
                if cur is None:
                    cur = len(eps)
                    eps.append({'ep': cur, 'tag': tag, 'coin': coin,
                                'side': int(np.sign(part)), 't_open': int(r.time)})
                legs.append({'ep': cur, 'time': int(r.time), 'tid': int(r.tid),
                             'oid': int(r.oid), 'px': float(r.px), 'sz': part,
                             'fee': float(r.fee) * abs(part) / abs(s) if s else 0.0,
                             'liq': int(r.tid) in liq_tids})
                pos += part
                if abs(pos) < FLAT:
                    pos = 0.0
                    eps[cur]['t_close'] = int(r.time)
                    cur = None
    legs = pd.DataFrame(legs, columns=['ep', 'time', 'tid', 'oid', 'px', 'sz', 'fee', 'liq'])
    e = pd.DataFrame(eps)
    if 't_close' not in e:
        e['t_close'] = np.nan
    e['closed'] = e.t_close.notna()
    legs['cash'] = -legs.sz * legs.px
    legs['q'] = legs.groupby('ep').sz.cumsum()
    agg = legs.groupby('ep').agg(cash=('cash', 'sum'), fees=('fee', 'sum'),
                                 q_end=('sz', 'sum'), n_fills=('tid', 'size'),
                                 any_liq=('liq', 'any'),
                                 notional_traded=('cash', lambda v: float(np.abs(v).sum())),
                                 max_abs_q=('q', lambda v: float(np.abs(v).max())))
    e = e.join(agg, on='ep')
    e.loc[e.closed, 'q_end'] = 0.0
    first = legs.groupby('ep').first()
    last = legs.groupby('ep').last()
    def vwap(sel):
        w = legs[sel]
        return (w.px * w.sz.abs()).groupby(w.ep).sum() / w.sz.abs().groupby(w.ep).sum()
    e['p_open'] = vwap(legs.oid.values == first.oid.reindex(legs.ep).values).reindex(e.ep).values
    e['p_close'] = vwap(legs.oid.values == last.oid.reindex(legs.ep).values).reindex(e.ep).values
    e['liq_close'] = last.liq.reindex(e.ep).values & e.closed.values
    e.loc[~e.closed, 'p_close'] = np.nan
    mark = e.coin.map(close_px or {}).astype(float)
    e['gross'] = e.cash + np.where(e.closed, 0.0, e.q_end * mark)
    e['t_end'] = np.where(e.closed, e.t_close, hi).astype('int64')
    e['model'] = e.tag.str.split('__').str[2]
    e['arm'] = e.tag.str.split('__').str[1].str[1:].astype(int)
    return e, legs


# ------------------------------------------------------------------- plans
def assign_plans(pos, e, lo, hi):
    """Organiser snapshot rows matched to the episode open at their time."""
    p = pos[(pos.t >= lo) & (pos.t <= hi) & (pos.quantity != 0)].copy()
    p = p.rename(columns={'symbol': 'coin'})
    p['sl'] = p.stop_loss.where(p.stop_loss > 0)
    p['tp'] = p.profit_target.where(p.profit_target > 0)
    p['ep'] = -1
    for (tag, coin), g in e.groupby(['tag', 'coin']):
        sel = p.index[(p.tag == tag) & (p.coin == coin)]
        if not len(sel):
            continue
        g = g.sort_values('t_open')
        t = p.loc[sel, 't'].to_numpy()
        i = np.searchsorted(g.t_open.to_numpy(), t, side='right') - 1
        ok = i >= 0
        j = np.maximum(i, 0)
        end = np.where(g.closed.to_numpy()[j], g.t_end.to_numpy()[j], hi + 1)
        ok &= t < end
        ok &= np.sign(p.loc[sel, 'quantity'].to_numpy()) == g.side.to_numpy()[j]
        p.loc[sel, 'ep'] = np.where(ok, g.ep.to_numpy()[j], -1)
    matched = p[p.ep >= 0].join(e.set_index('ep')[['t_open', 'side', 'p_open']], on='ep')
    # A row is linked to its episode when the organiser's entry_time falls
    # between LINK_MIN minutes before the first fill and the snapshot. Rows
    # with entry_time 0 mostly repeat the levels of an earlier episode in the
    # same instrument (stale) and are excluded from the primary analysis.
    et = matched.entry_time.fillna(0) * 1000
    matched['linked'] = (et > 0) & (et >= matched.t_open - LINK_MIN * MIN) & (et <= matched.t)
    declared = matched[matched.sl.notna() | matched.tp.notna()].sort_values(['ep', 't'])
    plan = declared[declared.linked]
    wrong = ((declared.side * (declared.p_open - declared.sl) <= 0)
             | (declared.side * (declared.tp - declared.p_open) <= 0))
    stale = []
    for _, g in declared.sort_values('t').groupby(['tag', 'coin']):
        seen = {}
        for r in g.itertuples():
            key = (r.sl, r.tp)
            if not r.linked:
                prev = seen.get(key)
                stale.append(prev is not None and prev != r.ep)
            else:
                seen[key] = r.ep
    unl = ~declared.linked
    return plan, declared, {
                  'snapshot_position_rows': int(len(p)), 'matched': int(len(matched)),
                  'unmatched': int((p.ep < 0).sum()), 'with_declared_level': int(len(declared)),
                  'linked_rows': int(len(plan)), 'unlinked_rows': int(unl.sum()),
                  'unlinked_entry_time_zero': int((unl & (declared.entry_time.fillna(0) == 0)).sum()),
                  'unlinked_repeat_earlier_episode_share': float(np.mean(stale)) if stale else None,
                  'wrong_side_share_linked': float(wrong[declared.linked].mean()),
                  'wrong_side_share_unlinked': float(wrong[unl].mean()),
                  'episodes_with_declared_level': int(declared.ep.nunique()),
                  'episodes_with_linked_plan': int(plan.ep.nunique()),
                  'stop_declared_share': float(matched.sl.notna().mean()),
                  'target_declared_share': float(matched.tp.notna().mean()),
                  'invalidation_declared_share': float(
                      matched.invalidation_condition.notna().mean()),
                  'invalidation_na_text': int(matched.invalidation_condition.astype(str)
                                              .str.startswith('N/A').sum())}


def plan_steps(plan):
    """ep -> (snapshot times, stops, targets)."""
    return {ep: (g.t.to_numpy('int64'), g.sl.to_numpy(float), g.tp.to_numpy(float))
            for ep, g in plan.groupby('ep')}


# ---------------------------------------------------------------- crossing
def first_cross(times, prices, a, b, b_inclusive, side, u, sl, tp, buffer=0.0,
                variant='observed'):
    """First price in (a, b) at or beyond the plan in force.

    Returns (time, kind, price, level, fresh) or None; fresh is False when
    the first tested price is already beyond the level (crossed before the
    plan was observed, or at the open). variant: 'observed' tests
    only from the first snapshot u[0]; 'backfill' applies the first plan from
    a; 'entry' applies the first plan throughout.
    """
    i0 = np.searchsorted(times, a, side='right')
    i1 = np.searchsorted(times, b, side='right' if b_inclusive else 'left')
    t, p = times[i0:i1], prices[i0:i1]
    if not len(t):
        return None
    if variant == 'unlinked':
        variant = 'observed'
    if variant == 'entry':
        j = np.zeros(len(t), int)
        keep = t >= u[0]
        t, p, j = t[keep], p[keep], j[keep]
    else:
        j = np.searchsorted(u, t, side='right') - 1
        if variant == 'backfill':
            j = np.maximum(j, 0)
        keep = j >= 0
        t, p, j = t[keep], p[keep], j[keep]
    if not len(t):
        return None
    ls, lt = sl[j], tp[j]
    with np.errstate(invalid='ignore'):
        if side > 0:
            hs, ht = p <= ls * (1 - buffer), p >= lt * (1 + buffer)
        else:
            hs, ht = p >= ls * (1 + buffer), p <= lt * (1 - buffer)
    hit = np.nonzero(hs | ht)[0]
    if not len(hit):
        return None
    k = hit[0]
    kind = 'sl' if hs[k] else 'tp'
    return int(t[k]), kind, float(p[k]), float(ls[k] if kind == 'sl' else lt[k]), bool(k > 0)


def classify(ep, cross, steps, near, grace_min, hi):
    """Adherence class of one episode, given its first crossing."""
    if steps is None:
        return 'no_plan'
    if ep['closed'] and ep['liq_close']:
        return 'liquidation'
    grace = grace_min * MIN
    if cross is not None:
        if cross[0] < ep['t_end'] - grace:
            return 'missed_' + cross[1]
        return cross[1] if ep['closed'] else 'open_no_cross'
    if not ep['closed']:
        return 'open_no_cross'
    u, sl, tp = steps
    j = max(int(np.searchsorted(u, ep['t_close'], side='right')) - 1, 0)
    with np.errstate(invalid='ignore'):
        d_sl = abs(ep['p_close'] / sl[j] - 1) if np.isfinite(sl[j]) else np.inf
        d_tp = abs(ep['p_close'] / tp[j] - 1) if np.isfinite(tp[j]) else np.inf
    if min(d_sl, d_tp) <= near:
        return 'sl' if d_sl <= d_tp else 'tp'
    return 'discretionary'


def plan_follow(ep_legs, cross, fee_rate, at='print'):
    """Gross and fee P&L if the position is closed at the first crossing.

    at='print': the crossing price. at='level': the declared level when the
    crossing is fresh (a resting order at the level), else the crossing
    price; for stops this ignores gap-through and is optimistic.
    """
    tau, _, price, level, fresh = cross
    x = level if (at == 'level' and fresh) else price
    before = ep_legs[ep_legs.time < tau]
    q = float(before.sz.sum())
    gross = float(before.cash.sum()) + q * x
    fees = float(before.fee.sum()) + fee_rate * abs(q) * x
    return gross, fees


# ------------------------------------------------------------ price sources
def price_paths(m, pos, root, lo, hi):
    paths = {'prints': {c: m.prices[c] for c in m.coins}}
    pan = m.panel[(m.panel.t >= lo) & (m.panel.t <= hi)]
    grid = pan.dropna(subset=['px']).drop_duplicates(['coin', 't']).sort_values('t')
    paths['grid5m'] = {c: (g.t.to_numpy('int64'), g.px.to_numpy(float))
                       for c, g in grid.groupby('coin')}
    o = pos[pos.current_price.notna()].rename(columns={'symbol': 'coin'})
    o = o.drop_duplicates(['coin', 't']).sort_values('t')
    paths['organiser'] = {c: (g.t.to_numpy('int64'), g.current_price.to_numpy(float))
                          for c, g in o.groupby('coin')}
    candles = {}
    for c in m.coins:
        d = pd.DataFrame(json.loads((root / f"data/raw/hl/candles4h/{c.replace(':', '_')}.json")
                                    .read_text()))
        candles[c] = (d.t.to_numpy('int64'), d.l.astype(float).to_numpy(),
                      d.h.astype(float).to_numpy())
    return paths, candles


def candle_cross(candles, coin, a, b, side, steps):
    """A four-hour bar inside [a, b] with a constant plan and a range beyond it."""
    t, low, high = candles[coin]
    u, sl, tp = steps
    bar = 4 * 3_600_000
    for k in np.nonzero((t >= a) & (t + bar <= b))[0]:
        j0 = np.searchsorted(u, t[k], side='right') - 1
        j1 = np.searchsorted(u, t[k] + bar, side='left') - 1
        if j0 < 0 or j0 != j1:
            continue
        s, g = sl[j0], tp[j0]
        if side > 0 and ((np.isfinite(s) and low[k] <= s) or (np.isfinite(g) and high[k] >= g)):
            return True
        if side < 0 and ((np.isfinite(s) and high[k] >= s) or (np.isfinite(g) and low[k] <= g)):
            return True
    return False


# --------------------------------------------------------------- revisions
def revisions(plan, e):
    """Changes of declared levels between consecutive snapshots of an episode."""
    p = plan.merge(e[['ep', 'model', 'arm']], on='ep')
    p = p.sort_values(['ep', 't'])
    g = p.groupby('ep')
    p['sl_prev'], p['tp_prev'], p['q_prev'] = g.sl.shift(), g.tp.shift(), g.quantity.shift()
    pairs = p[p.q_prev.notna()].copy()
    rel = lambda a, b: (a / b - 1).abs() > 1e-6
    pairs['sl_change'] = pairs.sl.notna() & pairs.sl_prev.notna() & rel(pairs.sl, pairs.sl_prev)
    pairs['tp_change'] = pairs.tp.notna() & pairs.tp_prev.notna() & rel(pairs.tp, pairs.tp_prev)
    pairs['sl_tighter'] = pairs.sl_change & (pairs.side * (pairs.sl - pairs.sl_prev) > 0)
    pairs['sl_looser'] = pairs.sl_change & (pairs.side * (pairs.sl - pairs.sl_prev) < 0)
    pairs['tp_further'] = pairs.tp_change & (pairs.side * (pairs.tp - pairs.tp_prev) > 0)
    pairs['tp_closer'] = pairs.tp_change & (pairs.side * (pairs.tp - pairs.tp_prev) < 0)
    pairs['same_q'] = (pairs.quantity - pairs.q_prev).abs() < FLAT
    per_ep = pairs.groupby('ep').agg(
        rev_sl=('sl_change', 'sum'), rev_tp=('tp_change', 'sum'),
        rev_sl_looser=('sl_looser', 'sum'), rev_sl_tighter=('sl_tighter', 'sum'),
        rev_tp_further=('tp_further', 'sum'), rev_tp_closer=('tp_closer', 'sum'))
    return pairs, per_ep


def revision_summary(pairs, per_ep, multi):
    def block(pr, pe):
        any_rev = (pe.rev_sl + pe.rev_tp) > 0
        unchanged = pr[pr.same_q]
        return {'snapshot_pairs': int(len(pr)),
                'episodes_with_two_snapshots': int(len(pe)),
                'episodes_with_any_revision': int(any_rev.sum()),
                'episodes_with_any_revision_share': float(any_rev.mean()) if len(pe) else None,
                'pairs_sl_changed': int(pr.sl_change.sum()),
                'pairs_tp_changed': int(pr.tp_change.sum()),
                'sl_tighter': int(pr.sl_tighter.sum()), 'sl_looser': int(pr.sl_looser.sum()),
                'tp_further': int(pr.tp_further.sum()), 'tp_closer': int(pr.tp_closer.sum()),
                'pairs_same_quantity': int(len(unchanged)),
                'sl_looser_same_quantity': int(unchanged.sl_looser.sum()),
                'changes_with_same_quantity_share': float(
                    (pr.sl_change | pr.tp_change)[pr.same_q].sum()
                    / max(1, (pr.sl_change | pr.tp_change).sum()))}
    out = {'all': block(pairs, per_ep)}
    for model, pr in pairs.groupby('model'):
        out[model] = block(pr, per_ep.loc[per_ep.index.isin(pr.ep)])
    return out


# --------------------------------------------------------------- inference
def within_arm_rho(x, y, arm):
    vals = []
    for a in np.unique(arm):
        s = arm == a
        vals.append(stats.spearmanr(x[s], y[s]).statistic)
    return float(np.mean(vals))


def perm_within_arm(x, y, arm, n=N_PERM, seed=SEED):
    """Two-sided within-arm permutation p on the mean Spearman correlation."""
    x, y, arm = np.asarray(x, float), np.asarray(y, float), np.asarray(arm)
    obs = within_arm_rho(x, y, arm)
    rng = np.random.default_rng(seed)
    idx = [np.nonzero(arm == a)[0] for a in np.unique(arm)]
    xp = x.copy()
    extreme = 0
    for _ in range(n):
        for i in idx:
            xp[i] = x[rng.permutation(i)]
        extreme += abs(within_arm_rho(xp, y, arm)) >= abs(obs) - 1e-12
    return {'rho': obs, 'p_two_sided': (extreme + 1) / (n + 1), 'draws': n}


# -------------------------------------------------------------------- main
def run_classes(e, legs_by_ep, steps, paths, hi, fee_rate, source, buffer, variant):
    """Crossings, classes for every NEAR x GRACE pair, and the plan-follow P&L."""
    times_prices = paths[source]
    rows = []
    for ep in e.itertuples(index=False):
        st = steps.get(ep.ep)
        cross = None
        if st is not None:
            times, prices = times_prices[ep.coin]
            cross = first_cross(times, prices, ep.t_open, ep.t_end, not ep.closed,
                                ep.side, *st, buffer=buffer, variant=variant)
        r = {'ep': ep.ep, 'planned': st is not None,
             'tau': cross[0] if cross else np.nan, 'cross_kind': cross[1] if cross else None,
             'fresh': cross[4] if cross else None,
             'gap_pct': 100 * abs(cross[2] / cross[3] - 1) if cross else np.nan}
        epd = ep._asdict()
        for near in NEAR:
            for grace in GRACE:
                r[f'class_{near}_{grace}'] = classify(epd, cross, st, near, grace, hi)
        if cross is not None:
            lg = legs_by_ep[ep.ep]
            for at in ('print', 'level'):
                g, f = plan_follow(lg, cross, fee_rate[ep.tag], at)
                r[f'plan_gross_{at}'], r[f'plan_fees_{at}'] = g, f
        else:
            for at in ('print', 'level'):
                r[f'plan_gross_{at}'], r[f'plan_fees_{at}'] = ep.gross, ep.fees
        rows.append(r)
    return pd.DataFrame(rows)


def shares(classes, mask=None):
    c = classes if mask is None else classes[mask]
    c = c[c != 'no_plan']
    n = len(c)
    return {k: float((c == k).sum() / n) if n else None for k in CLASSES} | {'n': int(n)}


def main():
    args = arguments()
    root, out = args.root, args.output
    acc, pos, _ = oh.load_archive(args.archive, root)
    m = oh.Market(root)
    lo, hi = m.lo, m.hi
    liq_fills, _ = oh.liquidation_events(root)
    liq_tids = frozenset(int(x) for x in liq_fills.tid)
    close_px = {c: float(m.price(c, np.array([hi]))[0]) for c in m.coins}
    e, legs = build_episodes(m.fills, lo, hi, liq_tids, close_px)
    legs_by_ep = {k: g for k, g in legs.groupby('ep')}

    # identity: episode gross equals the decomposition's fill-implied gross
    dec = pd.read_csv(root / 'data/derived/a1_pnl_decomposition.csv')
    dec = dec[dec.season.eq('S15')].set_index('tag')
    gross_acct = e.groupby('tag').gross.sum()
    identity_gap = float((gross_acct - dec.true_gross_pnl.reindex(gross_acct.index)).abs().max())
    if identity_gap > 5.0:   # exchange closedPnl rounding in the decomposition
        raise ValueError(f'Episode gross does not match the decomposition: {identity_gap}')

    plan, declared, plan_cov = assign_plans(pos, e, lo, hi)
    steps = plan_steps(plan)
    steps_all = plan_steps(declared)
    paths, candles = price_paths(m, pos, root, lo, hi)
    f_all = m.fills[(m.fills.time >= lo) & (m.fills.time <= hi)]
    fee_rate = (f_all.groupby('tag').fee.sum()
                / (f_all.sz * f_all.px).groupby(f_all.tag).sum()).to_dict()

    # snapshot-level: organiser's own price already beyond the declared level
    snap = plan.merge(e[['ep', 'model', 'arm']], on='ep')
    snap = snap[snap.current_price.notna()]
    beyond_sl = snap.sl.notna() & (snap.side * (snap.current_price - snap.sl) <= 0)
    beyond_tp = snap.tp.notna() & (snap.side * (snap.current_price - snap.tp) >= 0)
    snap = snap.assign(beyond_sl=beyond_sl, beyond_tp=beyond_tp)
    snapshot_level = {
        'rows': int(len(snap)),
        'beyond_stop_share': float(beyond_sl.sum() / snap.sl.notna().sum()),
        'beyond_target_share': float(beyond_tp.sum() / snap.tp.notna().sum()),
        'by_model_beyond_stop_share': snap.groupby('model').beyond_sl.mean().to_dict(),
        'by_model_beyond_target_share': snap.groupby('model').beyond_tp.mean().to_dict(),
        'by_arm_beyond_stop_share': {str(k): v for k, v in
                                     snap.groupby('arm').beyond_sl.mean().items()},
    }

    # all specifications
    runs = {}
    for source in SOURCES:
        for buffer in BUFFER:
            for variant in VARIANTS:
                primary_axis = (source == 'prints') + (buffer == MAIN_BUFFER) + (variant == 'observed')
                if primary_axis < 2:
                    continue      # one axis varied at a time
                runs[(source, buffer, variant)] = run_classes(
                    e, legs_by_ep, steps_all if variant == 'unlinked' else steps,
                    paths, hi, fee_rate, source, buffer, variant)
    main_run = runs[('prints', MAIN_BUFFER, 'observed')]
    main_col = f'class_{MAIN_NEAR}_{MAIN_GRACE}'
    ep = e.merge(main_run, on='ep')
    ep['cls'] = ep[main_col]
    ep['delta_gross'] = ep.plan_gross_print - ep.gross
    ep['delta_net'] = ep.delta_gross - (ep.plan_fees_print - ep.fees)
    ep['delta_gross_level'] = ep.plan_gross_level - ep.gross
    ep['hold_h'] = (ep.t_end - ep.t_open) / 3_600_000
    ep['lag_min'] = (ep.t_end - ep.tau) / MIN

    # crossing-to-close lag for closed, crossed episodes (motivates GRACE)
    lag = ep[ep.closed & ep.tau.notna() & ~ep.liq_close].lag_min
    lag_summary = {'episodes': int(len(lag)),
                   **{f'within_{x}min': float((lag <= x).mean()) for x in (1, 5, 15, 60, 240)},
                   'median_min': float(lag.median()),
                   'quantiles_min': {str(q): float(lag.quantile(q)) for q in (.25, .5, .75, .9)}}

    # how far beyond the level the crossing price lies
    cr = ep[ep.tau.notna()]
    fr = cr.fresh.astype(bool)
    crossing_summary = {
        'crossed_episodes': int(len(cr)), 'fresh': int(fr.sum()), 'stale': int((~fr).sum()),
        'gap_pct_median_fresh': float(cr[fr].gap_pct.median()),
        'gap_pct_median_stale': float(cr[~fr].gap_pct.median()),
        'gap_pct_median_fresh_stop': float(cr[fr & cr.cross_kind.eq('sl')].gap_pct.median()),
        'gap_pct_median_fresh_target': float(cr[fr & cr.cross_kind.eq('tp')].gap_pct.median()),
        'gap_pct_p90_fresh': float(cr[fr].gap_pct.quantile(.9)),
    }

    # candle check: crossings missed by pooled prints
    pl = ep[ep.planned]
    unseen = pl[(pl.tau.isna() | (pl.tau >= pl.t_end - MAIN_GRACE * MIN)) & ~pl.liq_close]
    candle_hits = 0
    for r in unseen.itertuples():
        st = steps[r.ep]
        if candle_cross(candles, r.coin, st[0][0], r.t_end - MAIN_GRACE * MIN, r.side, st):
            candle_hits += 1

    # coverage
    cov = {
        'episodes': int(len(ep)), 'closed': int(ep.closed.sum()),
        'open_at_close': int((~ep.closed).sum()),
        'planned': int(ep.planned.sum()),
        'planned_share': float(ep.planned.mean()),
        'planned_share_of_abs_gross': float(ep[ep.planned].gross.abs().sum() / ep.gross.abs().sum()),
        'planned_share_of_gross_notional': float(ep[ep.planned].notional_traded.sum()
                                                 / ep.notional_traded.sum()),
        'planned_gross_usd': float(ep[ep.planned].gross.sum()),
        'unplanned_gross_usd': float(ep[~ep.planned].gross.sum()),
        'median_hold_h_planned': float(ep[ep.planned].hold_h.median()),
        'median_hold_h_unplanned': float(ep[~ep.planned].hold_h.median()),
        'episodes_over_2h_planned_share': float(ep[ep.hold_h > 2].planned.mean()),
        'liquidated_episodes': int(ep.liq_close.sum()),
        'episodes_with_partial_liquidation': int((ep.any_liq & ~ep.liq_close).sum()),
        'liquidations_after_stop_cross': int((ep.liq_close & ep.cross_kind.eq('sl')).sum()),
        'liquidations_planned': int((ep.liq_close & ep.planned).sum()),
    }

    # class shares and P&L by model, arm and overall
    def pnl_block(d):
        return {'episodes': int(len(d)), 'planned': int(d.planned.sum()),
                'gross_usd': float(d.gross.sum()),
                'plan_minus_actual_gross_usd': float(d.delta_gross.sum()),
                'plan_minus_actual_net_usd': float(d.delta_net.sum()),
                'plan_minus_actual_gross_level_usd': float(d.delta_gross_level.sum()),
                'missed_sl_delta_usd': float(d[d.cls.eq('missed_sl')].delta_gross.sum()),
                'missed_tp_delta_usd': float(d[d.cls.eq('missed_tp')].delta_gross.sum()),
                'liquidation_delta_usd': float(d[d.cls.eq('liquidation')].delta_gross.sum()),
                'other_delta_usd': float(d[~d.cls.isin(['missed_sl', 'missed_tp', 'liquidation'])]
                                         .delta_gross.sum()),
                'gross_by_class_usd': {k: float(v) for k, v in d.groupby('cls').gross.sum().items()},
                'discretionary_in_profit_share': float((d[d.cls.eq('discretionary')].gross > 0).mean())
                if d.cls.eq('discretionary').any() else None,
                'classes': shares(d.cls)}
    overall = pnl_block(ep)
    by_model = {k: pnl_block(d) for k, d in ep.groupby('model')}
    by_arm = {str(k): pnl_block(d) for k, d in ep.groupby('arm')}
    counts = ep[ep.planned].cls.value_counts().to_dict()

    # account level and the timing contribution
    acct = ep.groupby('tag').agg(
        model=('model', 'first'), arm=('arm', 'first'), episodes=('ep', 'size'),
        planned=('planned', 'sum'), gross=('gross', 'sum'),
        delta_gross=('delta_gross', 'sum'), delta_net=('delta_net', 'sum'),
        delta_gross_level=('delta_gross_level', 'sum'))
    for k in CLASSES:
        acct[f'n_{k}'] = ep[ep.planned].groupby('tag').cls.apply(lambda s: (s == k).sum()).reindex(acct.index).fillna(0).astype(int)
    rated = acct[[f'n_{k}' for k in CLASSES]].sum(axis=1)
    acct['missed_share'] = (acct.n_missed_sl + acct.n_missed_tp) / rated
    acct['missed_sl_share'] = acct.n_missed_sl / rated
    acct['timing_exec'] = (dec.timing_pnl - dec.slippage).reindex(acct.index)
    acct['exposure'] = dec.exposure_pnl.reindex(acct.index)
    acct['net'] = dec.net_pnl.reindex(acct.index)
    for c in ('gross', 'delta_gross', 'delta_net', 'delta_gross_level', 'timing_exec',
              'exposure', 'net'):
        acct[f'{c}_pp'] = 100 * acct[c] / CAPITAL
    acct = acct.reset_index()

    arm = acct.arm.to_numpy()
    tests = {
        'delta_gross_vs_timing_exec': perm_within_arm(acct.delta_gross_pp, acct.timing_exec_pp, arm),
        'missed_share_vs_net_return': perm_within_arm(acct.missed_share, acct.net_pp, arm, seed=SEED + 1),
        'missed_sl_share_vs_timing_exec': perm_within_arm(acct.missed_sl_share, acct.timing_exec_pp,
                                                          arm, seed=SEED + 2),
    }
    book = CAPITAL * len(acct)
    explain = {
        'timing_exec_pp_total': float(100 * acct.timing_exec.sum() / book),
        'plan_minus_actual_gross_pp_total': float(100 * acct.delta_gross.sum() / book),
        'plan_minus_actual_net_pp_total': float(100 * acct.delta_net.sum() / book),
        'plan_minus_actual_gross_level_pp_total': float(100 * acct.delta_gross_level.sum() / book),
        'accounts_plan_ahead_gross': int((acct.delta_gross > 0).sum()),
        'accounts_plan_ahead_net': int((acct.delta_net > 0).sum()),
        'share_of_timing_loss_offset_gross': float(-acct.delta_gross.sum() / acct.timing_exec.sum()),
        'by_model_pp_of_40k': acct.groupby('model')[['delta_gross', 'delta_net', 'timing_exec']]
        .sum().div(4 * CAPITAL / 100).to_dict('index'),
        'by_arm_pp_of_80k': {str(k): v for k, v in acct.groupby('arm')[
            ['delta_gross', 'delta_net', 'timing_exec']].sum().div(8 * CAPITAL / 100)
            .to_dict('index').items()},
    }

    # sensitivity table
    sens = []
    for (source, buffer, variant), r in runs.items():
        d = e.merge(r, on='ep')
        dg = (d.plan_gross_print - d.gross).sum()
        dn = dg - (d.plan_fees_print - d.fees).sum()
        for near in NEAR:
            for grace in GRACE:
                c = d[f'class_{near}_{grace}']
                sh = shares(c)
                sens.append({'source': source, 'buffer': buffer, 'variant': variant,
                             'near': near, 'grace_min': grace, **sh,
                             'missed': (sh['missed_sl'] or 0) + (sh['missed_tp'] or 0),
                             'plan_minus_actual_gross_pp': 100 * dg / book,
                             'plan_minus_actual_net_pp': 100 * dn / book,
                             'primary': (source, buffer, variant, near, grace)
                             == ('prints', MAIN_BUFFER, 'observed', MAIN_NEAR, MAIN_GRACE)})
    sens = pd.DataFrame(sens)
    def srange(sub, col):
        return [float(sub[col].min()), float(sub[col].max())]
    p_sub = sens[(sens.source == 'prints') & (sens.buffer == MAIN_BUFFER) & (sens.variant == 'observed')]
    sens_summary = {
        'tolerances_missed_range': srange(p_sub, 'missed'),
        'tolerances_discretionary_range': srange(p_sub, 'discretionary'),
        'tolerances_sl_range': srange(p_sub, 'sl'),
        'tolerances_tp_range': srange(p_sub, 'tp'),
        'by_source_primary_tolerances': sens[(sens.near == MAIN_NEAR) & (sens.grace_min == MAIN_GRACE)
                                             & (sens.buffer == MAIN_BUFFER)
                                             & (sens.variant == 'observed')]
        .set_index('source')[['missed', 'missed_sl', 'missed_tp', 'sl', 'tp', 'discretionary',
                              'plan_minus_actual_gross_pp', 'plan_minus_actual_net_pp']].to_dict('index'),
        'by_buffer': sens[(sens.near == MAIN_NEAR) & (sens.grace_min == MAIN_GRACE)
                          & (sens.source == 'prints') & (sens.variant == 'observed')]
        .assign(buffer=lambda d: d.buffer.astype(str)).set_index('buffer')[
            ['missed', 'plan_minus_actual_gross_pp']].to_dict('index'),
        'by_variant': sens[(sens.near == MAIN_NEAR) & (sens.grace_min == MAIN_GRACE)
                           & (sens.source == 'prints') & (sens.buffer == MAIN_BUFFER)]
        .set_index('variant')[['n', 'missed', 'sl', 'tp', 'discretionary',
                               'plan_minus_actual_gross_pp']].to_dict('index'),
        'candle_crossings_not_seen_in_prints': int(candle_hits),
        'candle_checked_episodes': int(len(unseen)),
    }

    pairs, per_ep = revisions(plan, e)
    multi = per_ep.index
    rev = revision_summary(pairs, per_ep, multi)
    ep = ep.join(per_ep, on='ep')
    for c in per_ep.columns:
        ep[c] = ep[c].fillna(0).astype(int)
    revised = ep[ep.planned & ((ep.rev_sl + ep.rev_tp) > 0)]
    rev['missed_share_revised'] = shares(revised.cls)
    rev['missed_share_unrevised'] = shares(ep[ep.planned & ((ep.rev_sl + ep.rev_tp) == 0)
                                             ].cls)

    # cells: model x arm (aggregate, one account each)
    cells = acct[['tag', 'model', 'arm', 'episodes', 'planned', *[f'n_{k}' for k in CLASSES],
                  'missed_share', 'gross_pp', 'delta_gross_pp', 'delta_net_pp',
                  'delta_gross_level_pp', 'timing_exec_pp', 'exposure_pp', 'net_pp']]

    report = {
        'definitions': {
            'episode': 'flat to non-flat to flat in one account-instrument, official window; reversing fills split',
            'plan_in_force': 'latest organiser snapshot at or before t; primary tests from the first snapshot on',
            'crossing': 'first price at or beyond a declared level (stop or target), prices strictly before the closing fill',
            'near_tolerance_primary': MAIN_NEAR, 'near_tolerances': list(NEAR),
            'grace_minutes_primary': MAIN_GRACE, 'grace_minutes': list(GRACE),
            'buffer_primary': MAIN_BUFFER, 'buffers': list(BUFFER),
            'price_source_primary': 'pooled trade prints of all Season 1.5 accounts',
            'plan_follow': 'exit the remaining position at the first crossing print; fills after it dropped',
            'undeclared': 'stop_loss or profit_target zero or missing',
        },
        'coverage': cov, 'plan_coverage': plan_cov,
        'identity_episode_gross_vs_decomposition_max_abs_usd': identity_gap,
        'classes_primary': overall['classes'], 'class_counts_primary': counts,
        'pnl_overall': overall, 'by_model': by_model, 'by_arm': by_arm,
        'explain_timing': explain, 'tests': tests,
        'crossing_to_close_lag': lag_summary, 'crossing_gap': crossing_summary,
        'snapshot_level': snapshot_level, 'revisions': rev,
        'sensitivity': sens_summary,
        'limitations': [
            'Plans are observed only at hourly organiser snapshots; episodes closed before a snapshot have no observed plan, and revisions inside an hour are not seen.',
            'Pooled prints of 32 accounts are not the venue price; four-hour candles show additional crossings.',
            'The plan-follow counterfactual holds all other decisions fixed and ignores funding and price impact.',
            'Invalidation conditions are free text and are not evaluated.',
            'One run per model-arm cell; associations are descriptive.',
        ],
        'input_sha256': {str(p.relative_to(root)): digest(p) for p in
                         m.inputs + [args.archive, root / 'data/derived/a1_pnl_decomposition.csv']},
        'source_sha256': {n: digest(HERE / n) for n in
                          ('exit_plan_adherence.py', 'organiser_hourly.py')},
    }
    out.mkdir(parents=True, exist_ok=True)
    cols = ['ep', 'tag', 'model', 'arm', 'coin', 'side', 't_open', 't_end', 'closed', 'n_fills',
            'liq_close', 'planned', 'cls', 'cross_kind', 'fresh', 'gap_pct', 'tau', 'lag_min',
            'gross', 'fees',
            'delta_gross', 'delta_net', 'delta_gross_level', 'rev_sl', 'rev_tp',
            'rev_sl_looser', 'rev_sl_tighter', 'rev_tp_further', 'rev_tp_closer']
    (out / 'organiser_hourly').mkdir(exist_ok=True)
    ep[cols].to_csv(out / 'organiser_hourly' / 'exit_plan_episodes.csv', index=False)
    cells.to_csv(out / 'exit_plan_accounts.csv', index=False)
    sens.to_csv(out / 'exit_plan_sensitivity.csv', index=False)
    model_rows = []
    for k, b in list(by_model.items()) + [(f'arm{a}', b) for a, b in by_arm.items()] + [('all', overall)]:
        model_rows.append({'group': k, **{f'share_{c}': b['classes'][c] for c in CLASSES},
                           'rated': b['classes']['n'], 'episodes': b['episodes'],
                           'planned': b['planned'],
                           'plan_minus_actual_gross_usd': b['plan_minus_actual_gross_usd'],
                           'plan_minus_actual_net_usd': b['plan_minus_actual_net_usd']})
    pd.DataFrame(model_rows).to_csv(out / 'exit_plan_cells.csv', index=False)
    (out / 'exit_plan_adherence.json').write_text(
        json.dumps(report, indent=2, allow_nan=False, default=float) + '\n')
    render(report, acct, args.paper)
    print(json.dumps({k: report[k] for k in ('coverage', 'classes_primary', 'explain_timing',
                                             'tests', 'crossing_to_close_lag', 'snapshot_level',
                                             'sensitivity')}, indent=1, default=float))


# ------------------------------------------------------------------ render
def fmt(x, d=1):
    s = f'{x:,.{d}f}'.replace(',', '{,}')
    return s.replace('-', '\\ensuremath{-}') if x < 0 else s


def words(n):
    """CamelCase macro suffix from a short tag (LaTeX macros take letters only)."""
    return ''.join(ch for ch in n.title() if ch.isalpha())


MODEL_ORDER = ['claude-sonnet-4-5', 'deepseek-chat-v3.1', 'gemini-3-pro-preview', 'gpt-5.1',
               'grok-4', 'kimi-k2-thinking', 'qwen3-max', 'typhoon']
MODEL_TEX = {'claude-sonnet-4-5': 'Claude Sonnet 4.5', 'deepseek-chat-v3.1': 'DeepSeek V3.1',
             'gemini-3-pro-preview': 'Gemini 3 Pro', 'gpt-5.1': 'GPT-5.1', 'grok-4': 'Grok 4',
             'kimi-k2-thinking': 'Kimi K2 Thinking', 'qwen3-max': 'Qwen3 Max',
             'typhoon': 'typhoon'}


def render(r, acct, paper):
    cov, cl, ex, t = r['coverage'], r['classes_primary'], r['explain_timing'], r['tests']
    sn, sv, lag, rv = r['snapshot_level'], r['sensitivity'], r['crossing_to_close_lag'], r['revisions']
    pct = lambda v, d=1: fmt(100 * v, d)
    src = sv['by_source_primary_tolerances']
    var = sv['by_variant']
    macros = {
        'Episodes': fmt(cov['episodes'], 0), 'Planned': fmt(cov['planned'], 0),
        'PlannedShare': pct(cov['planned_share']),
        'PlannedGrossShare': pct(cov['planned_share_of_abs_gross']),
        'PlannedNotionalShare': pct(cov['planned_share_of_gross_notional']),
        'HoldPlanned': fmt(cov['median_hold_h_planned'], 1),
        'HoldUnplanned': fmt(cov['median_hold_h_unplanned'] * 60, 0),
        'Rated': fmt(cl['n'], 0),
        'Declared': fmt(r['plan_coverage']['episodes_with_declared_level'], 0),
        'LinkedRows': fmt(r['plan_coverage']['linked_rows'], 0),
        'UnlinkedRows': fmt(r['plan_coverage']['unlinked_rows'], 0),
        'UnlinkedRepeat': pct(r['plan_coverage']['unlinked_repeat_earlier_episode_share'], 0),
        'WrongLinked': pct(r['plan_coverage']['wrong_side_share_linked'], 1),
        'WrongUnlinked': pct(r['plan_coverage']['wrong_side_share_unlinked'], 0),
        'MissedUnlinked': pct(var['unlinked']['missed']),
        'PlanUnlinked': fmt(var['unlinked']['plan_minus_actual_gross_pp'], 2),
        'DiscProfit': pct(r['pnl_overall']['discretionary_in_profit_share'], 0),
        'GapFresh': fmt(r['crossing_gap']['gap_pct_median_fresh'], 2),
        'PlanBufferHi': fmt(sv['by_buffer'][str(BUFFER[-1])]['plan_minus_actual_gross_pp'], 2),
        'PlanMin': fmt(min([src[k]['plan_minus_actual_gross_pp'] for k in src]
                           + [var[k]['plan_minus_actual_gross_pp'] for k in ('observed', 'backfill', 'entry')]
                           + [v['plan_minus_actual_gross_pp'] for v in sv['by_buffer'].values()]), 2),
        'PlanMax': fmt(max([src[k]['plan_minus_actual_gross_pp'] for k in src]
                           + [var[k]['plan_minus_actual_gross_pp'] for k in ('observed', 'backfill', 'entry')]
                           + [v['plan_minus_actual_gross_pp'] for v in sv['by_buffer'].values()]
                           + [r['explain_timing']['plan_minus_actual_gross_level_pp_total']]), 2),
        'SL': pct(cl['sl']), 'TP': pct(cl['tp']), 'Disc': pct(cl['discretionary']),
        'MissedSL': pct(cl['missed_sl']), 'MissedTP': pct(cl['missed_tp']),
        'Missed': pct(cl['missed_sl'] + cl['missed_tp']),
        'Liq': pct(cl['liquidation']), 'OpenNoCross': pct(cl['open_no_cross']),
        'LiqN': str(cov['liquidated_episodes']), 'LiqPlanned': str(cov['liquidations_planned']),
        'LiqAfterStop': str(cov['liquidations_after_stop_cross']),
        'Near': fmt(100 * r['definitions']['near_tolerance_primary'], 2),
        'Grace': str(r['definitions']['grace_minutes_primary']),
        'MissedLo': pct(sv['tolerances_missed_range'][0]), 'MissedHi': pct(sv['tolerances_missed_range'][1]),
        'DiscLo': pct(sv['tolerances_discretionary_range'][0]),
        'DiscHi': pct(sv['tolerances_discretionary_range'][1]),
        'MissedGrid': pct(src['grid5m']['missed']), 'MissedOrg': pct(src['organiser']['missed']),
        'MissedBackfill': pct(var['backfill']['missed']), 'MissedEntry': pct(var['entry']['missed']),
        'CandleExtra': str(sv['candle_crossings_not_seen_in_prints']),
        'CandleChecked': fmt(sv['candle_checked_episodes'], 0),
        'LagOne': pct(lag['within_1min']), 'LagFifteen': pct(lag['within_15min']),
        'LagMedian': fmt(lag['median_min'], 0),
        'SnapBeyondStop': pct(sn['beyond_stop_share']), 'SnapBeyondTarget': pct(sn['beyond_target_share']),
        'RevShare': pct(rv['all']['episodes_with_any_revision_share']),
        'RevLooser': fmt(rv['all']['sl_looser'], 0), 'RevTighter': fmt(rv['all']['sl_tighter'], 0),
        'RevTPFurther': fmt(rv['all']['tp_further'], 0), 'RevTPCloser': fmt(rv['all']['tp_closer'], 0),
        'TimingExec': fmt(ex['timing_exec_pp_total'], 2),
        'PlanGross': fmt(ex['plan_minus_actual_gross_pp_total'], 2),
        'PlanNet': fmt(ex['plan_minus_actual_net_pp_total'], 2),
        'PlanLevel': fmt(ex['plan_minus_actual_gross_level_pp_total'], 2),
        'PlanGrid': fmt(src['grid5m']['plan_minus_actual_gross_pp'], 2),
        'PlanOrg': fmt(src['organiser']['plan_minus_actual_gross_pp'], 2),
        'PlanBackfill': fmt(var['backfill']['plan_minus_actual_gross_pp'], 2),
        'PlanEntry': fmt(var['entry']['plan_minus_actual_gross_pp'], 2),
        'PlanAhead': str(ex['accounts_plan_ahead_gross']),
        'PlanAheadNet': str(ex['accounts_plan_ahead_net']),
        'OffsetShare': pct(ex['share_of_timing_loss_offset_gross'], 0),
        'RhoTiming': fmt(t['delta_gross_vs_timing_exec']['rho'], 2),
        'PTiming': fmt(t['delta_gross_vs_timing_exec']['p_two_sided'], 3),
        'RhoMissedNet': fmt(t['missed_share_vs_net_return']['rho'], 2),
        'PMissedNet': fmt(t['missed_share_vs_net_return']['p_two_sided'], 3),
        'RhoStopTiming': fmt(t['missed_sl_share_vs_timing_exec']['rho'], 2),
        'PStopTiming': fmt(t['missed_sl_share_vs_timing_exec']['p_two_sided'], 3),
    }
    lines = ['% Generated by src/exit_plan_adherence.py']
    lines += [f'\\newcommand{{\\alExit{k}}}{{{v}}}' for k, v in macros.items()]
    (paper / 'exitplan_numbers.tex').write_text('\n'.join(lines) + '\n')

    rows = []
    groups = [(MODEL_TEX[mo], r['by_model'][mo], ex['by_model_pp_of_40k'][mo], 4) for mo in MODEL_ORDER]
    groups += [(f'Arm {a}', r['by_arm'][a], ex['by_arm_pp_of_80k'][a], 8) for a in sorted(r['by_arm'])]
    for name, b, pp, _ in groups:
        c = b['classes']
        rows.append(f"{name} & {fmt(b['planned'], 0)}/{fmt(b['episodes'], 0)} & "
                    f"{pct(c['sl'], 0)} & {pct(c['tp'], 0)} & {pct(c['discretionary'], 0)} & "
                    f"{pct(c['missed_sl'], 0)} & {pct(c['missed_tp'], 0)} & "
                    f"{pct(c['liquidation'] + c['open_no_cross'], 0)} & "
                    f"${fmt(pp['delta_gross'], 2)}$ & ${fmt(pp['timing_exec'], 2)}$ \\\\")
    o = r['pnl_overall']
    c = o['classes']
    total = (f"All & {fmt(o['planned'], 0)}/{fmt(o['episodes'], 0)} & {pct(c['sl'], 0)} & "
             f"{pct(c['tp'], 0)} & {pct(c['discretionary'], 0)} & {pct(c['missed_sl'], 0)} & "
             f"{pct(c['missed_tp'], 0)} & {pct(c['liquidation'] + c['open_no_cross'], 0)} & "
             f"${fmt(ex['plan_minus_actual_gross_pp_total'], 2)}$ & "
             f"${fmt(ex['timing_exec_pp_total'], 2)}$ \\\\")
    tex = r"""\begin{table}[ht]
\centering\small
\caption{Exits against declared plans, Season~1.5. Episodes run from flat to
flat in one account and instrument; ``planned'' episodes have at least one
organiser snapshot with a declared stop or target. Shares are per cent of
planned episodes. Stop and target exits close within \alExitGrace{} minutes of
the first pooled print at or beyond the level, or within \alExitNear{} per
cent of it before any crossing; missed exits stay open longer after a
crossing. Other: liquidations and positions open at the close without a
crossing. Plan$-$actual is the gross P\&L change from closing at the first
crossing print, and $B-X$ the timing and execution contribution, both
percentage points of the group's initial capital (models four accounts,
arms eight, all 32). Descriptive; one run per model--arm cell.}
\label{tab:exitplan}
\setlength{\tabcolsep}{3.5pt}
\begin{tabular}{lrrrrrrrrr}
\toprule
 & Planned & \multicolumn{2}{c}{Exit at} & Discre- & \multicolumn{2}{c}{Missed} & & Plan$-$ & \\
 & /all & stop & target & tionary & stop & target & Other & actual & $B-X$ \\
\midrule
""" + '\n'.join(rows[:8]) + '\n\\midrule\n' + '\n'.join(rows[8:]) + '\n\\midrule\n' + total + r"""
\bottomrule
\end{tabular}
\end{table}
"""
    (paper / 'exitplan_table.tex').write_text(tex)


if __name__ == '__main__':
    main()
