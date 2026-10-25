"""Validate organiser prices and funding against exchange-derived oracle prices.

No free source publishes historical oracle or mark prices for the HIP-3 xyz
perps (Dune's hyperliquid.perp_oracle_prices needs a workspace entitlement;
the hyperliquid-archive asset_ctxs bucket is requester-pays; the public info
API serves only current asset contexts). The exchange does, however, record
the oracle price implicitly in every funding payment:

    usdc = -szi * oracle_px * funding_rate        (Hyperliquid funding docs)

so the hourly oracle price at each funding time is recoverable, exactly up to
rounding, from the accounts' own userFunding records:

    oracle_px = -usdc / (szi * funding_rate).

Steps
1. Re-fetch public fundingHistory for the seven xyz coins over 19 Nov - 15 Dec
   2025 (no credentials) into data/external/oracle/hl_info/, with provenance.
2. Funding validation: re-fetched rows vs data/external/funding/ (same
   endpoint, earlier retrieval), and the per-account userFunding rate vs the
   public per-coin fundingHistory rate at the same hour.
3. Funding-implied oracle per (coin, hour), its cross-account consistency,
   and comparisons with organiser current_price and pooled trade prints at
   snapshots near the hour.
4. Actual liquidations: exchange-reported markPx at the liquidation fill and
   organiser threshold against the implied oracle at adjacent funding hours.

Mark prices are not recovered: funding uses the oracle, liquidation uses the
mark, and on HIP-3 the mark is deployer-nominated.

Usage: python src/oracle_validation.py [--no-fetch]
"""
import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data' / 'external' / 'oracle' / 'hl_info'
OLD_FUNDING = ROOT / 'data' / 'external' / 'funding'
USER_FUNDING = OLD_FUNDING / 'user_funding_enriched.parquet'
CELLS = ROOT / 'data' / 'derived' / 'organiser_hourly' / 'position_cells.csv'
LIQ = ROOT / 'data' / 'derived' / 'organiser_hourly_trigger_validation.csv'
OUT = ROOT / 'data' / 'derived'

URL = 'https://api.hyperliquid.xyz/info'
COINS = ['xyz:NVDA', 'xyz:MSFT', 'xyz:TSLA', 'xyz:GOOGL', 'xyz:AMZN', 'xyz:PLTR', 'xyz:XYZ100']
START = 1763510400000   # 2025-11-19 00:00 UTC
END = 1765756800000     # 2025-12-15 00:00 UTC
HOUR = 3_600_000
MAX_REL_ROUNDING = 1e-4  # keep implied prices whose usdc rounding error < 1 bp
NEAR_MIN = 10            # snapshot within this many minutes of a funding hour


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def fetch_funding(coin):
    """Paginated fundingHistory; returns rows and per-page provenance."""
    rows, pages, start = [], [], START
    while start < END:
        payload = {'type': 'fundingHistory', 'coin': coin, 'startTime': start, 'endTime': END}
        t0 = datetime.now(timezone.utc).isoformat()
        r = requests.post(URL, json=payload, timeout=60)
        r.raise_for_status()
        page = r.json()
        name = f"fundingHistory_{coin.replace(':', '_')}_{start}.json"
        (RAW / name).write_bytes(r.content)
        pages.append({'url': URL, 'request_payload': payload, 'fetched_at_utc': t0,
                      'status': r.status_code, 'bytes': len(r.content), 'sha256': sha256(r.content),
                      'file': f'data/external/oracle/hl_info/{name}', 'row_count': len(page)})
        if not page:
            break
        rows += page
        nxt = max(p['time'] for p in page) + 1
        if nxt <= start or len(page) < 500:
            break
        start = nxt
        time.sleep(0.5)
    return rows, pages


def load_raw(coin):
    rows = []
    for f in sorted(RAW.glob(f"fundingHistory_{coin.replace(':', '_')}_*.json")):
        rows += json.loads(f.read_bytes())
    return rows


def public_funding(fetch):
    RAW.mkdir(parents=True, exist_ok=True)
    prov, frames = [], []
    for coin in COINS:
        if fetch:
            rows, pages = fetch_funding(coin)
            prov += pages
        else:
            rows = load_raw(coin)
        frames.append(pd.DataFrame(rows))
    if fetch:
        (RAW.parent / 'oracle_provenance.json').write_text(json.dumps({
            'scope': 'Hyperliquid public info API, no credentials; exact response bytes preserved',
            'sources': prov}, indent=1))
    f = pd.concat(frames, ignore_index=True).drop_duplicates(['coin', 'time'])
    f['fundingRate'] = f.fundingRate.astype(float)
    f['premium'] = f.premium.astype(float)
    f['hour'] = (f.time + HOUR // 2) // HOUR * HOUR
    return f.sort_values(['coin', 'time']).reset_index(drop=True)


def funding_checks(pub):
    """Re-fetch vs stored fundingHistory; userFunding rate vs public rate."""
    old = []
    for coin in COINS:
        p = OLD_FUNDING / f"fundingHistory_{coin.replace(':', '_')}.json"
        old.append(pd.DataFrame(json.loads(p.read_bytes())))
    old = pd.concat(old, ignore_index=True)
    m = old.merge(pub, on=['coin', 'time'], how='left', suffixes=('_old', ''))
    refetch = {
        'stored_rows': int(len(old)),
        'matched_rows': int(m.fundingRate.notna().sum()),
        'rate_exact_equal': int((m.fundingRate_old.astype(float) == m.fundingRate).sum()),
        'premium_exact_equal': int((m.premium_old.astype(float) == m.premium).sum()),
        'public_rows_19nov_15dec': int(len(pub)),
        'public_rows_by_coin': pub.groupby('coin').size().to_dict(),
    }
    uf = pd.read_parquet(USER_FUNDING)
    uf = uf[uf.coin.isin(COINS) & uf.time.between(START, END)].copy()
    # userFunding returns some periods as aggregated summaries (nSamples set,
    # szi averaged, rate a blend); only single-hour records identify the oracle
    n_agg = int(uf.nSamples.notna().sum())
    uf = uf[uf.nSamples.isna()].copy()
    uf['hour'] = (uf.time + HOUR // 2) // HOUR * HOUR
    j = uf.merge(pub[['coin', 'hour', 'fundingRate']], on=['coin', 'hour'], how='left')
    rel = (j.funding_rate - j.fundingRate).abs() / j.fundingRate.abs().clip(lower=1e-12)
    user = {
        'aggregated_rows_excluded': n_agg,
        'user_funding_rows': int(len(uf)),
        'matched_to_public_hour': int(j.fundingRate.notna().sum()),
        'rate_rel_diff_max': float(rel.max()),
        'rate_rel_diff_gt_1e-4': int((rel > 1e-4).sum()),
        'rate_rel_diff_gt_1e-6': int((rel > 1e-6).sum()),
    }
    return refetch, user, uf


def implied_oracle(uf):
    """Hourly oracle price per coin from accounts' funding payments."""
    u = uf[(uf.szi != 0) & (uf.funding_rate != 0)].copy()
    denom = (u.szi * u.funding_rate).abs()
    u['oracle'] = -u.usdc / (u.szi * u.funding_rate)
    u['rel_rounding'] = 5e-7 / (denom * u.oracle.abs())
    u = u[(u.oracle > 0) & (u.rel_rounding < MAX_REL_ROUNDING)]
    g = u.groupby(['coin', 'hour'])
    o = g.oracle.agg(oracle_px='median', oracle_min='min', oracle_max='max', n_accounts='size').reset_index()
    o['dispersion_bps'] = 1e4 * (o.oracle_max / o.oracle_min - 1)
    return o


def snapshot_comparison(o):
    c = pd.read_csv(CELLS)
    c = c[c.q_org.ne(0) & c.px_org.notna()].copy()
    c['hour'] = (c.t + HOUR // 2) // HOUR * HOUR
    c['offset_min'] = (c.t - c.hour) / 60_000
    c = c[c.offset_min.abs().le(NEAR_MIN)].merge(o[['coin', 'hour', 'oracle_px']], on=['coin', 'hour'])
    c['org_vs_oracle_bps'] = 1e4 * (c.px_org / c.oracle_px - 1)
    c['pool_vs_oracle_bps'] = 1e4 * (c.px_pool / c.oracle_px - 1)
    # one row per (coin, snapshot time): the organiser price is the same across accounts
    s = c.groupby(['coin', 't']).agg(hour=('hour', 'first'), offset_min=('offset_min', 'first'),
                                     px_org=('px_org', 'median'), px_pool=('px_pool', 'median'),
                                     oracle_px=('oracle_px', 'first'),
                                     org_vs_oracle_bps=('org_vs_oracle_bps', 'median'),
                                     pool_vs_oracle_bps=('pool_vs_oracle_bps', 'median')).reset_index()
    return s


def in_season_aggregates(pub):
    """In-season userFunding is returned only as daily aggregates. For a
    (account, coin, day) aggregate, usdc = -sum_h q_h * oracle_h * rate_h, so
    -usdc / sum_h(q_h rate_h) is a q*rate-weighted mean oracle price. Compared
    with the same weighted mean of pooled prints and of organiser prices,
    restricted to days where every weight q_h*rate_h has one sign and the
    reconstructed sample count matches nSamples."""
    import funding_hourly_sensitivity as fhs
    fills = pd.read_parquet(ROOT / 'data' / 'derived' / 'fills.parquet')
    fills = fills[fills.season == 'S15']
    positions, prices = fhs.data_groups(fills)
    rates = pub.assign(hour=pub.time // HOUR * HOUR).set_index(['coin', 'hour']).fundingRate
    c = pd.read_csv(CELLS)
    c = c[c.px_org.notna()].copy()
    c['hour'] = (c.t + HOUR // 2) // HOUR * HOUR
    c = c[((c.t - c.hour) / 60_000).abs().le(NEAR_MIN)]
    org = c.groupby(['coin', 'hour']).px_org.median()
    uf = pd.read_parquet(USER_FUNDING)
    agg = uf[uf.tag.str.startswith('S15__') & uf.coin.isin(COINS) & uf.nSamples.notna()
             & uf.time.between(START, END)]
    rows = []
    for r in agg.itertuples():
        hours = r.time + np.arange(24) * HOUR
        q = fhs.position_path(positions[(r.tag, r.coin)], hours)
        rate = np.array([rates.get((r.coin, h), np.nan) for h in hours])
        pool = fhs.at_times(*prices[r.coin], hours, side='right', initial=np.nan)
        po = np.array([org.get((r.coin, h), np.nan) for h in hours])
        a = q != 0
        w = q[a] * rate[a]
        if a.sum() != r.nSamples or not len(w) or not np.isfinite(w).all() \
                or not (np.all(w > 0) or np.all(w < 0)):
            continue
        implied = -r.usdc / w.sum()
        has_org = np.isfinite(po[a]).all()
        rows.append({'tag': r.tag, 'coin': r.coin, 'day': r.time, 'n_hours': int(a.sum()),
                     'abs_usdc': abs(r.usdc), 'implied_mean_oracle': implied,
                     'pooled_weighted': float(np.sum(w * pool[a]) / w.sum()),
                     'organiser_weighted': float(np.sum(w * po[a]) / w.sum()) if has_org else np.nan})
    d = pd.DataFrame(rows)
    d['pool_vs_oracle_bps'] = 1e4 * (d.pooled_weighted / d.implied_mean_oracle - 1)
    d['org_vs_oracle_bps'] = 1e4 * (d.organiser_weighted / d.implied_mean_oracle - 1)
    # rounding of usdc to 1e-6 is negligible once |usdc| >= 0.1
    return d[d.abs_usdc >= 0.1], int(len(agg))


def summarise(x):
    a = x.abs()
    return {'n': int(len(x)), 'median_bps': float(x.median()), 'median_abs_bps': float(a.median()),
            'p90_abs_bps': float(a.quantile(.9)), 'p99_abs_bps': float(a.quantile(.99)),
            'max_abs_bps': float(a.max()), 'share_within_10bps': float((a <= 10).mean()),
            'share_within_50bps': float((a <= 50).mean())}


def liquidation_check(o):
    lv = pd.read_csv(LIQ)
    rows = []
    for _, e in lv.iterrows():
        oc = o[o.coin == e.coin].set_index('hour').oracle_px
        before = oc[(oc.index <= e.time) & (oc.index > e.time - HOUR)]
        after = oc[(oc.index > e.time) & (oc.index <= e.time + HOUR)]
        b = (before.index[-1], before.iloc[-1]) if len(before) else (np.nan, np.nan)
        a = (after.index[0], after.iloc[0]) if len(after) else (np.nan, np.nan)
        L, side = e.organiser_threshold, e.side
        def beyond(p):
            return bool(p <= L) if side > 0 else bool(p >= L)
        rows.append({'tag': e.tag, 'coin': e.coin, 'time': e.time, 'side': side,
                     'organiser_threshold': L, 'exchange_mark_px': e.mark_px,
                     'mark_beyond_threshold': beyond(e.mark_px),
                     'mark_minus_threshold_pct': e.mark_minus_threshold_pct,
                     'oracle_prev_hour': b[1], 'min_before': (e.time - b[0]) / 60_000 if len(before) else np.nan,
                     'oracle_next_hour': a[1], 'min_after': (a[0] - e.time) / 60_000 if len(after) else np.nan,
                     'oracle_prev_beyond_threshold': beyond(b[1]) if len(before) else None,
                     'oracle_next_beyond_threshold': beyond(a[1]) if len(after) else None,
                     'mark_vs_oracle_prev_bps': 1e4 * (e.mark_px / b[1] - 1) if len(before) else np.nan,
                     'mark_vs_oracle_next_bps': 1e4 * (e.mark_px / a[1] - 1) if len(after) else np.nan})
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--no-fetch', action='store_true')
    fetch = not ap.parse_args().no_fetch
    pub = public_funding(fetch)
    refetch, user, uf = funding_checks(pub)
    o = implied_oracle(uf)
    s = snapshot_comparison(o)
    liq = liquidation_check(o)
    ins, n_agg = in_season_aggregates(pub)
    (OUT / 'organiser_hourly').mkdir(exist_ok=True)
    ins.to_csv(OUT / 'organiser_hourly' / 'oracle_in_season_aggregates.csv', index=False)
    o.to_csv(OUT / 'oracle_implied_hourly.csv', index=False)
    s.to_csv(OUT / 'organiser_hourly' / 'oracle_snapshot_comparison.csv', index=False)
    liq.to_csv(OUT / 'organiser_hourly' / 'oracle_liquidation_check.csv', index=False)
    by_coin = {k: summarise(g.org_vs_oracle_bps) for k, g in s.groupby('coin')}
    res = {
        'generated_utc': datetime.now(timezone.utc).isoformat(),
        'method': 'oracle_px = -usdc / (szi * funding_rate) from accounts userFunding; '
                  'Hyperliquid funding payment = size * oracle price * rate',
        'funding_refetch_vs_stored': refetch,
        'user_vs_public_funding_rate': user,
        'implied_oracle': {'coin_hours': int(len(o)), 'by_coin': o.groupby('coin').size().to_dict(),
                           'multi_account_hours': int((o.n_accounts > 1).sum()),
                           'dispersion_bps_median': float(o.loc[o.n_accounts > 1, 'dispersion_bps'].median()),
                           'dispersion_bps_p99': float(o.loc[o.n_accounts > 1, 'dispersion_bps'].quantile(.99)),
                           'dispersion_bps_max': float(o.loc[o.n_accounts > 1, 'dispersion_bps'].max())},
        'organiser_current_price_vs_oracle': {'near_minutes': NEAR_MIN, 'all': summarise(s.org_vs_oracle_bps),
                                              'within_2min': summarise(s.loc[s.offset_min.abs() <= 2, 'org_vs_oracle_bps']),
                                              'by_coin': by_coin},
        'pooled_print_vs_oracle': summarise(s.pool_vs_oracle_bps.dropna()),
        'window_hourly_comparisons_utc': [str(pd.to_datetime(s.t.min(), unit='ms')),
                                          str(pd.to_datetime(s.t.max(), unit='ms'))],
        'in_season_daily_aggregates': {
            'aggregate_rows': n_agg, 'usable_rows': int(len(ins)),
            'organiser_vs_oracle': summarise(ins.org_vs_oracle_bps.dropna()),
            'pooled_vs_oracle': summarise(ins.pool_vs_oracle_bps.dropna())},
        'liquidations': {
            'events': int(len(liq)),
            'exchange_mark_beyond_organiser_threshold': int(liq.mark_beyond_threshold.sum()),
            'mark_minus_threshold_pct_median_abs': float(liq.mark_minus_threshold_pct.abs().median()),
            'oracle_prev_hour_beyond_threshold': int(liq.oracle_prev_beyond_threshold.fillna(False).sum()),
            'oracle_next_hour_beyond_threshold': int(liq.oracle_next_beyond_threshold.fillna(False).sum()),
            'with_oracle_prev': int(liq.oracle_prev_hour.notna().sum()),
            'with_oracle_next': int(liq.oracle_next_hour.notna().sum())},
    }
    (OUT / 'oracle_validation.json').write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()
