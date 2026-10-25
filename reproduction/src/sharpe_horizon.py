"""How long a season would have to be, on the Sharpe-difference estimand.

The horizon the paper quoted came from the variance of daily *return*
differences. That is the right variance for a difference in mean returns, not
for a difference in Sharpe ratios, which also involves each account's
volatility, the uncertainty in estimating it, and the dependence between the
two accounts. In a paper whose main finding is that the models differ in
volatility, that substitution is not innocuous. The referee is right.

This module rebuilds the calculation on the quantity actually of interest,

    Delta = sqrt(365) * ( mu_1/sigma_1 - mu_2/sigma_2 ),

for each of the 28 pairs of the eight models, with each model represented by
the daily return of the sum of its four account equities (equal initial
capital, subsequently varying weights; no daily rebalancing). Annualisation is by
sqrt(365) because the venue trades continuously and the equity series has a
mark every calendar day; there are no non-trading days to handle.

Two variance estimators, both in the spirit of Ledoit and Wolf (2008):

  HAC delta method. Stack the moment conditions (r_1, r_2, r_1^2, r_2^2),
  estimate their long-run covariance with a Bartlett kernel at bandwidth L,
  and map it through the gradient of Delta. Reported at L = 0, 1, 2, 3, where
  L = 0 is the iid case.

  Joint block bootstrap. Resample *common* time blocks: the same block indices
  are applied to every account at once, so contemporaneous dependence across
  accounts is preserved by construction and only the time dimension is
  resampled. Block lengths 1, 2 and 3 days.

With V the per-observation asymptotic variance of the daily Sharpe difference,
detecting an annualised gap of delta at the 5 per cent level with 80 per cent
power needs T >= 365 z^2 V / delta^2 days, that is

    T_years = z^2 V / delta^2,        z = 1.96 + 0.8416,  z^2 = 7.849,

and at the sample length actually available the smallest detectable gap is
delta_min = z sqrt(365 V / T).

The figures are a conditional planning calibration, not a property of language
models. Fourteen daily observations per account cannot identify a long-run
variance; the spread across bandwidths and block lengths is reported for that
reason, and the dependence on the pair correlation is reported separately,
because that is the assumption the answer is most sensitive to.

Writes data/derived/s1_sharpe_horizon.{csv,json}.
"""
from __future__ import annotations

import itertools
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import analyse
import prov

DER = os.path.join(prov.ROOT, "data", "derived")
RNG = np.random.default_rng(20261009)
Z2 = (1.959963985 + 0.8416212336) ** 2
PERIODS = 365.0
NBOOT = 4000
BANDWIDTHS = (0, 1, 2, 3)
BLOCKS = (1, 2, 3)
DAY_MS = 86_400_000


def daily_model_returns(season: str = "S15") -> pd.DataFrame:
    """Daily return of aggregate account equity, with no daily rebalancing."""
    eq = pd.read_parquet(os.path.join(DER, "equity.parquet"))
    fills = pd.read_parquet(os.path.join(DER, "fills.parquet"))
    lo, hi = analyse.common_window(fills, season)
    e = eq[(eq["season"] == season) & (eq["t"] >= lo) & (eq["t"] <= hi)].copy()
    e["day"] = e["t"] // DAY_MS
    # last equity mark of each day for each account
    dayend = (e.sort_values("t").groupby(["model", "tag", "day"])["equity"]
              .last().reset_index())
    # Equal initial capital, then varying equity weights: return on aggregate equity.
    book = dayend.groupby(["model", "day"])["equity"].sum().unstack("model")
    return book.sort_index().pct_change().dropna(how="any")


def lw_variance(r1: np.ndarray, r2: np.ndarray, L: int) -> float:
    """Per-observation asymptotic variance of the daily Sharpe difference.

    Ledoit-Wolf (2008) delta method: the Sharpe difference is a smooth
    function of (mu_1, mu_2, gamma_1, gamma_2) with gamma_i = E[r_i^2]; the
    long-run covariance of those four moments is estimated with a Bartlett
    kernel at bandwidth L (L = 0 gives the iid case).
    """
    T = len(r1)
    m1, m2 = r1.mean(), r2.mean()
    g1, g2 = (r1 ** 2).mean(), (r2 ** 2).mean()
    s1sq, s2sq = g1 - m1 ** 2, g2 - m2 ** 2
    if s1sq <= 0 or s2sq <= 0:
        return np.nan
    s1, s2 = np.sqrt(s1sq), np.sqrt(s2sq)

    v = np.column_stack([r1 - m1, r2 - m2, r1 ** 2 - g1, r2 ** 2 - g2])
    Psi = v.T @ v / T
    for l in range(1, L + 1):
        w = 1.0 - l / (L + 1.0)
        G = v[l:].T @ v[:-l] / T
        Psi += w * (G + G.T)

    grad = np.array([g1 / s1sq ** 1.5, -g2 / s2sq ** 1.5,
                     -m1 / (2 * s1sq ** 1.5), m2 / (2 * s2sq ** 1.5)])
    return float(grad @ Psi @ grad)


def joint_block_variance(R: np.ndarray, i: int, j: int, block: int) -> float:
    """Per-observation variance from resampling common time blocks.

    R is T x K: the same resampled block indices are applied to every column,
    so each draw keeps the cross-section of a given day together and only the
    ordering of days is resampled.
    """
    T = R.shape[0]
    nb = int(np.ceil(T / block))
    starts = RNG.integers(0, T, size=(NBOOT, nb))
    idx = ((starts[:, :, None] + np.arange(block)[None, None, :]) % T)
    idx = idx.reshape(NBOOT, -1)[:, :T]

    A, B = R[idx, i], R[idx, j]
    sa = A.mean(1) / A.std(1, ddof=1)
    sb = B.mean(1) / B.std(1, ddof=1)
    d = sa - sb
    d = d[np.isfinite(d)]
    return float(T * d.var(ddof=1))


def main() -> None:
    pd.set_option("display.width", 260, "display.max_columns", 40)
    book = daily_model_returns("S15")
    models = list(book.columns)
    R = book.to_numpy(float)
    T = R.shape[0]
    print(f"Season 1.5: {T} daily observations, {len(models)} models, "
          f"{len(models) * (len(models) - 1) // 2} pairs\n")

    rows = []
    for i, j in itertools.combinations(range(len(models)), 2):
        r1, r2 = R[:, i], R[:, j]
        s1 = r1.mean() / r1.std(ddof=1)
        s2 = r2.mean() / r2.std(ddof=1)
        rec = {
            "model_k": models[i], "model_l": models[j],
            "sharpe_k_ann": np.sqrt(PERIODS) * s1,
            "sharpe_l_ann": np.sqrt(PERIODS) * s2,
            "d_sharpe_ann": np.sqrt(PERIODS) * (s1 - s2),
            "corr_daily": float(np.corrcoef(r1, r2)[0, 1]),
        }
        for L in BANDWIDTHS:
            V = lw_variance(r1, r2, L)
            rec[f"V_hac{L}"] = V
            rec[f"Tyears_hac{L}"] = Z2 * V          # for delta = 1
            rec[f"mindet_hac{L}"] = np.sqrt(Z2) * np.sqrt(PERIODS * V / T)
        for b in BLOCKS:
            V = joint_block_variance(R, i, j, b)
            rec[f"V_blk{b}"] = V
            rec[f"Tyears_blk{b}"] = Z2 * V
            rec[f"mindet_blk{b}"] = np.sqrt(Z2) * np.sqrt(PERIODS * V / T)
        rows.append(rec)

    d = pd.DataFrame(rows)
    d.to_csv(os.path.join(DER, "s1_sharpe_horizon.csv"), index=False)

    cols = [f"Tyears_hac{L}" for L in BANDWIDTHS] + \
           [f"Tyears_blk{b}" for b in BLOCKS]
    print("=== years needed for an annualised Sharpe gap of 1 "
          "(5% two-sided, 80% power) ===\n")
    print(f"{'estimator':<22}{'median':>9}{'q25':>9}{'q75':>9}{'min':>9}{'max':>9}")
    for c in cols:
        v = d[c].dropna()
        lab = c.replace("Tyears_hac", "HAC bandwidth ").replace(
            "Tyears_blk", "block bootstrap b=")
        print(f"  {lab:<20}{v.median():>9.1f}{v.quantile(.25):>9.1f}"
              f"{v.quantile(.75):>9.1f}{v.min():>9.1f}{v.max():>9.1f}")

    mcols = [f"mindet_hac{L}" for L in BANDWIDTHS] + \
            [f"mindet_blk{b}" for b in BLOCKS]
    md = d[mcols].median()
    print(f"\nsmallest annualised Sharpe gap detectable at T = {T} days: "
          f"median over pairs {md.min():.1f} to {md.max():.1f} across estimators")

    # the correlation is the assumption the answer turns on
    print(f"\npair daily return correlation: median {d['corr_daily'].median():.2f}, "
          f"range {d['corr_daily'].min():.2f} to {d['corr_daily'].max():.2f}")
    lo_c = d[d["corr_daily"] < d["corr_daily"].median()]["Tyears_hac1"].median()
    hi_c = d[d["corr_daily"] >= d["corr_daily"].median()]["Tyears_hac1"].median()
    print(f"  median horizon at HAC(1): {lo_c:.1f} years for the less "
          f"correlated half of pairs, {hi_c:.1f} for the more correlated half")

    summary = {
        "T_days": int(T), "n_models": len(models), "n_pairs": int(len(d)),
        "periods_per_year": PERIODS, "z2": Z2, "nboot": NBOOT,
        "horizon": {c: {"median": float(d[c].median()),
                        "q25": float(d[c].quantile(.25)),
                        "q75": float(d[c].quantile(.75)),
                        "min": float(d[c].min()), "max": float(d[c].max())}
                    for c in cols},
        "horizon_all_median_lo": float(min(d[c].median() for c in cols)),
        "horizon_all_median_hi": float(max(d[c].median() for c in cols)),
        "mindet_median_lo": float(md.min()), "mindet_median_hi": float(md.max()),
        "corr_median": float(d["corr_daily"].median()),
        "corr_lo": float(d["corr_daily"].min()),
        "corr_hi": float(d["corr_daily"].max()),
        "horizon_lowcorr_half": float(lo_c), "horizon_highcorr_half": float(hi_c),
    }
    with open(os.path.join(DER, "s1_sharpe_horizon.json"), "w") as fh:
        json.dump(summary, fh, indent=1)


if __name__ == "__main__":
    main()
