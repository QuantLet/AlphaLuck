"""Check 3: how much of the outcome spread is the model, how much is the rules?

Two-way ANOVA (8 models x 4 arms, one wallet per cell) on three outcomes, with
the variance split into a model component, an arm component and a residual:

    var_model = max( (MS_model - MS_resid) / k , 0 )
    var_arm   = max( (MS_arm   - MS_resid) / n , 0 )
    var_resid = MS_resid
    shares    = each / (var_model + var_arm + var_resid)

Outcomes:
    final return      equity at the last grid point of the official window over
                      equity at the first, minus one -- the single definition
                      used throughout the paper. Inside the day bootstrap the
                      daily returns are compounded instead, since a resampled
                      set of days admits nothing else; the two differ only
                      through the window's two partial days (1.9pp on average).
    leverage-scaled   100 * sum_t x / L      (L = wallet's mean gross leverage)
    Sharpe            mean_t(x) / sd_t(x)    (daily)

Intervals: moving-block bootstrap over the 13 days (block 3, 4,000 draws), the
same day-blocks applied to every wallet, outcomes recomputed from the resampled
returns and the ANOVA refitted each draw.

IMPORTANT, and not fixable with this data: there is exactly one wallet per
(model, arm) cell, so the residual is model-by-arm interaction *plus* replicate
luck and the two cannot be separated. A "model behaves differently under
max leverage" effect is therefore scored as residual here, which if anything
understates the model's role. Separating them needs at least two wallets per
cell -- i.e. genuine replication within each arm.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import prov
import variance_components as vc

DER = os.path.join(prov.ROOT, "data", "derived")
RNG = np.random.default_rng(20261012)
NBOOT = 4000
BLOCK = 3


def two_way_shares(y: np.ndarray) -> dict:
    n, k = y.shape
    grand = y.mean()
    rm, cm = y.mean(axis=1), y.mean(axis=0)
    ss_model = k * ((rm - grand) ** 2).sum()
    ss_arm = n * ((cm - grand) ** 2).sum()
    ss_tot = ((y - grand) ** 2).sum()
    ss_resid = ss_tot - ss_model - ss_arm
    df_m, df_a, df_e = n - 1, k - 1, (n - 1) * (k - 1)
    ms_m, ms_a, ms_e = ss_model / df_m, ss_arm / df_a, ss_resid / df_e
    v_m = max((ms_m - ms_e) / k, 0.0)
    v_a = max((ms_a - ms_e) / n, 0.0)
    tot = v_m + v_a + ms_e
    return {
        "share_model": v_m / tot if tot > 0 else np.nan,
        "share_arm": v_a / tot if tot > 0 else np.nan,
        "share_resid": ms_e / tot if tot > 0 else np.nan,
        "F_model": ms_m / ms_e,
        "p_model": float(stats.f.sf(ms_m / ms_e, df_m, df_e)),
        "F_arm": ms_a / ms_e,
        "p_arm": float(stats.f.sf(ms_a / ms_e, df_a, df_e)),
        "ss_share_model": ss_model / ss_tot,
        "ss_share_arm": ss_arm / ss_tot,
        "ss_share_resid": ss_resid / ss_tot,
    }


def outcomes(X: np.ndarray, L: np.ndarray, ret_w: np.ndarray | None = None
             ) -> dict[str, np.ndarray]:
    """Outcomes on the 8x4 grid.

    `ret_w` is the reported final return, measured between the first and last
    grid point of the official window (the single definition used throughout).
    When it is None -- inside the day bootstrap -- the daily returns are
    compounded instead, which is the only thing a resampled set of days admits.
    The two differ only through the window's two partial days.
    """
    with np.errstate(divide="ignore", invalid="ignore"):
        sd = X.std(axis=2, ddof=1)
        sharpe = np.where(sd > 0, X.mean(axis=2) / sd, np.nan)
    final = ret_w if ret_w is not None else 100 * (np.prod(1 + X, axis=2) - 1)
    return {
        "final return %": final,
        "leverage-scaled cumulative %": 100 * X.sum(axis=2) / L,
        "daily Sharpe": sharpe,
    }


def main() -> None:
    pd.set_option("display.width", 260, "display.max_columns", 50)
    X, models, comps, T = vc.panel("daily")
    met = pd.read_csv(os.path.join(DER, "i1_wallet_metrics.csv"))
    L = np.ones(X.shape[:2])
    for r in met.itertuples():
        L[models.index(r.model), comps.index(r.competition_id)] = r.mean_leverage

    pub = (
        pd.read_csv(os.path.join(DER, "t1_descriptive.csv"))
        .query("season == 'S15'")
        .pivot(index="model", columns="competition_id", values="return_pct")
        .loc[models, comps]
        .to_numpy(float)
    )
    point = {k: two_way_shares(v) for k, v in outcomes(X, L, pub).items()}

    rebuilt = 100 * (np.prod(1 + X, axis=2) - 1)
    print(f"reported final return (window endpoints) vs the day-compounded "
          f"version used inside the bootstrap: max gap "
          f"{np.abs(rebuilt - pub).max():.2f}pp, mean "
          f"{np.abs(rebuilt - pub).mean():.2f}pp\n")

    draws = vc.block_days(T, BLOCK, NBOOT)
    boot = {k: [] for k in point}
    for b in range(NBOOT):
        Xb = X[:, :, draws[b]]
        for k, v in outcomes(Xb, L).items():
            if np.isnan(v).any():
                continue
            boot[k].append(two_way_shares(v))

    rows = []
    for k in point:
        bd = pd.DataFrame(boot[k])
        for q in ["share_model", "share_arm", "share_resid", "F_model", "p_model",
                  "F_arm", "p_arm"]:
            v = bd[q].to_numpy(float)
            rows.append(
                {
                    "outcome": k,
                    "quantity": q,
                    "estimate": point[k][q],
                    "ci_lo": np.nanpercentile(v, 2.5),
                    "ci_hi": np.nanpercentile(v, 97.5),
                    "n_boot": len(bd),
                }
            )
    res = pd.DataFrame(rows)
    res.to_csv(os.path.join(DER, "c3_variance_shares.csv"), index=False)

    print("=== C3 two-way variance shares, 95% day-bootstrap intervals ===")
    for k in point:
        d = res[res["outcome"] == k].set_index("quantity")
        print(f"\n{k}")
        for q, lab in [("share_model", "model"), ("share_arm", "arm (rules)"),
                       ("share_resid", "residual = interaction + luck")]:
            r = d.loc[q]
            print(f"   {lab:<30} {r.estimate:6.3f}  [{r.ci_lo:.3f}, {r.ci_hi:.3f}]")
        for q, lab in [("F_model", "F model (7,21)"), ("F_arm", "F arm (3,21)")]:
            r = d.loc[q]
            print(f"   {lab:<30} {r.estimate:6.2f}  [{r.ci_lo:.2f}, {r.ci_hi:.2f}]"
                  f"   p = {point[k]['p_' + q.split('_')[1]]:.3f}")

    print("\n--- sums-of-squares shares (descriptive, no component truncation) ---")
    ss = pd.DataFrame(
        [{"outcome": k, **{q: point[k][q] for q in
                           ["ss_share_model", "ss_share_arm", "ss_share_resid"]}}
         for k in point]
    )
    print(ss.to_string(index=False, float_format=lambda x: f"{x:,.3f}"))

    with open(os.path.join(DER, "c3_summary.json"), "w") as fh:
        json.dump(point, fh, indent=1, default=float)


if __name__ == "__main__":
    main()
