"""Check 1: is the implied rho_m > 1 evidence against the note's model, or is it
what the estimator does at T = 13, R = 4, K = 8?

Simulates *under* the note's model, so the model is true by construction, then
applies exactly the estimator used in item 2 and counts how many of the 28 pairs
come back with an inadmissible rho_m > 1.

Data-generating process (note eq. 1), sigma^2 = 1 without loss of generality:
    omega^2 = iota, tau^2 = 1 - iota
    m[k,t]  = omega * ( sqrt(rho_m) f[t] + sqrt(1-rho_m) z[k,t] )   -> equicorrelated
    e[k,r,t] = tau * u[k,r,t]                                        -> iid
with f, z, u unit-variance iid Gaussian, or Student-t(4) rescaled by sqrt(2) to
unit variance.

The estimator is the bias-corrected one of item 2:
    tau^2_hat   = mean over days of the between-replicate variance
    omega^2_hat = Var_t(xbar) - tau^2_hat / R      (unbiased for omega^2)
    rho_m_hat   = Cov_t(xbar_k, xbar_l) / (omega_hat_k omega_hat_l)
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import prov
import variance_components as vc

DER = os.path.join(prov.ROOT, "data", "derived")
NSIM = 4000
OBSERVED_COUNT = 11      # 11 of 28 pairs, daily, arm effects removed
OBSERVED_COUNT_POOLED = 13
OBSERVED_4H = 15


def draw(rng: np.random.Generator, shape, dist: str) -> np.ndarray:
    if dist == "gaussian":
        return rng.standard_normal(shape)
    if dist == "t4":
        return rng.standard_t(4, size=shape) / np.sqrt(2.0)  # unit variance
    raise ValueError(dist)


def simulate(rng, K, R, T, iota, rho, dist, sigma=None) -> np.ndarray:
    """One panel under the note's model. sigma: optional per-model sd (K,)."""
    s = np.ones(K) if sigma is None else np.asarray(sigma, float)
    om = s * np.sqrt(iota)
    tau = s * np.sqrt(1.0 - iota)
    f = draw(rng, T, dist)
    z = draw(rng, (K, T), dist)
    m = om[:, None] * (np.sqrt(rho) * f[None, :] + np.sqrt(1 - rho) * z)
    e = tau[:, None, None] * draw(rng, (K, R, T), dist)
    return m[:, None, :] + e


def run_cell(K, R, T, iota, rho, dist, sigma, nsim, seed) -> dict:
    rng = np.random.default_rng(seed)
    iu = np.triu_indices(K, 1)
    counts = np.empty(nsim, dtype=int)
    iota_hat = np.empty((nsim, K))
    rho_med = np.empty(nsim)
    neg_omega = np.empty(nsim, dtype=int)
    for i in range(nsim):
        X = simulate(rng, K, R, T, iota, rho, dist, sigma)
        c = vc.components(X)
        raw = c["rho_raw"][iu]
        raw = raw[~np.isnan(raw)]
        counts[i] = int((raw > 1).sum())
        rho_med[i] = np.median(raw) if len(raw) else np.nan
        iota_hat[i] = c["iota"]
        neg_omega[i] = int((c["omega2"] < 0).sum())
    return {
        "iota_true": iota,
        "rho_true": rho,
        "dist": dist,
        "sigma": "equal" if sigma is None else "observed spread",
        "mean_count_gt1": counts.mean(),
        "median_count_gt1": float(np.median(counts)),
        "q05_count": float(np.percentile(counts, 5)),
        "q95_count": float(np.percentile(counts, 95)),
        "P_count_ge_11": float((counts >= OBSERVED_COUNT).mean()),
        "P_count_ge_13": float((counts >= OBSERVED_COUNT_POOLED).mean()),
        "P_count_ge_15": float((counts >= OBSERVED_4H).mean()),
        "P_any_gt1": float((counts > 0).mean()),
        "median_rho_hat": float(np.nanmedian(rho_med)),
        "mean_iota_hat": float(np.nanmean(iota_hat)),
        "iota_bias": float(np.nanmean(iota_hat) - iota),
        "mean_n_omega2_negative": float(neg_omega.mean()),
        "_counts": counts,
    }


def main() -> None:
    pd.set_option("display.width", 250, "display.max_columns", 40)
    K, R, T = 8, 4, 13

    # observed per-model sigma (daily, arm effects removed) for the extra row
    X0, models, comps, Tobs = vc.panel("daily")
    cobs = vc.components(vc.adjust(X0, "arm_day"))
    sig_obs = np.sqrt(cobs["sigma2"])
    sig_obs = sig_obs / sig_obs.mean()  # scale-free shape only

    rows, counts_store = [], {}
    seed = 70001
    for dist in ["gaussian", "t4"]:
        for iota in [0.3, 0.5, 0.7]:
            for rho in [0.5, 0.8, 0.95]:
                r = run_cell(K, R, T, iota, rho, dist, None, NSIM, seed)
                seed += 1
                counts_store[f"{dist}_i{iota}_r{rho}"] = r.pop("_counts")
                rows.append(r)
    # sensitivity: the observed spread of per-model sigma, at the rho the data suggest
    for dist in ["gaussian", "t4"]:
        r = run_cell(K, R, T, 0.5, 0.95, dist, sig_obs, NSIM, seed)
        seed += 1
        counts_store[f"{dist}_i0.5_r0.95_obs_sigma"] = r.pop("_counts")
        rows.append(r)

    res = pd.DataFrame(rows)
    res.to_csv(os.path.join(DER, "c1_identification.csv"), index=False)

    print(f"=== C1 parametric bootstrap under the note's model "
          f"(K={K}, R={R}, T={T}, {NSIM:,} sims per cell) ===\n")
    print(
        res[["dist", "sigma", "iota_true", "rho_true", "mean_count_gt1",
             "median_count_gt1", "q05_count", "q95_count", "P_count_ge_11",
             "median_rho_hat", "mean_iota_hat", "iota_bias"]]
        .to_string(index=False, float_format=lambda x: f"{x:,.3f}")
    )

    allc = np.concatenate(list(counts_store.values()))
    print(f"\nPooled over all {len(counts_store)} cells:")
    print(f"  mean inadmissible pairs out of 28: {allc.mean():.2f}")
    print(f"  distribution: 5% {np.percentile(allc,5):.0f}, 25% {np.percentile(allc,25):.0f}, "
          f"50% {np.percentile(allc,50):.0f}, 75% {np.percentile(allc,75):.0f}, "
          f"95% {np.percentile(allc,95):.0f}, max {allc.max()}")
    print(f"  P(count >= 11, the observed daily arm-adjusted value) = {(allc>=11).mean():.3f}")
    print(f"  P(count >= 13, the observed pooled value)             = {(allc>=13).mean():.3f}")
    print(f"  P(count >=  1)                                        = {(allc>0).mean():.3f}")

    hist = np.bincount(allc, minlength=29)[:29]
    print("\n  count out of 28 :  " + " ".join(f"{i:>4d}" for i in range(0, 29, 2)))
    print("  share of sims   :  " + " ".join(
        f"{hist[i]/len(allc):>4.2f}" for i in range(0, 29, 2)))

    with open(os.path.join(DER, "c1_identification.json"), "w") as fh:
        json.dump(
            {
                "nsim_per_cell": NSIM,
                "K": K, "R": R, "T": T,
                "observed_daily_arm_adjusted": OBSERVED_COUNT,
                "observed_daily_pooled": OBSERVED_COUNT_POOLED,
                "observed_4h_arm_adjusted": OBSERVED_4H,
                "pooled_mean_count": float(allc.mean()),
                "pooled_P_ge_11": float((allc >= 11).mean()),
                "pooled_P_ge_13": float((allc >= 13).mean()),
                "pooled_quantiles": {
                    q: float(np.percentile(allc, q)) for q in [5, 25, 50, 75, 95]
                },
                "per_cell": res.to_dict("records"),
            },
            fh,
            indent=1,
            default=float,
        )


if __name__ == "__main__":
    main()
