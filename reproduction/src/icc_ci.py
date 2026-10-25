"""Item 5: exact F-based 95% interval for the ICC of S1.5 final returns.

One-way random effects (the audit's T6), n = 8 models, k = 4 competitions:
    F  = MS_between / MS_within,      df = (n-1, n(k-1)) = (7, 24)
    FL = F / F_{1-a/2}(n-1, n(k-1))
    FU = F * F_{1-a/2}(n(k-1), n-1)
    ICC in [ (FL-1)/(FL+k-1), (FU-1)/(FU+k-1) ]
(Shrout & Fleiss 1979; McGraw & Wong 1996.)

Item 1 showed the four competitions are different treatment arms, so the
consistency form is also reported: the same transformation with the two-way
residual mean square in place of MS_within, df = (7, 21), which is the ICC that
goes with the arm-fixed-effect decomposition.

A parametric bootstrap is run alongside purely as a check that the exact
interval is not misstated.
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

DER = os.path.join(prov.ROOT, "data", "derived")
RNG = np.random.default_rng(20261011)
ALPHA = 0.05


def mean_squares(y: np.ndarray) -> dict:
    """y is (n models, k arms), one observation per cell."""
    n, k = y.shape
    grand = y.mean()
    rm, cm = y.mean(axis=1), y.mean(axis=0)
    ss_b = k * ((rm - grand) ** 2).sum()
    ss_arm = n * ((cm - grand) ** 2).sum()
    ss_w = ((y - rm[:, None]) ** 2).sum()
    ss_e = ((y - grand) ** 2).sum() - ss_b - ss_arm
    return {
        "n": n,
        "k": k,
        "ms_b": ss_b / (n - 1),
        "ms_w": ss_w / (n * (k - 1)),
        "ms_e": ss_e / ((n - 1) * (k - 1)),
        "ms_arm": ss_arm / (k - 1),
    }


def icc_exact(ms_b: float, ms_err: float, n: int, k: int, df2: int) -> dict:
    F = ms_b / ms_err
    df1 = n - 1
    FL = F / stats.f.ppf(1 - ALPHA / 2, df1, df2)
    FU = F * stats.f.ppf(1 - ALPHA / 2, df2, df1)
    est = (F - 1) / (F + k - 1)
    return {
        "F": F,
        "df1": df1,
        "df2": df2,
        "p_value": float(stats.f.sf(F, df1, df2)),
        "icc": est,
        "icc_lo": (FL - 1) / (FL + k - 1),
        "icc_hi": (FU - 1) / (FU + k - 1),
        "var_model": max((ms_b - ms_err) / k, 0.0),
        "var_err": ms_err,
    }


def parametric_bootstrap(ms: dict, which: str, nboot: int = 20000) -> tuple[float, float]:
    """Check only: simulate under the fitted one-way model and re-estimate."""
    n, k = ms["n"], ms["k"]
    err = ms["ms_w"] if which == "oneway" else ms["ms_e"]
    df2 = n * (k - 1) if which == "oneway" else (n - 1) * (k - 1)
    va = max((ms["ms_b"] - err) / k, 0.0)
    out = np.empty(nboot)
    for b in range(nboot):
        a = RNG.normal(0, np.sqrt(va), size=n)
        e = RNG.normal(0, np.sqrt(err), size=(n, k))
        y = a[:, None] + e
        m = mean_squares(y)
        ee = m["ms_w"] if which == "oneway" else m["ms_e"]
        F = m["ms_b"] / ee
        out[b] = (F - 1) / (F + k - 1)
    return float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))


def main() -> None:
    desc = pd.read_csv(os.path.join(DER, "t1_descriptive.csv"))
    d = desc[desc["season"] == "S15"]
    piv = d.pivot(index="model", columns="competition_id", values="return_pct")
    y = piv.to_numpy(float)
    ms = mean_squares(y)
    n, k = ms["n"], ms["k"]

    one = icc_exact(ms["ms_b"], ms["ms_w"], n, k, n * (k - 1))
    two = icc_exact(ms["ms_b"], ms["ms_e"], n, k, (n - 1) * (k - 1))

    rows = []
    for name, r, lbl in [
        ("one-way (audit T6; arms treated as replicates)", one, "oneway"),
        ("consistency, arm fixed effect removed (item 1)", two, "twoway"),
    ]:
        pb = parametric_bootstrap(ms, lbl, nboot=5000)
        rows.append(
            {
                "model": name,
                "n_models": n,
                "k_arms": k,
                "F": r["F"],
                "df": f"({r['df1']},{r['df2']})",
                "p_value": r["p_value"],
                "ICC": r["icc"],
                "ICC_lo_exactF": r["icc_lo"],
                "ICC_hi_exactF": r["icc_hi"],
                "sd_model_pp": np.sqrt(r["var_model"]),
                "sd_err_pp": np.sqrt(r["var_err"]),
                "pboot_lo_check": pb[0],
                "pboot_hi_check": pb[1],
            }
        )
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(DER, "i5_icc_ci.csv"), index=False)
    pd.set_option("display.width", 250, "display.max_columns", 40)
    print("=== I5 ICC of S1.5 final returns, exact F-based 95% interval ===\n")
    for r in out.itertuples():
        print(f"{r.model}")
        print(f"   F{r.df} = {r.F:.3f}   p = {r.p_value:.4f}")
        print(f"   ICC = {r.ICC:.3f}   95% CI [{r.ICC_lo_exactF:.3f}, {r.ICC_hi_exactF:.3f}]"
              f"   (parametric-bootstrap check [{r.pboot_lo_check:.3f}, {r.pboot_hi_check:.3f}])")
        print(f"   sd between models {r.sd_model_pp:.1f}pp   sd within {r.sd_err_pp:.1f}pp\n")

    with open(os.path.join(DER, "i5_icc_ci.json"), "w") as fh:
        json.dump(out.to_dict("records"), fh, indent=1, default=float)


if __name__ == "__main__":
    main()
