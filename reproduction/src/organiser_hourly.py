"""Hourly organiser snapshots against the on-chain reconstruction, Season 1.5.

Run: python src/organiser_hourly.py [--archive PATH] [--output PATH]

Input: data/raw/nof1_hourly/account_totals_hourly.zip, a CSV export of the
paginated organiser endpoint
    https://www.alphaarena.ai/api/account-totals?lastHourlyMarker=N
(accounts.csv, positions.csv, coverage.csv). Its account rows equal those of
data/raw/nof1/account-totals.json; the positions, margins and liquidation
prices for every hour are new (the unpaginated payload carries positions for
the last 32 snapshots only). The organiser's files are not redistributed.
Existing derived inputs and data/external/funding are reused; no network.

Four calculations, each a check on an existing result rather than a new
headline:

1. Reconciliation at every snapshot. Positions at the snapshot timestamp are
   compared with cumulative on-chain fills. Equity is recomputed at the exact
   timestamp from cash flows, C - sum(signed size * price) + q * P - fees +
   funding, with hourly reconstructed funding inside the official window and
   recorded daily funding afterwards, once at pooled trade prices and once at
   the organiser's current_price. Organiser prices are a different source,
   not validated oracle prices.
2. Freeze and close. The snapshot nearest each formation time and the close
   is compared position by position; fills between snapshot and boundary are
   counted. Terminal books are revalued at the organiser's prices near the
   close.
3. Liquidations. Own-account liquidation fills are read from the raw
   Hyperliquid userFillsByTime pages. The organiser's liquidation_price is
   tested against the isolated-margin formula and against the mark price
   recorded in each actual liquidation.
4. Formation-hour sweep. The hourly-funded frozen-book comparison of
   src/funding_hourly_sensitivity.py is recomputed for every formation hour
   (it reproduces the 12-, 24- and 48-hour rows exactly). Two margin
   conventions bracket feasibility, neither of which is established:
     * account-wide: equity against the sum of asset maintenance margins,
       as if collateral could be moved between positions freely;
     * passive isolated: each frozen position keeps the isolated margin it
       had at formation, with no transfers. Its liquidation price is the
       organiser's value from the nearest snapshot with the same quantity and
       no intervening fill in that instrument, shifted for frozen funding.
       This uses the actual position's threshold only because at formation
       the frozen and actual positions are the same object; it ceases to
       describe the actual account after formation. Pooled trade prints are
       the trigger, which misses some mark-price crossings (see the
       validation), and liquidation at the threshold either returns (A) or
       forfeits (B) the remaining maintenance margin.
   Neither convention replays the exchange: mark prices, partial
   liquidation, fees and backstop rules are not reconstructed. Both the
   close and the fixed 24-, 72- and 168-hour horizons are evaluated under
   passive isolated margin; a position liquidated before the horizon
   contributes its liquidation result there.

Writes data/derived/organiser_hourly.json and organiser_hourly_*.csv, and
local per-snapshot detail under data/derived/organiser_hourly/.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import funding_hourly_sensitivity as fh
import wallets

CAPITAL = fh.CAPITAL
EPS = 1e-6
NEAR_MIN = 15          # organiser snapshot "near" a boundary, minutes
PRIMARY = (12, 24, 48)
HORIZONS = (24, 72, 168)   # fixed comparison horizons after formation, hours
# Liquidation stress. Actual liquidation fills in the archive executed a
# median 0.06% and at most 1.3% beyond the organiser threshold, and marks at
# liquidation lay within 0.06% of it; recorded fees reach 9 bp of notional.
HARSH = {'buffer': -0.01, 'slip': 0.013, 'charge': 0.001, 'worst_unscreened': True}
HARSH_ZERO = {'buffer': 0.0, 'slip': 0.0, 'charge': 0.0, 'worst_unscreened': False}
STRESSES = [
    ('none', {}),
    ('unscreened at worst mark', {'worst_unscreened': True}),
    ('trigger 1% earlier', {'buffer': 0.01}),
    ('trigger 1% later', {'buffer': -0.01}),
    ('slippage 0.25%', {'slip': 0.0025}),
    ('slippage 1.3%', {'slip': 0.013}),
    ('charge 10 bp', {'charge': 0.001}),
    ('joint, earlier trigger', {**HARSH, 'buffer': 0.01}),
    ('joint, later trigger', HARSH),
]


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=HERE.parent)
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    args.root = args.root.resolve()
    args.archive = args.archive or args.root / 'data/raw/nof1_hourly/account_totals_hourly.zip'
    args.output = args.output or args.root / 'data/derived'
    return args


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_archive(path, root):
    with zipfile.ZipFile(path) as z:
        read = {name: pd.read_csv(io.BytesIO(z.read(name)))
                for name in ('accounts.csv', 'positions.csv', 'coverage.csv')}
    w = pd.read_csv(root / 'wallets.csv')
    w = w[w.season.eq('S15')]
    tags = dict(zip(w.run_id.astype(int),
                    'S15__c' + w.competition_id.astype(str) + '__' + w.model))
    out = []
    for name in ('accounts.csv', 'positions.csv'):
        d = read[name]
        d['tag'] = d['id'].str.split('_').str[0].astype(int).map(tags)
        if d['tag'].isna().any():
            raise ValueError(f'Unmapped organiser run in {name}')
        d['t'] = (d['timestamp'] * 1000).round().astype('int64')
        out.append(d)
    return out[0], out[1], read['coverage.csv']


class Market:
    """On-chain fills, pooled prints and hourly funding for Season 1.5."""

    def __init__(self, root):
        der = root / 'data/derived'
        frames = {n: pd.read_parquet(der / f'{n}.parquet')
                  for n in ('fills', 'panel', 'equity', 'accounts', 'funding')}
        s = {n: d[d.season.eq('S15')].copy() for n, d in frames.items()}
        self.fills, self.panel, self.equity = s['fills'], s['panel'], s['equity']
        self.accounts, self.funding = s['accounts'].set_index('tag'), s['funding']
        self.lo, self.hi = wallets.S15_START_MS, wallets.S15_OFFICIAL_END_MS
        self.hours = np.arange(self.lo, self.hi + 1, fh.HOUR)
        rates, self.rate_paths = fh.load_rates(root / 'data/external/funding')
        self.positions, self.prices = fh.data_groups(self.fills)
        self.coins = sorted(self.prices)
        self.unit = {}
        for coin in self.coins:
            r, p = fh.hourly_market(coin, self.hours, rates, self.prices)
            self.unit[coin] = -r * p
        self.tags = sorted(self.accounts.index)
        self.pay = fh.actual_payments(self.tags, self.coins, self.hours,
                                      self.positions, self.unit)
        self.inputs = [der / f'{n}.parquet' for n in frames]

    def price(self, coin, t):
        times, values = self.prices[coin]
        return fh.at_times(times, values, t, side='right', initial=np.nan)

    def quantity(self, tag, coin, t):
        if (tag, coin) not in self.positions:
            return np.zeros(len(t))
        times, q = self.positions[(tag, coin)]
        q = fh.at_times(times, q, t, side='right', initial=0.0)
        q[np.abs(q) < fh.POSITION_EPS] = 0.0
        return q

    def funding_to(self, tag, t):
        """Hourly funding through t inside the window; recorded rows after it."""
        inside = fh.at_times(self.hours, self.pay[tag].cumsum(),
                             np.minimum(t, self.hi), side='right', initial=0.0)
        later = self.funding[self.funding.tag.eq(tag)
                             & self.funding.time.gt(self.hi)].sort_values('time')
        if later.empty:
            return inside
        return inside + fh.at_times(later.time.to_numpy(), later.usdc.cumsum().to_numpy(),
                                    t, side='right', initial=0.0)

    def cash_equity(self, tag, t, price):
        """Equity at exact timestamps from cash flows; price(coin, t) marks."""
        f = self.fills[self.fills.tag.eq(tag)].sort_values(['time', 'tid'], kind='mergesort')
        total = np.full(len(t), CAPITAL)
        for coin, g in f.groupby('coin'):
            times = g.time.to_numpy()
            cash = fh.at_times(times, (-g.signed_sz * g.px).cumsum().to_numpy(), t,
                               side='right', initial=0.0)
            q = self.quantity(tag, coin, t)
            total += cash + np.where(q != 0, q * price(coin, t), 0.0)
        fees = fh.at_times(f.time.to_numpy(), f.fee.cumsum().to_numpy(), t,
                           side='right', initial=0.0)
        return total - fees + self.funding_to(tag, t)


def quantiles(values, qs=(.5, .9, .99, 1.0)):
    v = np.abs(np.asarray(values, float))
    return {str(q): float(np.quantile(v, q)) for q in qs}


def reconcile(m, acc, pos):
    """Positions and equity at every organiser snapshot."""
    cells = []
    for tag, g in acc.groupby('tag'):
        t = g.t.to_numpy()
        for coin in m.coins:
            p = m.price(coin, t)
            age = (t - fh.at_times(m.prices[coin][0], m.prices[coin][0], t,
                                   side='right', initial=np.nan)) / 60_000
            cells.append(pd.DataFrame({'tag': tag, 't': t, 'coin': coin,
                                       'q_chain': m.quantity(tag, coin, t),
                                       'px_pool': p, 'px_pool_age_min': age}))
    cells = pd.concat(cells, ignore_index=True)
    org = pos[['tag', 't', 'symbol', 'quantity', 'current_price', 'margin',
               'liquidation_price', 'leverage']].rename(
        columns={'symbol': 'coin', 'quantity': 'q_org', 'current_price': 'px_org'})
    cells = cells.merge(org, on=['tag', 't', 'coin'], how='left')
    if cells.q_org.notna().sum() != len(pos):
        raise ValueError('Organiser positions outside the on-chain instrument set')
    cells['q_org'] = cells.q_org.fillna(0.0)
    cells['q_gap'] = cells.q_chain - cells.q_org
    held = cells[(cells.q_org != 0) | (cells.q_chain != 0)]
    px = cells.set_index(['tag', 't', 'coin']).px_org.dropna()

    rows = []
    for tag, g in acc.groupby('tag'):
        t = g.t.to_numpy()
        lookup = px.loc[tag] if tag in px.index.get_level_values(0) else pd.Series(dtype=float)

        def organiser(coin, times, lookup=lookup):
            base = m.price(coin, times)
            return np.array([lookup.get((x, coin), b) for x, b in zip(times, base)])

        rows.append(pd.DataFrame({
            'tag': tag, 'marker': g.since_inception_hourly_marker.to_numpy(), 't': t,
            'organiser_equity': g.dollar_equity.to_numpy(),
            'chain_equity_pooled': m.cash_equity(tag, t, m.price),
            'chain_equity_organiser_prices': m.cash_equity(tag, t, organiser)}))
    eq = pd.concat(rows, ignore_index=True)
    eq['in_season'] = eq.t.le(m.hi)
    for col in ('pooled', 'organiser_prices'):
        eq[f'gap_{col}'] = eq[f'chain_equity_{col}'] - eq.organiser_equity
        eq[f'gap_{col}_pct'] = 100 * eq[f'gap_{col}'] / eq.organiser_equity

    priced = cells[cells.q_org.ne(0) & cells.px_org.notna()]
    rel = 100 * (priced.px_pool / priced.px_org - 1)
    summary = {
        'snapshots': int(len(acc)), 'accounts': int(acc.tag.nunique()),
        'position_rows': int(len(pos)),
        'position_cells_held': int(len(held)),
        'position_cells_exact': int((held.q_gap.abs() < EPS).sum()),
        'position_mismatches': held[held.q_gap.abs() >= EPS][
            ['tag', 't', 'coin', 'q_chain', 'q_org']].to_dict('records'),
        'pooled_vs_organiser_price_abs_pct': quantiles(rel),
        'equity': {},
    }
    for label, part in (('in_season', eq[eq.in_season]), ('post_season', eq[~eq.in_season])):
        item = {'snapshots': int(len(part))}
        for col in ('pooled', 'organiser_prices'):
            pct = part[f'gap_{col}_pct']
            item[col] = {'abs_pct': quantiles(pct), 'abs_usd': quantiles(part[f'gap_{col}']),
                         'share_within_0.1pct': float((pct.abs() < .1).mean()),
                         'share_within_1pct': float((pct.abs() < 1).mean())}
        worst = part.loc[part.gap_organiser_prices_pct.abs().idxmax()]
        item['largest_organiser_price_gap'] = {
            'tag': worst.tag, 'marker': int(worst.marker),
            'utc': str(pd.to_datetime(worst.t, unit='ms')),
            'pct': float(worst.gap_organiser_prices_pct)}
        summary['equity'][label] = item
    later = eq[eq.in_season & eq.marker.gt(0)]
    summary['equity']['in_season_after_marker0_organiser_prices_abs_pct'] = quantiles(
        later.gap_organiser_prices_pct)
    return cells, eq, summary


def boundary(m, acc, cells, T, label):
    """Organiser snapshot nearest T, its positions and prices."""
    s = acc[['tag', 't', 'since_inception_hourly_marker']].copy()
    s['minutes_from_boundary'] = (s.t - T) / 60_000
    near = s.loc[s.groupby('tag').minutes_from_boundary.apply(lambda v: v.abs().idxmin())]
    between = []
    for r in near.itertuples():
        a, b = sorted((r.t, T))
        f = m.fills[m.fills.tag.eq(r.tag) & m.fills.time.gt(a) & m.fills.time.le(b)]
        between.append(len(f))
    near['fills_between'] = between
    c = cells.merge(near[['tag', 't']], on=['tag', 't'])
    held = c[(c.q_org != 0) | (c.q_chain != 0)]
    within = s[s.minutes_from_boundary.abs() <= NEAR_MIN]
    prices = {}
    window = cells[(cells.t - T).abs().le(NEAR_MIN * 60_000) & cells.px_org.notna()]
    for coin, g in window.groupby('coin'):
        pool = float(m.price(coin, np.array([T]))[0])
        prices[coin] = {'pooled_at_boundary': pool, 'organiser_median': float(g.px_org.median()),
                        'organiser_min': float(g.px_org.min()), 'organiser_max': float(g.px_org.max()),
                        'organiser_n': int(len(g)),
                        'relative_pct': float(100 * (g.px_org.median() / pool - 1))}
    return {
        'label': label, 'utc': str(pd.to_datetime(T, unit='ms')),
        'accounts_with_snapshot_within_15min': int(within.tag.nunique()),
        'accounts_with_snapshot_within_60min': int(s[s.minutes_from_boundary.abs() <= 60].tag.nunique()),
        'nearest_markers': {str(k): int(v) for k, v in
                            near.since_inception_hourly_marker.value_counts().sort_index().items()},
        'nearest_minutes_abs_max': float(near.minutes_from_boundary.abs().max()),
        'nearest_minutes_abs_median': float(near.minutes_from_boundary.abs().median()),
        'accounts_with_fills_between_snapshot_and_boundary': int((near.fills_between > 0).sum()),
        'nearest_position_cells': int(len(held)),
        'nearest_position_cells_exact': int((held.q_gap.abs() < EPS).sum()),
        'prices_within_15min': prices,
    }


def liquidation_events(root):
    w = pd.read_csv(root / 'wallets.csv')
    w = w[w.season.eq('S15')]
    own = dict(zip('S15__c' + w.competition_id.astype(str) + '__' + w.model,
                   w.address.str.lower()))
    rows = []
    for path in sorted(glob.glob(str(root / 'data/raw/hl/userFillsByTime/S15__*.json'))):
        tag = Path(path).name.split('.p0')[0]
        for x in json.loads(Path(path).read_text()):
            liq = x.get('liquidation')
            if liq and liq['liquidatedUser'].lower() == own[tag]:
                rows.append({'tag': tag, 'time': int(x['time']), 'coin': x['coin'],
                             'tid': x['tid'], 'px': float(x['px']), 'sz': float(x['sz']),
                             'closed_pnl': float(x['closedPnl']),
                             'mark_px': float(liq['markPx']), 'method': liq['method']})
    fills = pd.DataFrame(rows).drop_duplicates('tid')
    events = (fills.groupby(['tag', 'coin', 'time'])
              .agg(mark_px=('mark_px', 'first'), fills=('tid', 'size'),
                   size=('sz', 'sum'), closed_pnl=('closed_pnl', 'sum'),
                   method=('method', 'first')).reset_index())
    return fills, events


def isolated_fit(pos):
    """Maintenance fraction implied by the isolated formula for each row.

    Hyperliquid: L = P - s*(M - l*|q|*P)/|q|/(1 - l*s), with s the side and
    M the isolated margin including unrealised profit. Solved for l.
    """
    p = pos[(pos.quantity != 0) & pos.current_price.notna() & (pos.liquidation_price > 0)].copy()
    q, s = p.quantity.abs(), np.sign(p.quantity)
    P, M, L = p.current_price, p.margin, p.liquidation_price
    p['l_implied'] = (s * M - (P - L) * q) / (s * q * L)
    rates = p.groupby('symbol').l_implied.median()
    pred = P - s * (M - p.symbol.map(rates) * q * P) / q / (1 - p.symbol.map(rates) * s)
    p['fit_abs_pct'] = (100 * (pred / L - 1)).abs()
    by = {c: {'rows': int(len(g)), 'median_l': float(g.l_implied.median()),
              'abs_pct_error': quantiles(g.fit_abs_pct)}
          for c, g in p.groupby('symbol')}
    return rates.to_dict(), {'rows': int(len(p)), 'by_symbol': by,
                             'abs_pct_error_all': quantiles(p.fit_abs_pct)}


def validate_trigger(m, cells, events):
    """Organiser threshold before each actual liquidation, against marks and prints."""
    o = cells[cells.q_org.ne(0)].sort_values(['tag', 'coin', 't'])
    o = o.assign(q_prev=o.groupby(['tag', 'coin']).q_org.shift(),
                 L_prev=o.groupby(['tag', 'coin']).liquidation_price.shift())
    same = o[o.q_prev.eq(o.q_org)]
    drift = 100 * (same.liquidation_price / same.L_prev - 1)
    rows = []
    for e in events.itertuples():
        s = o[o.tag.eq(e.tag) & o.coin.eq(e.coin) & o.t.lt(e.time)]
        if s.empty:
            continue
        s = s.iloc[-1]
        side = np.sign(s.q_org)
        times, values = m.prices[e.coin]
        path = values[(times > s.t) & (times <= e.time)]
        crossed = bool((path <= s.liquidation_price).any() if side > 0
                       else (path >= s.liquidation_price).any())
        unchanged = int((m.fills.tag.eq(e.tag) & m.fills.coin.eq(e.coin)
                         & m.fills.time.gt(s.t) & m.fills.time.lt(e.time)).sum()) == 0
        rows.append({'tag': e.tag, 'coin': e.coin, 'time': e.time,
                     'in_season': bool(e.time <= m.hi), 'side': int(side),
                     'organiser_threshold': float(s.liquidation_price),
                     'mark_px': e.mark_px,
                     'mark_minus_threshold_pct': float(100 * (e.mark_px / s.liquidation_price - 1)),
                     'hours_since_snapshot': float((e.time - s.t) / fh.HOUR),
                     'position_unchanged_since_snapshot': unchanged,
                     'pooled_prints_crossed': crossed})
    v = pd.DataFrame(rows)
    u = v[v.position_unchanged_since_snapshot]
    # A liquidation is itself a fill, so a print crossing between consecutive
    # same-quantity snapshots with no fill in that instrument is a false alarm.
    intervals = alarms = 0
    for (tag, coin), g in o.groupby(['tag', 'coin']):
        t, q, L = g.t.to_numpy(), g.q_org.to_numpy(), g.liquidation_price.to_numpy()
        fills = np.sort(m.fills[m.fills.tag.eq(tag) & m.fills.coin.eq(coin)].time.to_numpy())
        times, values = m.prices[coin]
        for i in range(len(g) - 1):
            if q[i] != q[i + 1] or (np.searchsorted(fills, t[i + 1], side='right')
                                    != np.searchsorted(fills, t[i], side='right')):
                continue
            intervals += 1
            path = values[(times > t[i]) & (times <= t[i + 1])]
            alarms += bool((path <= L[i]).any() if q[i] > 0 else (path >= L[i]).any())
    return v, {
        'events': int(len(events)), 'accounts': int(events.tag.nunique()),
        'events_in_season': int((events.time <= m.hi).sum()),
        'accounts_in_season': int(events[events.time <= m.hi].tag.nunique()),
        'events_with_unchanged_position': int(len(u)),
        'mark_minus_threshold_abs_pct_max_unchanged': float(u.mark_minus_threshold_pct.abs().max()),
        'pooled_prints_crossed_unchanged': int(u.pooled_prints_crossed.sum()),
        'same_quantity_consecutive_pairs': int(len(same)),
        'same_quantity_threshold_drift_abs_pct': quantiles(drift, (.5, .9, .99, 1.0)),
        'same_quantity_share_drift_over_0.5pct': float((drift.abs() > .5).mean()),
        'fill_free_same_quantity_intervals': int(intervals),
        'print_crossings_without_fill': int(alarms),
    }


class Sweep:
    """Hourly-funded frozen-book comparison for any formation hour."""

    def __init__(self, m, cells, rates):
        self.m, self.rates = m, rates
        p = m.panel[m.panel.t.between(m.lo, m.hi)]
        self.grid = np.sort(p.t.unique())
        if self.grid[-1] != m.hi:
            raise ValueError('Close is absent from the five-minute grid')
        self.q, self.px = {}, {}
        for (tag, coin), g in p.groupby(['tag', 'coin']):
            g = g.sort_values('t')
            if not np.array_equal(g.t.to_numpy(), self.grid):
                raise ValueError(f'Irregular grid: {tag}/{coin}')
            self.q[(tag, coin)] = g.signed_size.to_numpy(float)
            self.px[(tag, coin)] = g.px.to_numpy(float)
        self.eq, self.booked = {}, {}
        for tag, e in m.equity.groupby('tag'):
            e = e.sort_values('t').set_index('t').reindex(self.grid)
            self.eq[tag] = e.equity.to_numpy(float)
            self.booked[tag] = e.funding.to_numpy(float)
        self.actual = {}
        for tag in m.tags:
            end = m.equity[m.equity.tag.eq(tag) & m.equity.t.le(m.hi)].sort_values('t').iloc[-1]
            self.actual[tag] = float(m.accounts.loc[tag, 'equity_change'] - end.funding
                                     + m.pay[tag].sum())
        # realised equity on the grid with hourly funding, the actual-book
        # counterpart of the frozen path; it ends at the realised result
        self.actual_path = {
            tag: self.eq[tag] - self.booked[tag]
            + fh.at_times(m.hours, m.pay[tag].cumsum(), self.grid, side='right', initial=0.0)
            for tag in m.tags}
        worst = max(abs(self.actual_path[tag][-1] - CAPITAL - self.actual[tag]) for tag in m.tags)
        if worst > 1e-6:
            raise ValueError(f'Realised path does not end at the realised result: {worst}')
        org = cells[cells.q_org.ne(0)]
        self.org = {k: g.sort_values('t')[['t', 'q_org', 'liquidation_price']].to_numpy()
                    for k, g in org.groupby(['tag', 'coin'])}
        self.fill_times = {k: np.sort(g.time.to_numpy()) for k, g in m.fills.groupby(['tag', 'coin'])}

    def threshold(self, tag, coin, q0, t0):
        """Organiser liquidation price for the same position nearest formation."""
        if (tag, coin) not in self.org:
            return None
        snaps = self.org[(tag, coin)]
        same = snaps[np.abs(snaps[:, 1] - q0) < EPS]
        if not len(same):
            return None
        fills = self.fill_times.get((tag, coin), np.array([]))
        a, b = np.minimum(same[:, 0], t0), np.maximum(same[:, 0], t0)
        clean = (np.searchsorted(fills, b, side='right')
                 == np.searchsorted(fills, a, side='right'))
        if not clean.any():
            return None
        same = same[clean]
        best = same[np.argmin(np.abs(same[:, 0] - t0))]
        return best[0], best[2]

    def run(self, hour, organiser_close=None, stress=None):
        """stress: trigger buffer and slippage beyond it (fractions of price),
        a charge on the liquidated notional, and unscreened positions closed
        at their worst grid mark; None is the unstressed specification."""
        m, grid = self.m, self.grid
        st = {'buffer': 0.0, 'slip': 0.0, 'charge': 0.0, 'worst_unscreened': False,
              **(stress or {})}
        t0 = m.lo + hour * fh.HOUR
        i0 = int(np.searchsorted(grid, t0))
        if grid[i0] != t0:
            raise ValueError(f'Formation hour absent from grid: {hour}')
        g = grid[i0:]
        after = m.hours > t0
        rows, z, z_org = [], np.zeros(len(m.coins)), 0.0
        for tag in m.tags:
            inherited = float(m.pay[tag][m.hours <= t0].sum())
            start = self.eq[tag][i0] - self.booked[tag][i0] + inherited
            mtm, gross, maint = np.zeros(len(g)), np.zeros(len(g)), np.zeros(len(g))
            fund = np.zeros(len(m.hours))
            contrib = {'A': 0.0, 'B': 0.0}
            # isolated-margin value at each fixed horizon: a position
            # liquidated by then contributes its liquidation result
            ends = {}
            for w in HORIZONS:
                j = int(np.searchsorted(g, t0 + w * fh.HOUR))
                if j < len(g) and g[j] == t0 + w * fh.HOUR:
                    ends[w] = j
            contrib_h = {w: {'A': 0.0, 'B': 0.0} for w in ends}
            n_liq, n_unknown, n_open = 0, 0, 0
            for k, coin in enumerate(m.coins):
                q0 = self.q[(tag, coin)][i0]
                qT = self.q[(tag, coin)][-1]
                p = self.px[(tag, coin)][i0:]
                z[k] += (q0 - qT) * p[-1] if np.isfinite(p[-1]) else 0.0
                if organiser_close is not None and coin in organiser_close:
                    z_org += (q0 - qT) * (organiser_close[coin] - p[-1])
                if q0 == 0:
                    continue
                n_open += 1
                fh.finite(p, (tag, coin, 'frozen path'))
                l = self.rates[coin]
                mtm += q0 * (p - p[0])
                gross += np.abs(q0 * p)
                maint += l * np.abs(q0 * p)
                pay = np.where(after, q0 * m.unit[coin], 0.0)
                fh.finite(pay[after], (tag, coin, 'frozen funding'))
                fund += pay
                full = q0 * (p[-1] - p[0]) + pay.sum()
                held = {w: q0 * (p[j] - p[0]) + pay[m.hours <= t0 + w * fh.HOUR].sum()
                        for w, j in ends.items()}
                found = self.threshold(tag, coin, q0, t0)
                if found is None and st['worst_unscreened']:
                    n_unknown += 1
                    run_pnl = q0 * (p - p[0]) + fh.at_times(
                        m.hours, pay.cumsum(), g, side='right', initial=0.0)
                    worst = min(float(run_pnl.min()), full)
                    contrib['A'] += worst
                    contrib['B'] += worst
                    for w, j in ends.items():
                        low = min(float(run_pnl[:j + 1].min()), held[w])
                        contrib_h[w]['A'] += low
                        contrib_h[w]['B'] += low
                    continue
                if found is None:
                    n_unknown += 1
                    contrib['A'] += full
                    contrib['B'] += full
                    for w in ends:
                        contrib_h[w]['A'] += held[w]
                        contrib_h[w]['B'] += held[w]
                    continue
                L0 = found[1]
                times, values = m.prices[coin]
                sel = (times > t0) & (times <= m.hi)
                tp, vp = times[sel], values[sel]
                paid = -np.cumsum(pay)            # funding paid from isolated margin
                Lt = L0 + fh.at_times(m.hours, paid, tp, side='right', initial=0.0) / (q0 - l * abs(q0))
                side = np.sign(q0)
                Lt = Lt * (1 + side * st['buffer'])   # earlier trigger
                hit = np.nonzero(vp <= Lt if q0 > 0 else vp >= Lt)[0]
                if not len(hit):
                    contrib['A'] += full
                    contrib['B'] += full
                    for w in ends:
                        contrib_h[w]['A'] += held[w]
                        contrib_h[w]['B'] += held[w]
                    continue
                n_liq += 1
                tau, L = tp[hit[0]], Lt[hit[0]]
                X = L * (1 - side * st['slip'])       # execution beyond the trigger
                received = pay[m.hours <= tau].sum()
                a = q0 * (X - p[0]) + received - st['charge'] * abs(q0) * X
                contrib['A'] += a
                contrib['B'] += a - l * abs(q0) * L
                for w in ends:
                    gone = tau <= t0 + w * fh.HOUR
                    contrib_h[w]['A'] += a if gone else held[w]
                    contrib_h[w]['B'] += a - l * abs(q0) * L if gone else held[w]
            path = start + mtm + fh.at_times(m.hours, fund.cumsum(), g, side='right', initial=0.0)
            fh.finite(path, (tag, 'funded path'))
            ratio = np.divide(path, gross, out=np.full_like(gross, np.inf), where=gross > 0)
            fixed = {}
            for w in HORIZONS:
                j = int(np.searchsorted(g, t0 + w * fh.HOUR))
                if j < len(g) and g[j] == t0 + w * fh.HOUR:
                    fixed[f'advantage_{w}h'] = float(path[j] - self.actual_path[tag][i0 + j])
                else:
                    fixed[f'advantage_{w}h'] = np.nan
                for case in ('A', 'B'):
                    fixed[f'isolated_{case}_advantage_{w}h'] = (
                        float(start + contrib_h[w][case] - self.actual_path[tag][i0 + ends[w]])
                        if w in ends else np.nan)
                    if stress is None and w in ends and n_liq == 0 and abs(
                            fixed[f'isolated_{case}_advantage_{w}h'] - fixed[f'advantage_{w}h']) > 1e-6:
                        raise ValueError(f'Isolated horizon value without liquidation differs: {tag}')
            rows.append({**fixed,
                'formation_hour': hour, 'tag': tag,
                'frozen_net': float(path[-1] - CAPITAL),
                'actual_net': self.actual[tag],
                'positions_open': n_open,
                'min_equity_to_gross': float(ratio.min()),
                'accountwide_maintenance_breach': bool((path < maint).any()),
                'isolated_liquidated_positions': n_liq,
                'isolated_unscreened_positions': n_unknown,
                'isolated_net_A': float(start + contrib['A'] - CAPITAL),
                'isolated_net_B': float(start + contrib['B'] - CAPITAL),
            })
        d = pd.DataFrame(rows)
        book = CAPITAL * len(d)
        gap = float((d.frozen_net - d.actual_net).sum())
        item = {
            'formation_hour': hour, 'accounts': len(d),
            'frozen_return_pct': 100 * d.frozen_net.sum() / book,
            'actual_return_pct': 100 * d.actual_net.sum() / book,
            'advantage_pp': 100 * gap / book,
            'accounts_ahead': int((d.frozen_net > d.actual_net).sum()),
            'endpoint_common_break_even_pct': 100 * gap / float(np.abs(z).sum())
            if np.abs(z).sum() > 0 else None,
            'advantage_pp_organiser_close_prices': 100 * (gap + z_org) / book
            if organiser_close is not None else None,
            'accountwide_maintenance_breaches': int(d.accountwide_maintenance_breach.sum()),
            'isolated_accounts_liquidated': int((d.isolated_liquidated_positions > 0).sum()),
            'isolated_positions_liquidated': int(d.isolated_liquidated_positions.sum()),
            'isolated_positions_unscreened': int(d.isolated_unscreened_positions.sum()),
            'remaining_days': (m.hi - t0) / (24 * fh.HOUR),
            'advantage_pp_per_day': 100 * gap / book / ((m.hi - t0) / (24 * fh.HOUR)),
            'isolated_accounts_unscreened': int((d.isolated_unscreened_positions > 0).sum()),
        }
        for w in HORIZONS:
            col = d[f'advantage_{w}h']
            item[f'advantage_pp_{w}h'] = 100 * float(col.sum()) / book if col.notna().all() else None
            item[f'accounts_ahead_{w}h'] = int((col > 0).sum()) if col.notna().all() else None
            for case in ('A', 'B'):
                col = d[f'isolated_{case}_advantage_{w}h']
                item[f'isolated_{case}_advantage_pp_{w}h'] = (
                    100 * float(col.sum()) / book if col.notna().all() else None)
        for case in ('A', 'B'):
            item[f'isolated_{case}_advantage_pp'] = 100 * float(
                (d[f'isolated_net_{case}'] - d.actual_net).sum()) / book
            item[f'isolated_{case}_accounts_ahead'] = int(
                (d[f'isolated_net_{case}'] > d.actual_net).sum())
        return d, item


def describe_sweep(s):
    def block(part):
        return {
            'hours': int(len(part)),
            'advantage_pp_min': float(part.advantage_pp.min()),
            'advantage_pp_median': float(part.advantage_pp.median()),
            'advantage_pp_max': float(part.advantage_pp.max()),
            'hours_positive': int((part.advantage_pp > 0).sum()),
            'accounts_ahead_min': int(part.accounts_ahead.min()),
            'accounts_ahead_median': float(part.accounts_ahead.median()),
            'accounts_ahead_max': int(part.accounts_ahead.max()),
            'hour_at_min': int(part.loc[part.advantage_pp.idxmin(), 'formation_hour']),
            'isolated_A_hours_positive': int((part.isolated_A_advantage_pp > 0).sum()),
            'isolated_B_hours_positive': int((part.isolated_B_advantage_pp > 0).sum()),
            'isolated_B_advantage_pp_min': float(part.isolated_B_advantage_pp.min()),
            'isolated_B_advantage_pp_median': float(part.isolated_B_advantage_pp.median()),
            'isolated_accounts_liquidated_median': float(part.isolated_accounts_liquidated.median()),
            'endpoint_break_even_pct_min': float(part.endpoint_common_break_even_pct.min()),
            'endpoint_break_even_pct_median': float(part.endpoint_common_break_even_pct.median()),
        }
    out = {'all': block(s), 'first_week': block(s[s.formation_hour <= 168]),
           'first_48h': block(s[s.formation_hour <= 48])}
    at24 = s.set_index('formation_hour').loc[24]
    out['all']['percentile_of_24h'] = float(100 * (s.advantage_pp < at24.advantage_pp).mean())
    per_day = s.advantage_pp_per_day
    out['per_day'] = {'median': float(per_day.median()), 'min': float(per_day.min()),
                      'max': float(per_day.max()), 'at_24h': float(at24.advantage_pp_per_day),
                      'percentile_of_24h': float(100 * (per_day < at24.advantage_pp_per_day).mean())}
    for w in HORIZONS:
        col = s[f'advantage_pp_{w}h'].dropna()
        out[f'horizon_{w}h'] = {
            'formations': int(len(col)), 'median': float(col.median()),
            'min': float(col.min()), 'max': float(col.max()),
            'positive': int((col > 0).sum()),
            'at_24h': float(at24[f'advantage_pp_{w}h']),
            'percentile_of_24h': float(100 * (col < at24[f'advantage_pp_{w}h']).mean()),
            'accounts_ahead_median': float(s[f'accounts_ahead_{w}h'].dropna().median())}
        for case in ('A', 'B'):
            iso = s[f'isolated_{case}_advantage_pp_{w}h'].dropna()
            out[f'horizon_{w}h'].update({
                f'isolated_{case}_median': float(iso.median()),
                f'isolated_{case}_positive': int((iso > 0).sum()),
                f'isolated_{case}_at_24h': float(at24[f'isolated_{case}_advantage_pp_{w}h'])})
    return out


def main():
    args = arguments()
    root, out = args.root, args.output
    acc, pos, coverage = load_archive(args.archive, root)
    m = Market(root)
    cells, eq, rec = reconcile(m, acc, pos)
    rates, fit = isolated_fit(pos)
    liq_fills, events = liquidation_events(root)
    validation, trig = validate_trigger(m, cells, events)
    # execution of actual liquidation fills beyond the organiser threshold
    f = liq_fills.assign(n=liq_fills.px * liq_fills.sz).groupby(['tag', 'coin', 'time'])[['n', 'sz']].sum()
    v = validation.join(f, on=['tag', 'coin', 'time'])
    beyond = -v.side * 100 * (v.n / v.sz / v.organiser_threshold - 1)
    trig['fill_beyond_threshold_pct'] = quantiles(beyond, (0.0, .5, 1.0))

    close_window = cells[(cells.t - m.hi).abs().le(NEAR_MIN * 60_000) & cells.px_org.notna()]
    organiser_close = close_window.groupby('coin').px_org.median().to_dict()
    boundaries = [boundary(m, acc, cells, m.lo + h * fh.HOUR, f'freeze_{h}h') for h in PRIMARY]
    boundaries.append(boundary(m, acc, cells, m.hi, 'close'))

    sweep = Sweep(m, cells, rates)
    last = int((m.hi - m.lo) // fh.HOUR) - 1
    accounts, items = [], []
    for hour in range(1, last + 1):
        d, item = sweep.run(hour, organiser_close)
        accounts.append(d)
        items.append(item)
    accounts = pd.concat(accounts, ignore_index=True)
    s = pd.DataFrame(items)

    stress_rows = []
    for name, st in STRESSES:
        _, it = sweep.run(24, stress=st)
        stress_rows.append({'scenario': name, **{**HARSH_ZERO, **st},
                            **{k: it[k] for k in ('actual_return_pct', 'isolated_positions_liquidated')},
                            **{f'{k}_{c}': it[f'isolated_{c}_{k}'] for k in
                               ('advantage_pp', 'accounts_ahead', 'advantage_pp_168h')
                               for c in ('A', 'B')}})
    stress = pd.DataFrame(stress_rows)
    base = s.set_index('formation_hour').loc[24]
    for c in ('A', 'B'):
        if abs(stress.loc[0, f'advantage_pp_{c}'] - base[f'isolated_{c}_advantage_pp']) > 1e-9:
            raise ValueError('Unstressed run differs from the sweep')
    stress_summary = {'at_24h': stress.to_dict('records')}
    stress_sweep = []
    for label, st in (('earlier', {**HARSH, 'buffer': 0.01}), ('later', HARSH)):
        harsh = pd.DataFrame([sweep.run(h, stress=st)[1] for h in range(1, last + 1)])
        stress_sweep.append(harsh.assign(trigger=label))
        week = {c: harsh[f'isolated_{c}_advantage_pp_168h'].dropna() for c in ('A', 'B')}
        stress_summary[f'joint_{label}_all_hours'] = {
            'formations_168h': int(len(week['A'])),
            **{f'{c}_168h_{k}': v for c, x in week.items()
               for k, v in (('median', float(x.median())), ('positive', int((x > 0).sum())),
                            ('min', float(x.min())))},
            **{f'{c}_close_{k}': v for c in ('A', 'B')
               for k, v in (('median', float(harsh[f'isolated_{c}_advantage_pp'].median())),
                            ('positive', int((harsh[f'isolated_{c}_advantage_pp'] > 0).sum())))}}

    existing = pd.read_csv(root / 'data/derived/funding_hourly_sensitivity_accounts.csv')
    check = accounts.merge(existing, left_on=['formation_hour', 'tag'],
                           right_on=['freeze_hours', 'tag'])
    if len(check) != 32 * len(PRIMARY):
        raise ValueError('Sweep does not cover the published formation hours')
    worst = float(max((check.frozen_net - check.proxy_hold_net).abs().max(),
                      (check.actual_net - check.proxy_actual_net).abs().max()))
    if worst > 1e-6:
        raise ValueError(f'Sweep does not reproduce the hourly-funded rows: {worst}')

    gaps = coverage[coverage.accounts_captured < 32]
    report = {
        'source': 'alphaarena.ai/api/account-totals?lastHourlyMarker=N, paginated CSV export',
        'archive_sha256': digest(args.archive),
        'coverage': {
            'markers': int(len(coverage)), 'snapshots': int(coverage.accounts_captured.sum()),
            'possible': int(32 * len(coverage)),
            'first_utc': str(pd.to_datetime(acc.t.min(), unit='ms')),
            'last_utc': str(pd.to_datetime(acc.t.max(), unit='ms')),
            'markers_below_32': int(len(gaps)),
            'marker_24_accounts': int(coverage.set_index('hourly_marker').accounts_captured.get(24)),
            'snapshot_offset_from_nominal_hour_minutes': quantiles(
                (acc.t - m.lo - acc.since_inception_hourly_marker * fh.HOUR) / 60_000,
                (0.0, .5, 1.0)),
        },
        'reconciliation': rec,
        'boundaries': boundaries,
        'organiser_close_prices': organiser_close,
        'isolated_margin_fit': fit, 'maintenance_rates': rates,
        'liquidation_trigger_validation': trig,
        'liquidation_events_by_account': events.groupby('tag').size().to_dict(),
        'sweep_reproduces_published_rows_max_abs_usd': worst,
        'sweep_summary': describe_sweep(s),
        'liquidation_stress': stress_summary,
        'sweep_primary': s[s.formation_hour.isin(PRIMARY)].to_dict('records'),
        'limitations': [
            'Organiser snapshots are not exchange records; prices are the organiser current_price, not validated oracle or mark prices.',
            'Snapshots fall about an hour after their nominal marker and are missing for some accounts in hours 2-28 and 118-143.',
            'Pooled trade prints are the liquidation trigger; they miss some mark-price crossings.',
            'Account-wide and passive-isolated conventions bracket, but do not establish, feasibility; mark prices, partial liquidation, fees and backstop rules are not replayed.',
            'The formation-hour sweep is descriptive; hours are not independent and share one market path.',
        ],
        'input_sha256': {str(p.relative_to(root)): digest(p)
                         for p in m.inputs + m.rate_paths
                         + [root / 'data/derived/funding_hourly_sensitivity_accounts.csv']},
        'source_sha256': {name: digest(HERE / name) for name in
                          ('organiser_hourly.py', 'funding_hourly_sensitivity.py', 'wallets.py')},
    }
    out.mkdir(parents=True, exist_ok=True)
    local = out / 'organiser_hourly'
    local.mkdir(exist_ok=True)
    cells.to_csv(local / 'position_cells.csv', index=False)
    eq.to_csv(local / 'equity_snapshots.csv', index=False)
    s.to_csv(out / 'organiser_hourly_sweep.csv', index=False)
    accounts.to_csv(out / 'organiser_hourly_sweep_accounts.csv', index=False)
    events.to_csv(out / 'organiser_hourly_liquidations.csv', index=False)
    stress.to_csv(out / 'organiser_hourly_liquidation_stress.csv', index=False)
    pd.concat(stress_sweep, ignore_index=True).to_csv(
        out / 'organiser_hourly_stress_sweep.csv', index=False)
    validation.to_csv(out / 'organiser_hourly_trigger_validation.csv', index=False)
    (out / 'organiser_hourly.json').write_text(
        json.dumps(report, indent=2, allow_nan=False, default=float) + '\n')
    print(json.dumps({k: report[k] for k in ('coverage', 'sweep_summary',
                                             'liquidation_trigger_validation')},
                     indent=2, default=float))


if __name__ == '__main__':
    main()
