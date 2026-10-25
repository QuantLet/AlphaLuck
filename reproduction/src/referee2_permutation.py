"""Referee item 2: permutation p-values beside the F-based ones, for every ANOVA.

Covers every F-test reported in AUDIT.md on the 8-model x 4-arm Season-1.5
design: the final-return decomposition of section 9, the rescaled outcomes of
section 15, the variance shares of section 16 and the risk metrics of section 17.

Three statistics per outcome:
    F_model (one-way)  MS_model / MS_within,  df (7, 24)   -- arms as replicates
    F_model (arm FE)   MS_model / MS_resid,   df (7, 21)
    F_arm              MS_arm   / MS_resid,   df (3, 21)

Permutation nulls respect the balanced design (each arm holds all eight models
exactly once):
    for a model effect, permute model labels *within* each arm -- i.e. shuffle
        the eight values inside each column, preserving the arm marginals;
    for an arm effect, permute arm labels *within* each model -- shuffle the four
        values inside each row, preserving the model marginals.
10,000 draws each, one-sided (the F statistic is one-sided by construction).
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import variance_components as vc
import prov

DER = os.path.join(prov.ROOT, "data", "derived")
RNG = np.random.default_rng(20261016)
NPERM = 10000


def f_stats(Y: np.ndarray) -> dict[str, np.ndarray]:
    """Vectorised two-way ANOVA. Y is (B, n models, k arms)."""
    if Y.ndim == 2:
        Y = Y[None]
    B, n, k = Y.shape
    grand = Y.mean(axis=(1, 2), keepdims=True)
    rm = Y.mean(axis=2)
    cm = Y.mean(axis=1)
    ss_m = k * ((rm - grand[:, :, 0]) ** 2).sum(axis=1)
    ss_a = n * ((cm - grand[:, 0, :]) ** 2).sum(axis=1)
    ss_tot = ((Y - grand) ** 2).sum(axis=(1, 2))
    ss_w = ((Y - rm[:, :, None]) ** 2).sum(axis=(1, 2))
    ss_e = ss_tot - ss_m - ss_a
    ms_m = ss_m / (n - 1)
    ms_a = ss_a / (k - 1)
    ms_w = ss_w / (n * (k - 1))
    ms_e = ss_e / ((n - 1) * (k - 1))
    with np.errstate(divide="ignore", invalid="ignore"):
        return {
            "F_model_oneway": ms_m / ms_w,
            "F_model_armFE": ms_m / ms_e,
            "F_arm": ms_a / ms_e,
        }


def shuffle_within_cols(y: np.ndarray, nperm: int) -> np.ndarray:
    """(nperm, n, k): independently permute the n rows inside each column."""
    n, k = y.shape
    out = np.repeat(y[None], nperm, axis=0)
    order = RNG.random((nperm, n, k)).argsort(axis=1)
    return np.take_along_axis(out, order, axis=1)


def shuffle_within_rows(y: np.ndarray, nperm: int) -> np.ndarray:
    """(nperm, n, k): independently permute the k columns inside each row."""
    n, k = y.shape
    out = np.repeat(y[None], nperm, axis=0)
    order = RNG.random((nperm, n, k)).argsort(axis=2)
    return np.take_along_axis(out, order, axis=2)


def outcomes() -> dict[str, np.ndarray]:
    """Every ANOVA outcome quoted in the paper, as an 8 x 4 matrix."""
    X, models, comps, T = vc.panel("daily")
    met = pd.read_csv(os.path.join(DER, "i1_wallet_metrics.csv"))
    L = np.ones(X.shape[:2])
    for r in met.itertuples():
        L[models.index(r.model), comps.index(r.competition_id)] = r.mean_leverage

    desc = pd.read_csv(os.path.join(DER, "t1_descriptive.csv"))
    pub = (
        desc[desc["season"] == "S15"]
        .pivot(index="model", columns="competition_id", values="return_pct")
        .loc[models, comps]
        .to_numpy(float)
    )
    sd = X.std(axis=2, ddof=1)
    out = {
        "final return % (published, sec 9/13)": pub,
        "cumulative return % arithmetic (sec 15)": 100 * X.sum(axis=2),
        "leverage-scaled cumulative % (sec 15/16)": 100 * X.sum(axis=2) / L,
        "vol-standardised cumulative (sec 15)": (X / sd[:, :, None]).sum(axis=2),
        "daily Sharpe (sec 16)": X.mean(axis=2) / sd,
    }
    w = pd.read_csv(os.path.join(DER, "c4_wallet_risk.csv"))
    for m, lab in [("daily_vol", "realised daily volatility (sec 17)"),
                   ("mean_leverage", "mean gross leverage (sec 17)"),
                   ("share_in_market", "share of time in market (sec 17)"),
                   ("turnover_per_day", "turnover per day (sec 17)")]:
        out[lab] = (
            w.pivot(index="model", columns="arm", values=m)
            .loc[models, comps]
            .to_numpy(float)
        )
    return out


def main() -> None:
    pd.set_option("display.width", 280, "display.max_columns", 40)
    rows = []
    for label, y in outcomes().items():
        obs = {k: float(v[0]) for k, v in f_stats(y).items()}
        n, k = y.shape
        perm_cols = f_stats(shuffle_within_cols(y, NPERM))   # model nulls
        perm_rows = f_stats(shuffle_within_rows(y, NPERM))   # arm null
        dfs = {
            "F_model_oneway": (n - 1, n * (k - 1)),
            "F_model_armFE": (n - 1, (n - 1) * (k - 1)),
            "F_arm": (k - 1, (n - 1) * (k - 1)),
        }
        for stat in ["F_model_oneway", "F_model_armFE", "F_arm"]:
            draws = perm_rows[stat] if stat == "F_arm" else perm_cols[stat]
            d1, d2 = dfs[stat]
            rows.append(
                {
                    "outcome": label,
                    "test": stat,
                    "df": f"({d1},{d2})",
                    "F": obs[stat],
                    "p_F": float(stats.f.sf(obs[stat], d1, d2)),
                    "p_perm": float((np.nansum(draws >= obs[stat]) + 1) / (NPERM + 1)),
                    "perm_scheme": "arm labels within model"
                    if stat == "F_arm"
                    else "model labels within arm",
                }
            )
    res = pd.DataFrame(rows)
    res.to_csv(os.path.join(DER, "r2_permutation.csv"), index=False)

    print(f"=== R2 permutation vs F-based p-values, {NPERM:,} draws ===\n")
    for stat in ["F_model_oneway", "F_model_armFE", "F_arm"]:
        d = res[res["test"] == stat]
        print(f"--- {stat}  {d['df'].iloc[0]} ---")
        print(d[["outcome", "F", "p_F", "p_perm"]].to_string(
            index=False, float_format=lambda x: f"{x:,.4f}"))
        print()

    diff = (res["p_perm"] - res["p_F"]).abs()
    both = res[(res["p_F"] < 0.05) != (res["p_perm"] < 0.05)]
    print(f"max |p_perm - p_F| = {diff.max():.4f} (mean {diff.mean():.4f})")
    print(f"tests where the 5% verdict differs: {len(both)} of {len(res)}")
    if len(both):
        print(both[["outcome", "test", "F", "p_F", "p_perm"]].to_string(index=False))

    with open(os.path.join(DER, "r2_permutation.json"), "w") as fh:
        json.dump({"nperm": NPERM, "rows": rows,
                   "max_abs_diff": float(diff.max()),
                   "n_verdict_flips": int(len(both))}, fh, indent=1, default=float)


if __name__ == "__main__":
    main()
