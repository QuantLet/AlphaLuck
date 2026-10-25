"""Referee item 4: serial dependence and the nine-year headline.

Section 11 quoted T(R=1) ~ 9 years for a Sharpe gap of 1, computed from the
*iid* variance of daily return differences. Positions persist, so Remark 1 of
alphaluck_note.tex applies: A and B must be replaced by long-run variances. This
recomputes the horizon with

    T_years = z^2 * LRV_diff / (delta^2 * sigmabar^2),     z^2 = 7.8489

which is frequency-invariant in form, because T_periods = z^2 LRV / Delta^2 and
Delta^2 = delta^2 sigma^2 / P with P periods per year, so the P cancels. Only the
variance of the *difference* is replaced by its long-run counterpart: sigmabar^2
stays the ordinary per-period variance, since that is what defines the Sharpe
ratio the effect size delta is expressed in.

LRV estimators, all applied to the single-instance difference series
x[k,r,t] - x[l,r',t] averaged over replicate pairs r != r':
    iid            the plain sample variance (what section 11 used)
    Newey-West     Bartlett kernel at lags 1, 2, 3
    block boot     T * Var(bootstrap distribution of the sample mean),
                   moving blocks of 2 and 3 days, 4,000 draws

Run at daily and 4-hour frequency. The autocorrelation of the difference series
is reported at lags 1-3 across the 28 pairs, since that is what drives any gap
between the iid and long-run numbers.
"""
from __future__ import annotations

import itertools
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import prov
import variance_components as vc

DER = os.path.join(prov.ROOT, "data", "derived")
RNG = np.random.default_rng(20261018)
NBOOT = 4000
Z2 = 7.8489          # (z_0.975 + z_0.80)^2
DELTA = 1.0          # annualised Sharpe gap


def nw_lrv(d: np.ndarray, L: int) -> float:
    """Newey-West / Bartlett long-run variance at lag L."""
    T = len(d)
    x = d - d.mean()
    g0 = float(x @ x / T)
    lrv = g0
    for l in range(1, L + 1):
        gl = float(x[l:] @ x[:-l] / T)
        lrv += 2 * (1 - l / (L + 1)) * gl
    return max(lrv, 1e-18)


def block_lrv(d: np.ndarray, block: int, nboot: int = NBOOT) -> float:
    """T * Var(moving-block bootstrap distribution of the sample mean)."""
    T = len(d)
    nb = int(np.ceil(T / block))
    starts = RNG.integers(0, T, size=(nboot, nb))
    off = np.arange(block)
    idx = ((starts[:, :, None] + off[None, None, :]) % T).reshape(nboot, -1)[:, :T]
    means = d[idx].mean(axis=1)
    return max(float(T * means.var(ddof=1)), 1e-18)


def acf(d: np.ndarray, L: int) -> float:
    x = d - d.mean()
    denom = float(x @ x)
    return float(x[L:] @ x[:-L] / denom) if denom > 0 else np.nan


def pair_series(X: np.ndarray, k: int, l: int) -> list[np.ndarray]:
    """Single-instance difference series over replicate pairs r != r'."""
    R = X.shape[1]
    return [X[k, r, :] - X[l, r2, :] for r in range(R) for r2 in range(R) if r != r2]


def main() -> None:
    pd.set_option("display.width", 280, "display.max_columns", 40)
    rows, ac_rows = [], []

    for freq in ["daily", "4h"]:
        X0, models, comps, T = vc.panel(freq)
        for variant in ["pooled", "arm_day"]:
            X = vc.adjust(X0, variant)
            K = X.shape[0]
            sig2 = X.reshape(K, -1).var(axis=1, ddof=1)      # per-model variance
            per_method: dict[str, list[float]] = {}
            acc: dict[int, list[float]] = {1: [], 2: [], 3: []}

            for k, l in itertools.combinations(range(K), 2):
                series = pair_series(X, k, l)
                sbar = (sig2[k] + sig2[l]) / 2
                est = {
                    "iid": np.mean([np.var(d, ddof=1) for d in series]),
                    "NW lag 1": np.mean([nw_lrv(d, 1) for d in series]),
                    "NW lag 2": np.mean([nw_lrv(d, 2) for d in series]),
                    "NW lag 3": np.mean([nw_lrv(d, 3) for d in series]),
                    "block 2": np.mean([block_lrv(d, 2) for d in series]),
                    "block 3": np.mean([block_lrv(d, 3) for d in series]),
                }
                for m, v in est.items():
                    per_method.setdefault(m, []).append(
                        Z2 * v / (DELTA**2 * sbar)
                    )
                for L in (1, 2, 3):
                    acc[L].append(float(np.mean([acf(d, L) for d in series])))

            for m, vals in per_method.items():
                v = np.array(vals)
                rows.append(
                    {
                        "frequency": freq,
                        "variant": variant,
                        "lrv_method": m,
                        "T_years_median": float(np.median(v)),
                        "T_years_q25": float(np.percentile(v, 25)),
                        "T_years_q75": float(np.percentile(v, 75)),
                        "T_years_min": float(v.min()),
                        "T_years_max": float(v.max()),
                        "ratio_to_iid": float(
                            np.median(v) / np.median(per_method["iid"])
                        ),
                    }
                )
            ac_rows.append(
                {
                    "frequency": freq,
                    "variant": variant,
                    **{f"acf_lag{L}_mean": float(np.mean(acc[L])) for L in (1, 2, 3)},
                    **{f"acf_lag{L}_median": float(np.median(acc[L])) for L in (1, 2, 3)},
                    **{f"acf_lag{L}_min": float(np.min(acc[L])) for L in (1, 2, 3)},
                    **{f"acf_lag{L}_max": float(np.max(acc[L])) for L in (1, 2, 3)},
                    "n_pairs": len(acc[1]),
                }
            )

    res = pd.DataFrame(rows)
    res.to_csv(os.path.join(DER, "r4_horizon.csv"), index=False)
    ac = pd.DataFrame(ac_rows)
    ac.to_csv(os.path.join(DER, "r4_autocorr.csv"), index=False)

    print("=== R4 required horizon for a Sharpe gap of 1 at R = 1, in years ===\n")
    print(res.to_string(index=False, float_format=lambda x: f"{x:,.3f}"))
    print("\n=== R4 autocorrelation of the difference series, across 28 pairs ===\n")
    print(
        ac[["frequency", "variant", "acf_lag1_mean", "acf_lag2_mean",
            "acf_lag3_mean", "acf_lag1_min", "acf_lag1_max"]]
        .to_string(index=False, float_format=lambda x: f"{x:,.4f}")
    )

    d = res[res["frequency"] == "daily"]
    print(f"\ndaily, across all variants and LRV methods: "
          f"{d['T_years_median'].min():.1f} to {d['T_years_median'].max():.1f} years")
    allr = res["T_years_median"]
    print(f"all frequencies and methods: {allr.min():.1f} to {allr.max():.1f} years")

    with open(os.path.join(DER, "r4_horizon.json"), "w") as fh:
        json.dump({"rows": rows, "autocorr": ac_rows, "z2": Z2, "delta": DELTA,
                   "range_daily": [float(d["T_years_median"].min()),
                                   float(d["T_years_median"].max())],
                   "range_all": [float(allr.min()), float(allr.max())]},
                  fh, indent=1, default=float)


if __name__ == "__main__":
    main()
