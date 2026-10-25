"""Check 2: put the arms on a common scale, then redo the decomposition.

Arm 4 forces maximum leverage and arm 2 ("Monk Mode") restrains it, so most of
the measured spread between arms is a scale difference rather than a difference
in what the models decided. Two rescalings remove it:

    per_leverage  x[k,r,t] / L[k,r]      L = that wallet's mean gross leverage
    per_vol       x[k,r,t] / s[k,r]      s = that wallet's own daily sd

Both divisors vary by arm *within* a model, so they genuinely change the
decomposition rather than rescaling it: the replicate mean xbar is a weighted
average and tau^2 is recomputed on the rescaled series.

Reported for each scaling: the daily variance components (median iota, median
rho_m, how many of the 28 pairs stay inadmissible) and the final-return ANOVA
(one-way ICC, arm-fixed-effect ICC, model F). Arm 4 is then dropped as a
sensitivity check, leaving K=8, R=3.

Note on the vol-standardised ANOVA outcome: standardising each wallet's daily
returns by its own sd and summing gives T x daily Sharpe, so that ANOVA is the
Sharpe ANOVA up to a constant factor; its F statistics and variance shares are
identical. It is reported here and reused in check 3.
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
import variance_components as vc

DER = os.path.join(prov.ROOT, "data", "derived")


def scaled_panels():
    """X (K,R,T) daily returns under each scaling, plus labels."""
    X, models, comps, T = vc.panel("daily")
    met = pd.read_csv(os.path.join(DER, "i1_wallet_metrics.csv"))
    L = np.ones_like(X[:, :, 0])
    for r in met.itertuples():
        k = models.index(r.model)
        j = comps.index(r.competition_id)
        L[k, j] = r.mean_leverage
    S = X.std(axis=2, ddof=1)
    return {
        "raw": X,
        "per_leverage": X / L[:, :, None],
        "per_vol": X / S[:, :, None],
    }, models, comps, T, L, S


def anova(y: np.ndarray) -> dict:
    """Two-way (model, arm) with one observation per cell."""
    n, k = y.shape
    grand = y.mean()
    rm, cm = y.mean(axis=1), y.mean(axis=0)
    ss_model = k * ((rm - grand) ** 2).sum()
    ss_arm = n * ((cm - grand) ** 2).sum()
    ss_tot = ((y - grand) ** 2).sum()
    ss_within = ((y - rm[:, None]) ** 2).sum()
    ss_resid = ss_tot - ss_model - ss_arm
    df_m, df_a = n - 1, k - 1
    df_w, df_e = n * (k - 1), (n - 1) * (k - 1)
    ms_m, ms_a = ss_model / df_m, ss_arm / df_a
    ms_w, ms_e = ss_within / df_w, ss_resid / df_e

    def icc(ms_b, ms_err):
        vm = max((ms_b - ms_err) / k, 0.0)
        return vm / (vm + ms_err) if (vm + ms_err) > 0 else np.nan

    def icc_exact_ci(ms_b, ms_err, df2):
        """Shrout & Fleiss / McGraw & Wong exact F-based interval."""
        F = ms_b / ms_err
        FL = F / stats.f.ppf(0.975, df_m, df2)
        FU = F * stats.f.ppf(0.975, df2, df_m)
        return (FL - 1) / (FL + k - 1), (FU - 1) / (FU + k - 1)

    lo_e, hi_e = icc_exact_ci(ms_m, ms_e, df_e)
    lo_w, hi_w = icc_exact_ci(ms_m, ms_w, df_w)
    return {
        "icc_armFE_lo": lo_e,
        "icc_armFE_hi": hi_e,
        "icc_oneway_lo": lo_w,
        "icc_oneway_hi": hi_w,
        "n_models": n,
        "n_arms": k,
        "icc_oneway": icc(ms_m, ms_w),
        "icc_armFE": icc(ms_m, ms_e),
        "F_model_oneway": ms_m / ms_w,
        "p_model_oneway": float(stats.f.sf(ms_m / ms_w, df_m, df_w)),
        "F_model_armFE": ms_m / ms_e,
        "p_model_armFE": float(stats.f.sf(ms_m / ms_e, df_m, df_e)),
        "F_arm": ms_a / ms_e,
        "p_arm": float(stats.f.sf(ms_a / ms_e, df_a, df_e)),
        "sd_within_oneway": np.sqrt(ms_w),
        "sd_resid_armFE": np.sqrt(ms_e),
    }


def main() -> None:
    pd.set_option("display.width", 260, "display.max_columns", 50)
    panels, models, comps, T, L, S = scaled_panels()
    iu = np.triu_indices(len(models), 1)

    # observed compounded final return, to tie back to the published ICC
    desc = pd.read_csv(os.path.join(DER, "t1_descriptive.csv"))
    d15 = desc[desc["season"] == "S15"]
    compounded = d15.pivot(index="model", columns="competition_id",
                           values="return_pct").loc[models, comps].to_numpy(float)

    # ---------------------------------------------------- decomposition
    rows = []
    for name, X in panels.items():
        for drop4 in [False, True]:
            Xs = X[:, :3, :] if drop4 else X
            for how in ["pooled", "arm_day"]:
                c = vc.components(vc.adjust(Xs, how))
                raw = c["rho_raw"][iu]
                raw = raw[~np.isnan(raw)]
                rows.append(
                    {
                        "scaling": name,
                        "arms": "1-3" if drop4 else "1-4",
                        "variant": how,
                        "R": Xs.shape[1],
                        "median_iota": float(np.nanmedian(c["iota"])),
                        "min_iota": float(np.nanmin(c["iota"])),
                        "max_iota": float(np.nanmax(c["iota"])),
                        "median_rho_raw": float(np.median(raw)),
                        "n_rho_gt1": int((raw > 1).sum()),
                        "n_pairs": int(len(raw)),
                        "n_omega2_neg": int((c["omega2"] < 0).sum()),
                        "median_B_over_A": float(
                            np.nanmedian((c["B"] / c["A"])[iu])
                        ),
                    }
                )
    dec = pd.DataFrame(rows)
    dec.to_csv(os.path.join(DER, "c2_decomposition.csv"), index=False)
    print("=== C2a daily decomposition under each scaling ===")
    print(dec.to_string(index=False, float_format=lambda x: f"{x:,.3f}"))

    # ---------------------------------------------------- ANOVA
    arows = []
    outcomes = {
        "final return % (compounded, as published)": compounded,
        "cumulative return % (arithmetic sum of daily)": 100 * panels["raw"].sum(axis=2),
        "leverage-scaled cumulative % (per 1x of gross)":
            100 * panels["per_leverage"].sum(axis=2),
        "vol-standardised cumulative (= T x daily Sharpe)":
            panels["per_vol"].sum(axis=2),
    }
    for lbl, y in outcomes.items():
        for drop4 in [False, True]:
            yy = y[:, :3] if drop4 else y
            arows.append({"outcome": lbl, "arms": "1-3" if drop4 else "1-4", **anova(yy)})
    av = pd.DataFrame(arows)
    av.to_csv(os.path.join(DER, "c2_anova.csv"), index=False)
    print("\n=== C2b final-return ANOVA under each scaling ===")
    print(
        av[["outcome", "arms", "n_arms", "icc_oneway", "icc_armFE",
            "F_model_oneway", "p_model_oneway", "F_model_armFE", "p_model_armFE",
            "F_arm", "p_arm"]]
        .to_string(index=False, float_format=lambda x: f"{x:,.3f}")
    )

    with open(os.path.join(DER, "c2_summary.json"), "w") as fh:
        json.dump({"decomposition": rows, "anova": arows}, fh, indent=1, default=float)

    print("\nmean gross leverage by arm (pooled over models): "
          + ", ".join(f"arm{c} {L[:, j].mean():.2f}x" for j, c in enumerate(comps)))
    print("mean daily sd by arm: "
          + ", ".join(f"arm{c} {100*S[:, j].mean():.2f}%" for j, c in enumerate(comps)))


if __name__ == "__main__":
    main()
