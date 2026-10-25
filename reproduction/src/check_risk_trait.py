"""Check 4: is risk-taking a stable model trait, or an artefact of the rule set?

Four risk metrics per wallet, on the official S1.5 window. Every quantity is
defined on the *continuous* official window and weighted by time, because the
window begins at 17:47 and ends at 22:00, so its first and last days hold 74
and 265 of 288 grid points. Averaging daily means instead would weight a
six-hour day like a full one, and compounding daily returns would drop both
partial pieces (1.9 percentage points on average, 5.7 at most):

    daily volatility      sd over days of the wallet's daily return
    mean gross leverage   time-weighted mean of |notional| / equity over the
                          5-minute grid, i.e. sum(lev x points) / sum(points)
    share of time in mkt  time-weighted share of grid points with a position
    turnover per day      traded notional / mean equity / trading day
    final return          equity at the last grid point of the window over
                          equity at the first, minus one

Everything is built from per-(wallet, day) primitives so that one day-block
bootstrap regenerates all four metrics *and* the final return coherently:

    daily_vol   = sd_d( r )              mean_lev  = mean_d( lev_d )
    share_in    = mean_d( inmkt_d )      turnover  = sum_d(notional_d) /
                                                     (mean_d(eq_d) * |D|)
    final_ret   = prod_d (1 + r) - 1

For each metric: two-way ANOVA (8 models x 4 arms, one wallet per cell) giving
the model F-test and the arm-adjusted (consistency) ICC with its exact F-based
interval; then the rank of each model within each arm and Kendall's W across
arms, testing whether the arms *agree* on the ordering of models.

Note on which Friedman is which. Item 1 used arms as treatments and models as
blocks, asking "do the arms differ?". Here the roles are swapped: the four arms
are the raters and the eight models are the items being ranked, asking "do the
arms agree on the model ordering?". W = 12 S / (m^2 (n^3 - n)) with m=4 raters,
n=8 items, and Friedman chi2 = m (n - 1) W on n - 1 = 7 df; a permutation test
(ranks shuffled independently within each arm) is reported too, since n = 8 is
small for the chi2 approximation.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import analyse
import prov

DER = os.path.join(prov.ROOT, "data", "derived")
RNG = np.random.default_rng(20261013)
NBOOT = 4000
NPERM = 20000
BLOCK = 3
DAY_MS = 86_400_000
ALPHA = 0.05

METRICS = ["daily_vol", "mean_leverage", "share_in_market", "turnover_per_day"]


# ------------------------------------------------------------------ primitives
def primitives():
    """Per (wallet, day): return, mean leverage, in-market share, notional, equity."""
    fills = pd.read_parquet(os.path.join(DER, "fills.parquet"))
    pan = pd.read_parquet(os.path.join(DER, "panel.parquet"))
    eq = pd.read_parquet(os.path.join(DER, "equity.parquet"))
    lo, hi = analyse.common_window(fills, "S15")

    e = eq[(eq["season"] == "S15") & (eq["t"] >= lo) & (eq["t"] <= hi)].copy()
    p = pan[(pan["season"] == "S15") & (pan["t"] >= lo) & (pan["t"] <= hi)].copy()
    f = fills[(fills["season"] == "S15") & (fills["time"] >= lo)
              & (fills["time"] <= hi)].copy()

    e["day"] = e["t"] // DAY_MS
    p["day"] = p["t"] // DAY_MS
    f["day"] = f["time"] // DAY_MS

    meta = e.groupby("tag")[["model", "competition_id"]].first()
    tags = sorted(e["tag"].unique())

    # day-end equity -> daily return
    dayend = e.sort_values("t").groupby(["tag", "day"])["equity"].last().unstack()
    ret = dayend.pct_change(axis=1).iloc[:, 1:]          # (tags, D) first day drops out
    days = list(ret.columns)

    # gross notional and in-market, per grid point then per day
    g = (
        p.assign(absn=p["signed_notional"].abs(),
                 nz=(p["signed_size"].abs() > 1e-12))
        .groupby(["tag", "day", "t"])
        .agg(gross=("absn", "sum"), inmkt=("nz", "any"))
        .reset_index()
    )
    # forward-fill equity onto the panel's grid points, as competitions.py and
    # persistence.py do, so all three modules share one leverage definition
    eqs = (
        e.sort_values("t").set_index(["tag", "t"])["equity"]
        .groupby(level=0).ffill()
    )
    g["equity"] = eqs.reindex(pd.MultiIndex.from_arrays([g["tag"], g["t"]])).to_numpy()
    g["equity"] = g.groupby("tag")["equity"].ffill()
    g["lev"] = g["gross"] / g["equity"].replace(0, np.nan)
    perday = g.groupby(["tag", "day"]).agg(
        lev_sum=("lev", "sum"), inmkt_sum=("inmkt", "sum"),
        # count, not size: leverage is NaN where equity is zero, and the
        # denominator must match the terms actually summed
        npts=("lev", "count"), eq=("equity", "mean")
    )

    f["notional"] = f["sz"].abs() * f["px"]
    notional = f.groupby(["tag", "day"])["notional"].sum()

    def mat(series, fill=0.0):
        return (
            series.unstack()
            .reindex(index=tags, columns=days)
            .astype(float)
            .fillna(fill)
            .to_numpy()
        )

    R = ret.reindex(index=tags, columns=days).to_numpy(float)
    LEV = mat(perday["lev_sum"])      # sum of leverage over the day's grid points
    INM = mat(perday["inmkt_sum"])
    NPT = mat(perday["npts"])
    EQ = mat(perday["eq"])
    NOT = mat(notional)

    # window endpoints, for the single final-return definition
    ends = e.sort_values("t").groupby("tag")["equity"].agg(["first", "last"])
    RET_W = (ends["last"] / ends["first"] - 1.0).reindex(tags).to_numpy(float)

    # Reported leverage and in-market share are time-weighted over EVERY grid
    # point of the official window. The daily panel below starts one day later,
    # because a daily return needs a previous close, so it would silently drop
    # the first (partial) day; `days` has 13 entries against the window's 14.
    wide = g.groupby("tag").agg(lev_sum=("lev", "sum"), npts=("lev", "count"),
                                inmkt_sum=("inmkt", "sum"))
    LEV_W = (wide["lev_sum"] / wide["npts"]).reindex(tags).to_numpy(float)
    INM_W = (wide["inmkt_sum"] / wide["npts"]).reindex(tags).to_numpy(float)
    # forward/backward fill equity so a day with no grid rows cannot zero a mean
    EQ = np.where(EQ > 0, EQ, np.nan)
    EQ = pd.DataFrame(EQ).ffill(axis=1).bfill(axis=1).to_numpy()
    if np.isnan(R).any():
        raise SystemExit("incomplete daily return panel")
    return tags, meta, days, R, LEV, INM, EQ, NOT, NPT, RET_W, LEV_W, INM_W


def metrics_from(R, LEV, INM, EQ, NOT, NPT, cols) -> dict[str, np.ndarray]:
    """Time-weighted over the selected days; see the module docstring.

    `final_return` compounds daily returns, which is the only thing a day
    bootstrap can resample. The *reported* final return uses the window
    endpoints instead (RET_W); the two differ only through the partial days and
    give identical rank correlations.
    """
    nd = len(cols)
    pts = NPT[:, cols].sum(axis=1)
    return {
        "daily_vol": R[:, cols].std(axis=1, ddof=1),
        "mean_leverage": LEV[:, cols].sum(axis=1) / pts,
        "share_in_market": INM[:, cols].sum(axis=1) / pts,
        "turnover_per_day": NOT[:, cols].sum(axis=1)
        / (EQ[:, cols].mean(axis=1) * nd),
        "final_return": np.prod(1 + R[:, cols], axis=1) - 1,
    }


def to_grid(v, tags, meta, models, comps) -> np.ndarray:
    y = np.full((len(models), len(comps)), np.nan)
    for i, t in enumerate(tags):
        y[models.index(meta.loc[t, "model"]), comps.index(meta.loc[t, "competition_id"])] = v[i]
    return y


# ----------------------------------------------------------------- statistics
def anova_icc(y: np.ndarray) -> dict:
    n, k = y.shape
    grand = y.mean()
    rm, cm = y.mean(axis=1), y.mean(axis=0)
    ss_m = k * ((rm - grand) ** 2).sum()
    ss_a = n * ((cm - grand) ** 2).sum()
    ss_e = ((y - grand) ** 2).sum() - ss_m - ss_a
    df_m, df_a, df_e = n - 1, k - 1, (n - 1) * (k - 1)
    ms_m, ms_a, ms_e = ss_m / df_m, ss_a / df_a, ss_e / df_e
    F = ms_m / ms_e
    icc = max((ms_m - ms_e) / k, 0.0)
    icc = icc / (icc + ms_e) if (icc + ms_e) > 0 else np.nan
    FL = F / stats.f.ppf(1 - ALPHA / 2, df_m, df_e)
    FU = F * stats.f.ppf(1 - ALPHA / 2, df_e, df_m)
    return {
        "F_model": F,
        "p_model": float(stats.f.sf(F, df_m, df_e)),
        "icc_armFE": icc,
        "icc_lo": (FL - 1) / (FL + k - 1),
        "icc_hi": (FU - 1) / (FU + k - 1),
        "F_arm": ms_a / ms_e,
        "p_arm": float(stats.f.sf(ms_a / ms_e, df_a, df_e)),
    }


def kendall_w(y: np.ndarray) -> dict:
    """Arms are raters, models are items. y is (n models, m arms)."""
    n, m = y.shape
    ranks = np.apply_along_axis(stats.rankdata, 0, y)   # rank models within each arm
    Ri = ranks.sum(axis=1)
    S = ((Ri - Ri.mean()) ** 2).sum()
    # Midrank ties reduce the attainable rank-sum variation.  The tie term
    # is fixed under within-arm permutations, so it cannot change tail order.
    tie_sum = 0
    for j in range(m):
        counts = np.unique(ranks[:, j], return_counts=True)[1]
        tie_sum += np.sum(counts**3 - counts)
    denominator = m**2 * (n**3 - n) - m * tie_sum
    W = 12 * S / denominator if denominator > 0 else np.nan
    chi2 = m * (n - 1) * W
    return {
        "kendall_W": W,
        "chi2": chi2,
        "p_chi2": float(stats.chi2.sf(chi2, n - 1)),
        "ranks": ranks,
        "rank_sum": Ri,
    }


def perm_p_w(y: np.ndarray, nperm: int = NPERM, rng=None) -> float:
    rng = RNG if rng is None else rng
    n, m = y.shape
    ranks = kendall_w(y)["ranks"]
    obs = ((ranks.sum(axis=1) - m * (n + 1) / 2) ** 2).sum()
    # Preserve each arm's observed tie pattern. Sorting keeps the original
    # random draws unchanged for untied data (base is then 1, ..., n).
    base = np.sort(ranks, axis=0)
    cnt = 0
    for _ in range(nperm):
        shuffled = np.apply_along_axis(rng.permutation, 0, base)
        score = ((shuffled.sum(axis=1) - m * (n + 1) / 2) ** 2).sum()
        # The tie-corrected denominator is constant over this randomisation.
        if score >= obs:
            cnt += 1
    return (cnt + 1) / (nperm + 1)


def block_days(nd: int, n: int) -> np.ndarray:
    nb = int(np.ceil(nd / BLOCK))
    starts = RNG.integers(0, nd, size=(n, nb))
    off = np.arange(BLOCK)
    return ((starts[:, :, None] + off[None, None, :]) % nd).reshape(n, -1)[:, :nd]


def main() -> None:
    pd.set_option("display.width", 260, "display.max_columns", 50)
    (tags, meta, days, R, LEV, INM, EQ, NOT, NPT,
     RET_W, LEV_W, INM_W) = primitives()
    models = sorted(meta["model"].unique())
    comps = sorted(meta["competition_id"].unique())
    nd = len(days)
    allc = np.arange(nd)
    print(f"{len(tags)} wallets, {nd} days, {len(models)} models x {len(comps)} arms\n")

    base = metrics_from(R, LEV, INM, EQ, NOT, NPT, allc)
    # single reported definition: the full official window, time-weighted
    base["final_return"] = RET_W
    base["mean_leverage"] = LEV_W
    base["share_in_market"] = INM_W
    grids = {m: to_grid(base[m], tags, meta, models, comps) for m in METRICS}
    ret_grid = to_grid(base["final_return"], tags, meta, models, comps)

    # wallet-level table
    wt = pd.DataFrame({"tag": tags,
                       "model": [meta.loc[t, "model"] for t in tags],
                       "arm": [meta.loc[t, "competition_id"] for t in tags],
                       **{m: base[m] for m in METRICS},
                       "final_return_pct": 100 * base["final_return"]})
    wt.to_csv(os.path.join(DER, "c4_wallet_risk.csv"), index=False)
    print("=== C4a per-arm means of each risk metric ===")
    print(wt.groupby("arm")[METRICS].mean().to_string(float_format=lambda x: f"{x:,.4f}"))

    # ------------------------------------------------- ANOVA / ICC / Kendall W
    rows = []
    for m in METRICS:
        a = anova_icc(grids[m])
        kw = kendall_w(grids[m])
        rows.append({"metric": m, **{k: v for k, v in a.items()},
                     "kendall_W": kw["kendall_W"], "p_W_chi2": kw["p_chi2"],
                     "p_W_perm": perm_p_w(grids[m])})
    stat = pd.DataFrame(rows)
    stat.to_csv(os.path.join(DER, "c4_stats.csv"), index=False)
    print("\n=== C4b two-way ANOVA, arm-adjusted ICC, and arm agreement on model order ===")
    print(stat.to_string(index=False, float_format=lambda x: f"{x:,.4f}"))

    # rank matrix for the headline metric set
    rk = []
    for m in METRICS:
        ranks = kendall_w(grids[m])["ranks"]
        for i, mdl in enumerate(models):
            rk.append({"metric": m, "model": mdl,
                       **{f"arm{c}": ranks[i, j] for j, c in enumerate(comps)},
                       "rank_sum": ranks[i].sum(),
                       "mean_value": grids[m][i].mean()})
    ranks_df = pd.DataFrame(rk)
    ranks_df.to_csv(os.path.join(DER, "c4_ranks.csv"), index=False)
    print("\n=== C4c rank of each model within each arm (1 = least risk) ===")
    for m in METRICS:
        d = ranks_df[ranks_df["metric"] == m].sort_values("rank_sum")
        print(f"\n{m}  (Kendall W = {stat.set_index('metric').loc[m,'kendall_W']:.3f})")
        print(d[["model"] + [f"arm{c}" for c in comps] + ["rank_sum", "mean_value"]]
              .to_string(index=False, float_format=lambda x: f"{x:,.3f}"))

    # ------------------------------------------- risk vs published ranking
    print("\n=== C4d Spearman rank correlation: mean risk metric vs mean final return ===")
    rc_rows = []
    draws = block_days(nd, NBOOT)
    for m in METRICS:
        x = grids[m].mean(axis=1)
        y = ret_grid.mean(axis=1)
        rho = stats.spearmanr(x, y).statistic
        pear = stats.pearsonr(x, y).statistic
        bs = []
        for b in range(NBOOT):
            mb = metrics_from(R, LEV, INM, EQ, NOT, NPT, draws[b])
            xg = to_grid(mb[m], tags, meta, models, comps).mean(axis=1)
            yg = to_grid(mb["final_return"], tags, meta, models, comps).mean(axis=1)
            bs.append(stats.spearmanr(xg, yg).statistic)
        bs = np.array(bs, dtype=float)
        # permutation p for the model-mean correlation (relabel the 8 returns)
        cnt = 0
        NP = 20000
        for _ in range(NP):
            if stats.spearmanr(x, RNG.permutation(y)).statistic <= rho:
                cnt += 1
        perm_p = (cnt + 1) / (NP + 1)
        rc_rows.append({
            "perm_p_one_sided": perm_p,
            "metric": m,
            "spearman": rho,
            "ci_lo": np.nanpercentile(bs, 2.5),
            "ci_hi": np.nanpercentile(bs, 97.5),
            "boot_sd": np.nanstd(bs, ddof=1),
            "P_rho_lt_0": float((bs < 0).mean()),
            "pearson": pear,
            "spearman_p_exact": float(stats.spearmanr(x, y).pvalue),
        })
    rc = pd.DataFrame(rc_rows)
    rc.to_csv(os.path.join(DER, "c4_rankcorr.csv"), index=False)
    print(rc.to_string(index=False, float_format=lambda x: f"{x:,.4f}"))

    # --------------------------------------------- why the sign is negative
    print("\n=== C4e costs, and the market the window actually delivered ===")
    fl = pd.read_parquet(os.path.join(DER, "fills.parquet"))
    fu = pd.read_parquet(os.path.join(DER, "funding.parquet"))
    lo, hi = analyse.common_window(fl, "S15")
    fl = fl[(fl["season"] == "S15") & (fl["time"] >= lo) & (fl["time"] <= hi)]
    fu = fu[(fu["season"] == "S15") & (fu["time"] >= lo) & (fu["time"] <= hi)]
    fee = fl.groupby("tag")["fee"].sum().reindex(tags).fillna(0.0)
    fund = fu.groupby("tag")["usdc"].sum().reindex(tags).fillna(0.0)
    cost_pct = 100 * (fee - fund) / 10000.0          # as % of the $10k book
    cg = to_grid(cost_pct.to_numpy(), tags, meta, models, comps)
    xc, yc = cg.mean(axis=1), 100 * ret_grid.mean(axis=1)
    rho_c = stats.spearmanr(xc, yc)
    print(f"  total fees paid across the 32 wallets: ${fee.sum():,.0f} "
          f"on a ${32*10000:,} book over {nd} days "
          f"({100*fee.sum()/(32*10000):.1f}% of capital)")
    print(f"  net funding received: ${fund.sum():,.0f}")
    print(f"  mean cost per wallet: {cost_pct.mean():.1f}% of its book "
          f"(min {cost_pct.min():.1f}%, max {cost_pct.max():.1f}%)")
    print(f"  Spearman(cost %, final return %) = {rho_c.statistic:.3f} "
          f"(exact p = {rho_c.pvalue:.4f})")
    rc_extra = {"metric": "cost_pct_of_book", "spearman": float(rho_c.statistic),
                "spearman_p_exact": float(rho_c.pvalue),
                "total_fees_usd": float(fee.sum()),
                "total_funding_usd": float(fund.sum()),
                "mean_cost_pct": float(cost_pct.mean())}

    with open(os.path.join(DER, "c4_summary.json"), "w") as fh:
        json.dump({"stats": rows, "rankcorr": rc_rows, "costs": rc_extra,
                   "models": models, "arms": [int(c) for c in comps],
                   "n_days": nd}, fh, indent=1, default=float)


if __name__ == "__main__":
    main()
