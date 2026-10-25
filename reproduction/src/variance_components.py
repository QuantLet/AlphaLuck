"""Items 2 and 3: daily variance components of alphaluck_note.tex, and the
design numbers they imply.

Model (note eq. 1):
    x[k,r,t] = mu_k + m[k,t] + e[k,r,t]
with the four Season-1.5 competitions standing in for replicates r.

Estimators (note section 6):
    tau_k^2   = mean over days of the between-replicate variance within a day
    omega_k^2 = Var_t( xbar_{k,t} ) - tau_k^2 / R
    iota_k    = omega_k^2 / (omega_k^2 + tau_k^2)
    rho^m_kl  = Cov_t( xbar_k , xbar_l ) / (omega_k * omega_l)
    A_kl      = omega_k^2 + omega_l^2 - 2 rho^m_kl omega_k omega_l
    B_kl      = tau_k^2 + tau_l^2

Three variants, because item 1 established the arms are *not* exchangeable:
    pooled        raw returns; arm differences are charged to e, so tau is
                  inflated and iota biased down
    arm-level     a constant per-arm mean removed
    arm x day     the arm's common daily deviation removed, keeping the overall
                  day mean so the market path m is preserved:
                      x~[k,r,t] = x[k,r,t] - mean_k x[k,r,t] + mean_{k,r} x[k,r,t]

Intervals: moving-block bootstrap over days (block 3) combined with an iid
resample of the four competitions, 10,000 draws. With R = 4 and T = 13 these are
wide, and the competition resample is coarse by construction -- duplicated arms
shrink the within-day spread -- so a delete-one-arm jackknife range for iota is
reported alongside.
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
RNG = np.random.default_rng(20261009)
NBOOT = 10000
BLOCK = 3
Z = stats.norm.ppf(0.975) + stats.norm.ppf(0.80)  # 2.8016
TRADING_DAYS_PER_YEAR = 252  # the note's convention, so tables are comparable


# --------------------------------------------------------------------- panels
def panel(freq: str = "daily") -> tuple[np.ndarray, list[str], list[int], int]:
    """Return X of shape (K models, R competitions, T periods)."""
    fills = pd.read_parquet(os.path.join(DER, "fills.parquet"))
    eq = pd.read_parquet(os.path.join(DER, "equity.parquet"))
    lo, hi = analyse.common_window(fills, "S15")
    s15 = eq[(eq["season"] == "S15") & (eq["t"] >= lo) & (eq["t"] <= hi)]

    step = 86400_000 if freq == "daily" else 4 * 3600_000
    ser = {}
    for tag, g in s15.groupby("tag"):
        s = g.sort_values("t").set_index("t")["equity"]
        b = s.groupby(s.index // step).last()
        ser[tag] = b.pct_change().dropna()

    idx = None
    for v in ser.values():
        idx = v.index if idx is None else idx.intersection(v.index)

    meta = s15.groupby("tag")[["model", "competition_id"]].first()
    models = sorted(meta["model"].unique())
    comps = sorted(meta["competition_id"].unique())
    X = np.full((len(models), len(comps), len(idx)), np.nan)
    for tag, v in ser.items():
        k = models.index(meta.loc[tag, "model"])
        r = comps.index(meta.loc[tag, "competition_id"])
        X[k, r, :] = v.reindex(idx).to_numpy()
    if np.isnan(X).any():
        raise SystemExit("incomplete panel")
    return X, models, comps, len(idx)


def adjust(X: np.ndarray, how: str) -> np.ndarray:
    if how == "pooled":
        return X
    if how == "arm_level":
        # remove a constant per-arm mean, keep the grand mean
        return X - X.mean(axis=(0, 2), keepdims=True) + X.mean()
    if how == "arm_day":
        # remove the arm's common daily deviation, keep the overall day mean
        return X - X.mean(axis=0, keepdims=True) + X.mean(axis=(0, 1), keepdims=True)
    raise ValueError(how)


# ---------------------------------------------------------------- estimators
def components(X: np.ndarray) -> dict:
    """tau^2, omega^2, iota per model; rho^m, A, B per pair."""
    K, R, T = X.shape
    xbar = X.mean(axis=1)                       # (K, T) replicate mean per day
    within = X.var(axis=1, ddof=1)              # (K, T) between-replicate var
    tau2 = within.mean(axis=1)                  # (K,)
    var_xbar = xbar.var(axis=1, ddof=1)         # (K,)
    omega2 = var_xbar - tau2 / R
    omega2_tr = np.maximum(omega2, 0.0)         # truncated for ratios
    sigma2 = omega2_tr + tau2
    iota = np.where(sigma2 > 0, omega2_tr / sigma2, np.nan)

    C = np.cov(xbar, ddof=1)                    # (K, K) over days
    om = np.sqrt(omega2_tr)
    rho = np.full((K, K), np.nan)
    rho_raw = np.full((K, K), np.nan)
    for k in range(K):
        for l in range(K):
            if k != l and om[k] > 0 and om[l] > 0:
                rho_raw[k, l] = C[k, l] / (om[k] * om[l])
                rho[k, l] = np.clip(rho_raw[k, l], -1, 1)
    A = np.full((K, K), np.nan)
    B = np.full((K, K), np.nan)
    for k in range(K):
        for l in range(K):
            if k != l:
                A[k, l] = omega2_tr[k] + omega2_tr[l] - 2 * rho[k, l] * om[k] * om[l]
                B[k, l] = tau2[k] + tau2[l]
    return {
        "tau2": tau2,
        "omega2": omega2,
        "omega2_tr": omega2_tr,
        "iota": iota,
        "rho": rho,
        "A": A,
        "B": B,
        "rho_raw": rho_raw,
        "mu": X.mean(axis=(1, 2)),
        "sigma2": sigma2,
        # single-instance pairwise difference variance, estimated directly with
        # no decomposition: this is A + B and it anchors T(R=1)
        "var_diff_single": _var_diff_single(X),
    }


def _var_diff_single(X: np.ndarray) -> np.ndarray:
    """Var_t( x[k,r,t] - x[l,r',t] ) averaged over replicate pairs r != r'.

    Needs no variance decomposition, so it is well determined even where the
    two-component split is not. Under the note's model it equals A + B.
    Vectorised through the (K*R) covariance matrix:
        Var(Z_i - Z_j) = C_ii + C_jj - 2 C_ij.
    """
    K, R, T = X.shape
    Z = X.reshape(K * R, T)
    C = np.cov(Z, ddof=1)
    d = np.diag(C)
    V = d[:, None] + d[None, :] - 2 * C          # (KR, KR) difference variances
    V = V.reshape(K, R, K, R)
    # average over r != r' only
    mask = ~np.eye(R, dtype=bool)
    out = (V * mask[None, :, None, :]).sum(axis=(1, 3)) / mask.sum()
    np.fill_diagonal(out, np.nan)
    return out


def block_days(T: int, block: int, n: int) -> np.ndarray:
    nb = int(np.ceil(T / block))
    starts = RNG.integers(0, T, size=(n, nb))
    off = np.arange(block)
    return ((starts[:, :, None] + off[None, None, :]) % T).reshape(n, -1)[:, :T]


def bootstrap(X: np.ndarray, how: str, nboot: int = NBOOT) -> dict:
    """Blocks over days x iid resample of competitions."""
    K, R, T = X.shape
    days = block_days(T, BLOCK, nboot)
    keep = {"tau2": [], "omega2": [], "iota": [], "rho": [], "A": [], "B": [],
            "BA": [], "var_diff_single": []}
    for b in range(nboot):
        comp = RNG.integers(0, R, R)
        Xb = adjust(X[:, comp, :][:, :, days[b]], how)
        c = components(Xb)
        keep["tau2"].append(c["tau2"])
        keep["omega2"].append(c["omega2"])
        keep["iota"].append(c["iota"])
        keep["rho"].append(c["rho"])
        keep["A"].append(c["A"])
        keep["B"].append(c["B"])
        keep["var_diff_single"].append(c["var_diff_single"])
        with np.errstate(divide="ignore", invalid="ignore"):
            keep["BA"].append(np.where(c["A"] > 0, c["B"] / c["A"], np.nan))
    return {k: np.array(v) for k, v in keep.items()}


def ci(arr: np.ndarray, axis: int = 0) -> tuple[np.ndarray, np.ndarray]:
    return (
        np.nanpercentile(arr, 2.5, axis=axis),
        np.nanpercentile(arr, 97.5, axis=axis),
    )


def jackknife_iota(X: np.ndarray, how: str) -> np.ndarray:
    """Delete-one-arm range for iota (R=4 -> 4 subsamples of 3)."""
    R = X.shape[1]
    out = []
    for drop in range(R):
        keep = [r for r in range(R) if r != drop]
        out.append(components(adjust(X[:, keep, :], how))["iota"])
    return np.array(out)


# ------------------------------------------------------------------ item 3
def t_years(iota: float, rho_m: float, delta: float, R: float) -> float:
    """Note eq. (14): years to detect an annualised Sharpe gap delta."""
    bracket = iota * (1 - rho_m) + (0.0 if np.isinf(R) else (1 - iota) / R)
    return 2 * Z**2 / delta**2 * bracket


def r_for_eps(iota: float, rho_m: float, eps: float = 0.10) -> float:
    """Note cor. 2: replicates needed to sit within (1+eps) of the floor."""
    den = eps * iota * (1 - rho_m)
    return np.inf if den <= 0 else (1 - iota) / den


def main() -> None:
    pd.set_option("display.width", 250, "display.max_columns", 60)
    report: dict = {}

    for freq in ["daily", "4h"]:
        X0, models, comps, T = panel(freq)
        K, R = len(models), len(comps)
        print(f"\n{'='*78}\n{freq.upper()}  K={K} models, R={R} competitions, T={T} periods\n{'='*78}")
        report[freq] = {"K": K, "R": R, "T": T}

        for how in ["pooled", "arm_level", "arm_day"]:
            X = adjust(X0, how)
            c = components(X)
            bs = bootstrap(X0, how)

            lo_t, hi_t = ci(bs["tau2"])
            lo_o, hi_o = ci(bs["omega2"])
            lo_i, hi_i = ci(bs["iota"])
            jk = jackknife_iota(X0, how)

            per = pd.DataFrame(
                {
                    "model": models,
                    "mean_daily_pct": 100 * c["mu"],
                    "tau2": c["tau2"],
                    "tau_pct": 100 * np.sqrt(c["tau2"]),
                    "tau2_lo": lo_t,
                    "tau2_hi": hi_t,
                    "omega2": c["omega2"],
                    "omega_pct": 100 * np.sqrt(c["omega2_tr"]),
                    "omega2_lo": lo_o,
                    "omega2_hi": hi_o,
                    "iota": c["iota"],
                    "iota_lo": lo_i,
                    "iota_hi": hi_i,
                    "iota_jk_min": jk.min(axis=0),
                    "iota_jk_max": jk.max(axis=0),
                    "omega2_negative": c["omega2"] < 0,
                }
            )
            per.to_csv(os.path.join(DER, f"i2_components_{freq}_{how}.csv"), index=False)
            print(f"\n--- per model [{freq}, {how}] ---")
            print(
                per[
                    ["model", "mean_daily_pct", "tau_pct", "omega_pct", "iota",
                     "iota_lo", "iota_hi", "iota_jk_min", "iota_jk_max", "omega2_negative"]
                ].to_string(index=False, float_format=lambda x: f"{x:,.3f}")
            )

            # pairwise
            rows = []
            for k in range(K):
                for l in range(k + 1, K):
                    ba = c["B"][k, l] / c["A"][k, l] if c["A"][k, l] > 0 else np.inf
                    rows.append(
                        {
                            "a": models[k],
                            "b": models[l],
                            "rho_m": c["rho"][k, l],
                            "rho_m_lo": np.nanpercentile(bs["rho"][:, k, l], 2.5),
                            "rho_m_hi": np.nanpercentile(bs["rho"][:, k, l], 97.5),
                            "A": c["A"][k, l],
                            "A_lo": np.nanpercentile(bs["A"][:, k, l], 2.5),
                            "A_hi": np.nanpercentile(bs["A"][:, k, l], 97.5),
                            "B": c["B"][k, l],
                            "B_lo": np.nanpercentile(bs["B"][:, k, l], 2.5),
                            "B_hi": np.nanpercentile(bs["B"][:, k, l], 97.5),
                            "B_over_A": ba,
                            "BA_lo": np.nanpercentile(bs["BA"][:, k, l], 2.5),
                            "BA_hi": np.nanpercentile(bs["BA"][:, k, l], 97.5),
                        }
                    )
            pw = pd.DataFrame(rows)
            pw.to_csv(os.path.join(DER, f"i2_pairs_{freq}_{how}.csv"), index=False)
            print(f"\n--- pairwise summary [{freq}, {how}], 28 pairs ---")
            print(
                pw[["rho_m", "A", "B", "B_over_A"]]
                .describe()
                .loc[["mean", "50%", "min", "max"]]
                .to_string(float_format=lambda x: f"{x:,.4f}")
            )

            raw = c["rho_raw"][np.triu_indices(K, 1)]
            raw = raw[~np.isnan(raw)]
            n_inadm = int((raw > 1).sum())
            print(f"    rho^m admissibility [{freq}, {how}]: "
                  f"{n_inadm}/{len(raw)} pairs have an implied rho^m > 1 "
                  f"(max {raw.max():.3f}); median raw {np.median(raw):.3f}")

            report[freq][how] = {
                "n_pairs": int(len(raw)),
                "n_rho_inadmissible": n_inadm,
                "rho_raw_median": float(np.median(raw)),
                "rho_raw_max": float(raw.max()),
                "median_var_diff_single": float(
                    np.nanmedian(c["var_diff_single"][np.triu_indices(K, 1)])
                ),
                "median_sigma2": float(np.median(c["sigma2"])),
                "median_iota": float(np.nanmedian(c["iota"])),
                "iota_ci": [float(np.nanmedian(lo_i)), float(np.nanmedian(hi_i))],
                "median_rho_m": float(np.nanmedian(pw["rho_m"])),
                "rho_m_ci": [
                    float(np.nanmedian(pw["rho_m_lo"])),
                    float(np.nanmedian(pw["rho_m_hi"])),
                ],
                "median_B_over_A": float(np.nanmedian(pw["B_over_A"])),
                "n_omega2_negative": int((c["omega2"] < 0).sum()),
            }

    with open(os.path.join(DER, "i2_summary.json"), "w") as fh:
        json.dump(report, fh, indent=1)

    # ------------------------------------------------------------- item 3
    print(f"\n{'='*78}\nITEM 3  implied design numbers\n{'='*78}")
    print(
        "T_years(R) = z^2 (A + B/R) / (delta^2 sigma_bar^2), per pair, median over\n"
        "the 28 pairs; 'year' = 252 trading days, the note's convention. The\n"
        "R=1 column is also computed directly from Var(x_k,r,t - x_l,r',t), which\n"
        "needs no variance decomposition and so is the one robust anchor.\n"
    )
    rows = []
    for freq in ["daily", "4h"]:
        X0, models, comps, T = panel(freq)
        K = len(models)
        iu = np.triu_indices(K, 1)
        for how in ["pooled", "arm_day"]:
            X = adjust(X0, how)
            c = components(X)
            bs = bootstrap(X0, how, nboot=2000)
            sig = c["sigma2"]
            sbar = (sig[:, None] + sig[None, :]) / 2
            A, B, VD = c["A"], c["B"], c["var_diff_single"]
            for delta in [0.5, 1.0, 2.0]:
                row = {"freq": freq, "variant": how, "delta": delta}
                for R in [1, 4, 20, 100, np.inf]:
                    add = 0.0 if np.isinf(R) else 1.0 / R
                    ty = Z**2 * (A + B * add) / (delta**2 * sbar)
                    lab = f"T_years_R{int(R) if np.isfinite(R) else 'inf'}"
                    row[lab] = float(np.nanmedian(ty[iu]))
                    btv = Z**2 * (bs["A"] + bs["B"] * add) / (delta**2 * sbar[None])
                    med = np.nanmedian(btv[:, iu[0], iu[1]], axis=1)
                    row[lab + "_lo"] = float(np.nanpercentile(med, 2.5))
                    row[lab + "_hi"] = float(np.nanpercentile(med, 97.5))
                # robust, decomposition-free anchor for R = 1
                ty1 = Z**2 * VD / (delta**2 * sbar)
                row["T_years_R1_direct"] = float(np.nanmedian(ty1[iu]))
                bt1 = Z**2 * bs["var_diff_single"] / (delta**2 * sbar[None])
                med1 = np.nanmedian(bt1[:, iu[0], iu[1]], axis=1)
                row["T_years_R1_direct_lo"] = float(np.nanpercentile(med1, 2.5))
                row["T_years_R1_direct_hi"] = float(np.nanpercentile(med1, 97.5))
                # replicate threshold, per pair (note cor. 2): R >= B/(eps A)
                with np.errstate(divide="ignore", invalid="ignore"):
                    reps = np.where(A > 0, B / (0.10 * A), np.inf)
                row["R_within_10pct_median"] = float(np.nanmedian(reps[iu]))
                row["R_within_10pct_q25"] = float(np.nanpercentile(reps[iu], 25))
                row["R_within_10pct_q75"] = float(np.nanpercentile(reps[iu], 75))
                rows.append(row)
    t3 = pd.DataFrame(rows)
    t3.to_csv(os.path.join(DER, "i3_design.csv"), index=False)
    cols = ["freq", "variant", "delta", "T_years_R1", "T_years_R1_direct",
            "T_years_R4", "T_years_R20", "T_years_R100", "T_years_Rinf",
            "R_within_10pct_median"]
    print(t3[cols].to_string(index=False, float_format=lambda x: f"{x:,.2f}"))

    print("\n--- with 95% bootstrap intervals (daily) ---")
    d = t3[t3["freq"] == "daily"]
    for r in d.itertuples():
        print(f"  {r.variant:<8} delta={r.delta}:  "
              f"R=1 {r.T_years_R1:6.2f} [{r.T_years_R1_lo:.2f}, {r.T_years_R1_hi:.2f}]   "
              f"R=4 {r.T_years_R4:6.2f} [{r.T_years_R4_lo:.2f}, {r.T_years_R4_hi:.2f}]   "
              f"R=inf {r.T_years_Rinf:6.2f} [{r.T_years_Rinf_lo:.2f}, {r.T_years_Rinf_hi:.2f}]")

    # note-standardised version, for comparability with the note's Table 1
    print("\n--- note-standardised form, eq.(14), from median iota and median rho^m ---")
    rows2 = []
    for freq in ["daily", "4h"]:
        for how in ["pooled", "arm_day"]:
            sm = report[freq][how]
            io, rm = sm["median_iota"], sm["median_rho_m"]
            for delta in [0.5, 1.0, 2.0]:
                rows2.append({
                    "freq": freq, "variant": how, "iota": io, "rho_m": rm,
                    "delta": delta,
                    **{f"T_years_R{R if np.isfinite(R) else 'inf'}":
                       t_years(io, rm, delta, R) for R in [1, 4, 20, 100, np.inf]},
                    "R_within_10pct_of_floor": r_for_eps(io, rm, 0.10),
                })
    t3b = pd.DataFrame(rows2)
    t3b.to_csv(os.path.join(DER, "i3_design_standardised.csv"), index=False)
    print(t3b.to_string(index=False, float_format=lambda x: f"{x:,.2f}"))


if __name__ == "__main__":
    main()
