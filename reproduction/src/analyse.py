"""Phase 3 descriptive audit: activity, similarity (Q1), precision (Q2).

Method choices, fixed here and reported rather than tuned:
  grid              5-minute, UTC, from the fills of the arena wallets
  marks             last traded print per coin, pooled over all 38 arena wallets
                    and forward-filled (Hyperliquid serves no 5m/1h candles this
                    far back -- see data/derived/candle_probe.json)
  common window     per season, max(first fill) .. min(last fill) over wallets
  trading day       UTC calendar day with at least one fill
  daily return      last 5-min equity of each UTC day, simple return
  Sharpe            daily mean / daily sd; annualised by sqrt(365) (the venue
                    trades 24/7, including weekends, in both seasons)
  Sharpe SE         Lo (2002) delta method on (mean, variance) with a
                    Newey-West/Bartlett HAC covariance, lag = floor(4*(T/100)^(2/9))
  paired bootstrap  moving-block bootstrap over days, block length 3, 10,000 draws,
                    same day-blocks applied to both models of a pair
  power             n = (z_0.975 + z_0.80)^2 * sd(diff)^2 / mean(diff)^2
"""
from __future__ import annotations

import itertools
import os
import sys

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import prov
import wallets

DER = os.path.join(prov.ROOT, "data", "derived")
HOUR_MS = 3600 * 1000
DAY_MS = 86400 * 1000
RNG = np.random.default_rng(20261008)
NBOOT = 10000
BLOCK = 3
Z = stats.norm.ppf(0.975) + stats.norm.ppf(0.80)  # 2.8016


def load():
    fills = pd.read_parquet(os.path.join(DER, "fills.parquet"))
    rt = pd.read_parquet(os.path.join(DER, "roundtrips.parquet"))
    pan = pd.read_parquet(os.path.join(DER, "panel.parquet"))
    eq = pd.read_parquet(os.path.join(DER, "equity.parquet"))
    fu = pd.read_parquet(os.path.join(DER, "funding.parquet"))
    recon = pd.read_parquet(os.path.join(DER, "recon.parquet"))
    return fills, rt, pan, eq, fu, recon


def common_window(fills: pd.DataFrame, season: str, official: bool = True) -> tuple[int, int]:
    """The organiser's published season: official start .. official end.

    This used to start at max(first fill) across accounts, which is not the
    season but the moment the last account happened to trade for the first
    time. In Season 1.5 that threw away the first 20.8 hours, during which
    every account was already trading: by the old start, account equity ranged
    from 5,765 to 15,278 rather than the 10,000 each was funded with. Returns
    measured from there are returns on a mid-season balance, and they do not
    reconcile with a profit-and-loss decomposition whose denominator is initial
    capital. On the published window every account starts at exactly 10,000, so
    the two agree by construction.

    On-chain activity runs past the published end in both seasons (to
    2025-11-13 in S1 and 2025-12-14 in S1.5); official=False gives the full
    on-chain window, which the continuation sample uses.
    """
    f = fills[fills["season"] == season]
    if official:
        return int(wallets.SEASON_START[season]), int(wallets.OFFICIAL_END[season])
    g = f.groupby("tag")["time"]
    return int(g.min().max()), int(g.max().min())


# ------------------------------------------------------------------ descriptive
def descriptive(fills, rt, pan, eq, fu) -> pd.DataFrame:
    out = []
    for season in ["S1", "S15"]:
        lo, hi = common_window(fills, season)
        for tag, g in fills[fills["season"] == season].groupby("tag"):
            w = g[(g["time"] >= lo) & (g["time"] <= hi)]
            p = pan[(pan["tag"] == tag) & (pan["t"] >= lo) & (pan["t"] <= hi)]
            e = eq[(eq["tag"] == tag) & (eq["t"] >= lo) & (eq["t"] <= hi)].sort_values("t")
            r = rt[(rt["tag"] == tag) & (rt["entry_time"] >= lo) & (rt["exit_time"] <= hi)]
            f_ = fu[(fu["tag"] == tag) & (fu["time"] >= lo) & (fu["time"] <= hi)]

            # exposure/leverage on the grid
            grp = p.groupby("t")
            gross = grp["signed_notional"].apply(lambda s: s.abs().sum())
            inmkt = grp["signed_size"].apply(lambda s: (s.abs() > 1e-12).any())
            eqs = e.set_index("t")["equity"].reindex(gross.index).ffill()
            lev = (gross / eqs.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan)

            e0 = float(e["equity"].iloc[0]) if len(e) else np.nan
            e1 = float(e["equity"].iloc[-1]) if len(e) else np.nan
            curve = e.set_index("t")["equity"]
            dd = (curve / curve.cummax() - 1).min() if len(curve) else np.nan

            out.append(
                {
                    "season": season,
                    "competition_id": g["competition_id"].iloc[0],
                    "model": g["model"].iloc[0],
                    "tag": tag,
                    "n_fills": len(w),
                    "n_roundtrips": len(r),
                    "n_coins": w["coin"].nunique(),
                    "trading_days": pd.to_datetime(w["time"], unit="ms", utc=True)
                    .dt.date.nunique(),
                    "share_in_market": float(inmkt.mean()) if len(inmkt) else np.nan,
                    "median_hold_h": float(r["hold_ms"].median() / HOUR_MS)
                    if len(r)
                    else np.nan,
                    "mean_leverage": float(lev.mean()),
                    "max_leverage": float(lev.max()),
                    "fees_usd": float(w["fee"].sum()),
                    "funding_usd": float(f_["usdc"].sum()),
                    "equity_start": e0,
                    "equity_end": e1,
                    "return_pct": 100 * (e1 / e0 - 1) if e0 else np.nan,
                    "max_drawdown_pct": 100 * dd,
                }
            )
    return pd.DataFrame(out)


# -------------------------------------------------------------------- similarity
def _grid_series(pan, tag, lo, hi, coins):
    """signed notional per coin, and the aggregate, on the common grid."""
    p = pan[(pan["tag"] == tag) & (pan["t"] >= lo) & (pan["t"] <= hi)]
    wide = p.pivot_table(index="t", columns="coin", values="signed_notional",
                         aggfunc="sum").reindex(columns=coins)
    szw = p.pivot_table(index="t", columns="coin", values="signed_size",
                        aggfunc="sum").reindex(columns=coins)
    return wide.fillna(0.0), szw.fillna(0.0)


def similarity(fills, pan, eq, season, group: str) -> pd.DataFrame:
    """Pairwise exposure correlation, same-direction share and 1h-PnL correlation.

    group: 'within_competition' pairs distinct models inside one competition;
           'across_competition' pairs the same model in different competitions
           (a same-model replicate benchmark for how much of the overlap is the
           market rather than the model).
    """
    lo, hi = common_window(fills, season)
    f = fills[fills["season"] == season]
    coins = sorted(f["coin"].unique())
    tags = sorted(f["tag"].unique())
    meta = {t: f[f["tag"] == t].iloc[0] for t in tags}

    series = {}
    for t in tags:
        nw, sw = _grid_series(pan, t, lo, hi, coins)
        e = eq[(eq["tag"] == t) & (eq["t"] >= lo) & (eq["t"] <= hi)].sort_values("t")
        e = e.set_index("t")["equity"]
        hr = e.groupby((e.index // HOUR_MS)).last()
        series[t] = (nw, sw, hr.diff().dropna())

    rows = []
    for a, b in itertools.combinations(tags, 2):
        ca, cb = meta[a]["competition_id"], meta[b]["competition_id"]
        ma, mb = meta[a]["model"], meta[b]["model"]
        if group == "within_competition" and (ca != cb or ma == mb):
            continue
        if group == "across_competition" and (ca == cb or ma != mb):
            continue

        na, sa, ha = series[a]
        nb, sb, hb = series[b]
        idx = na.index.intersection(nb.index)
        na, nb, sa, sb = na.loc[idx], nb.loc[idx], sa.loc[idx], sb.loc[idx]

        # aggregate signed exposure
        agg_a, agg_b = na.sum(axis=1), nb.sum(axis=1)
        agg_corr = agg_a.corr(agg_b)

        # per-coin correlation, averaged over coins where both ever traded
        percoin, dirshare, both_cov = {}, {}, {}
        for c in coins:
            x, y = na[c], nb[c]
            if x.abs().sum() == 0 or y.abs().sum() == 0:
                continue
            percoin[c] = x.corr(y)
            both = (sa[c].abs() > 1e-12) & (sb[c].abs() > 1e-12)
            both_cov[c] = float(both.mean())
            if both.sum():
                dirshare[c] = float(
                    (np.sign(sa[c][both]) == np.sign(sb[c][both])).mean()
                )
        hidx = ha.index.intersection(hb.index)
        pnl_corr = ha.loc[hidx].corr(hb.loc[hidx]) if len(hidx) > 3 else np.nan

        rows.append(
            {
                "season": season,
                "a": f"c{ca}:{ma}" if season == "S15" else ma,
                "b": f"c{cb}:{mb}" if season == "S15" else mb,
                "model_a": ma,
                "model_b": mb,
                "comp_a": ca,
                "comp_b": cb,
                "exposure_corr_agg": agg_corr,
                "exposure_corr_percoin_mean": np.nanmean(list(percoin.values()))
                if percoin
                else np.nan,
                "same_direction_share": np.nanmean(list(dirshare.values()))
                if dirshare
                else np.nan,
                "both_in_market_share": np.nanmean(list(both_cov.values()))
                if both_cov
                else np.nan,
                "pnl1h_corr": pnl_corr,
                "n_coins_compared": len(percoin),
                "n_grid": len(idx),
            }
        )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------- precision
def daily_returns(eq, tag, lo, hi) -> pd.Series:
    e = eq[(eq["tag"] == tag) & (eq["t"] >= lo) & (eq["t"] <= hi)].sort_values("t")
    s = e.set_index("t")["equity"]
    d = s.groupby(s.index // DAY_MS).last()
    return d.pct_change().dropna()


def nw_lag(T: int) -> int:
    return max(1, int(np.floor(4 * (T / 100) ** (2 / 9))))


def sharpe_se_lo(r: np.ndarray) -> tuple[float, float]:
    """Daily Sharpe and its SE, Lo (2002) delta method with Newey-West HAC."""
    T = len(r)
    if T < 5:
        return np.nan, np.nan
    mu = r.mean()
    var = r.var(ddof=1)
    sd = np.sqrt(var)
    sr = mu / sd if sd > 0 else np.nan
    # moment conditions g_t = (r_t - mu, (r_t-mu)^2 - var)
    g = np.column_stack([r - mu, (r - mu) ** 2 - var])
    L = nw_lag(T)
    Om = g.T @ g / T
    for l in range(1, L + 1):
        w = 1 - l / (L + 1)
        G = g[l:].T @ g[:-l] / T
        Om += w * (G + G.T)
    grad = np.array([1 / sd, -mu / (2 * var * sd)])
    v = grad @ Om @ grad / T
    return float(sr), float(np.sqrt(max(v, 0)))


def block_idx(T: int, block: int, n: int) -> np.ndarray:
    nb = int(np.ceil(T / block))
    starts = RNG.integers(0, T, size=(n, nb))
    off = np.arange(block)
    idx = (starts[:, :, None] + off[None, None, :]) % T
    return idx.reshape(n, -1)[:, :T]


def paired_bootstrap(ra: np.ndarray, rb: np.ndarray) -> dict:
    """SE of the difference in mean daily return and in daily Sharpe."""
    T = len(ra)
    idx = block_idx(T, BLOCK, NBOOT)
    A, B = ra[idx], rb[idx]
    dmean = A.mean(1) - B.mean(1)
    sa = A.mean(1) / A.std(1, ddof=1)
    sb = B.mean(1) / B.std(1, ddof=1)
    dsharpe = sa - sb
    obs_dmean = ra.mean() - rb.mean()
    obs_ds = ra.mean() / ra.std(ddof=1) - rb.mean() / rb.std(ddof=1)
    diff = ra - rb
    sd_diff = diff.std(ddof=1)
    n_req = (Z**2) * sd_diff**2 / obs_dmean**2 if obs_dmean else np.inf
    return {
        "T_days": T,
        "d_mean_daily_ret": obs_dmean,
        "se_d_mean_boot": float(np.nanstd(dmean, ddof=1)),
        "d_sharpe_daily": obs_ds,
        "se_d_sharpe_boot": float(np.nanstd(dsharpe, ddof=1)),
        "sd_daily_diff": float(sd_diff),
        "corr_daily": float(np.corrcoef(ra, rb)[0, 1]),
        "days_needed_80pct_power": float(n_req),
    }


def precision(fills, eq, season) -> tuple[pd.DataFrame, pd.DataFrame]:
    lo, hi = common_window(fills, season)
    f = fills[fills["season"] == season]
    tags = sorted(f["tag"].unique())
    meta = {t: f[f["tag"] == t].iloc[0] for t in tags}
    rets = {t: daily_returns(eq, t, lo, hi) for t in tags}
    common = None
    for s in rets.values():
        common = s.index if common is None else common.intersection(s.index)

    per = []
    for t in tags:
        r = rets[t].reindex(common).dropna().to_numpy()
        sr, se = sharpe_se_lo(r)
        per.append(
            {
                "season": season,
                "competition_id": meta[t]["competition_id"],
                "model": meta[t]["model"],
                "tag": t,
                "T_days": len(r),
                "mean_daily_ret_pct": 100 * r.mean(),
                "sd_daily_ret_pct": 100 * r.std(ddof=1),
                "sharpe_daily": sr,
                "sharpe_ann": sr * np.sqrt(365),
                "se_sharpe_daily_lo2002": se,
                "nw_lag": nw_lag(len(r)),
            }
        )
    perdf = pd.DataFrame(per).sort_values("mean_daily_ret_pct", ascending=False)

    # best vs worst, and the two closest, by mean daily return
    pairs = []
    srt = perdf.reset_index(drop=True)
    cand = [("best_vs_worst", srt["tag"].iloc[0], srt["tag"].iloc[-1])]
    gaps = srt["mean_daily_ret_pct"].diff().abs()
    j = int(gaps.iloc[1:].idxmin())
    cand.append(("two_closest", srt["tag"].iloc[j - 1], srt["tag"].iloc[j]))
    for label, a, b in cand:
        ra = rets[a].reindex(common).dropna()
        rb = rets[b].reindex(common).dropna()
        k = ra.index.intersection(rb.index)
        res = paired_bootstrap(ra.loc[k].to_numpy(), rb.loc[k].to_numpy())
        pairs.append(
            {
                "season": season,
                "pair": label,
                "a": a,
                "b": b,
                **res,
            }
        )
    return perdf, pd.DataFrame(pairs)


def main() -> None:
    fills, rt, pan, eq, fu, recon = load()
    pd.set_option("display.width", 250, "display.max_columns", 60)

    desc = descriptive(fills, rt, pan, eq, fu)
    desc.to_csv(os.path.join(DER, "t1_descriptive.csv"), index=False)
    print("=== T1 descriptive ===")
    print(desc.to_string(index=False, float_format=lambda x: f"{x:,.2f}"))

    sims = []
    for season in ["S1", "S15"]:
        for grp in ["within_competition", "across_competition"]:
            s = similarity(fills, pan, eq, season, grp)
            if len(s):
                s["group"] = grp
                sims.append(s)
    sim = pd.concat(sims, ignore_index=True)
    sim.to_csv(os.path.join(DER, "t2_similarity.csv"), index=False)
    print("\n=== T2 similarity: S1, all 15 pairs ===")
    s1 = sim[sim["season"] == "S1"]
    print(
        s1[
            [
                "a",
                "b",
                "exposure_corr_agg",
                "exposure_corr_percoin_mean",
                "same_direction_share",
                "both_in_market_share",
                "pnl1h_corr",
            ]
        ].to_string(index=False, float_format=lambda x: f"{x:,.3f}")
    )
    print("\n=== T2 similarity: S15 summary by group ===")
    print(
        sim[sim["season"] == "S15"]
        .groupby("group")[
            [
                "exposure_corr_agg",
                "exposure_corr_percoin_mean",
                "same_direction_share",
                "pnl1h_corr",
            ]
        ]
        .agg(["mean", "std", "count"])
        .to_string(float_format=lambda x: f"{x:,.3f}")
    )

    pers, prs = [], []
    for season in ["S1", "S15"]:
        p, q = precision(fills, eq, season)
        pers.append(p)
        prs.append(q)
    per = pd.concat(pers, ignore_index=True)
    pr = pd.concat(prs, ignore_index=True)
    per.to_csv(os.path.join(DER, "t3_precision_per_model.csv"), index=False)
    pr.to_csv(os.path.join(DER, "t4_precision_pairs.csv"), index=False)
    print("\n=== T3 per-model precision ===")
    print(per.to_string(index=False, float_format=lambda x: f"{x:,.3f}"))
    print("\n=== T4 pairwise precision / power ===")
    print(pr.to_string(index=False, float_format=lambda x: f"{x:,.4f}"))


if __name__ == "__main__":
    main()
