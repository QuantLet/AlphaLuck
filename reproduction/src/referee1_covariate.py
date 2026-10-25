"""Referee item 1: does risk account for the model effect in returns?

On the 32 Season-1.5 wallets, regress final return on model and arm effects,
then add the wallet's own realised daily volatility -- and, separately, its mean
gross leverage -- as a covariate:

    (A)  y = mu + model + arm + e
    (B)  y = mu + model + arm + b*volatility + e
    (C)  y = mu + model + arm + b*leverage   + e

Reported for each: the joint F-test on the seven model dummies with its F-based
p, a permutation p, the partial R^2 of the model term, and the model sum of
squares. The share of the between-model variance removed by the covariate is
1 - SS_model(with covariate) / SS_model(without), using partial (Type II) sums
of squares throughout.

Permutation scheme: the design is balanced -- every arm contains all eight
models exactly once -- so under the null of no model effect the wallets are
exchangeable within an arm. Each draw permutes which model label is attached to
which wallet *within* each arm, carrying the wallet's (y, covariate) pair
together so the return-risk relationship is left intact and only the model
assignment is scrambled. 10,000 draws.
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
RNG = np.random.default_rng(20261015)
NPERM = 10000


def design(models, arms, model_codes, arm_codes, cov=None):
    """Intercept + (K-1) model dummies + (R-1) arm dummies + optional covariate."""
    n = len(model_codes)
    cols = [np.ones(n)]
    for k in models[1:]:
        cols.append((model_codes == k).astype(float))
    for a in arms[1:]:
        cols.append((arm_codes == a).astype(float))
    if cov is not None:
        cols.append(np.asarray(cov, float))
    return np.column_stack(cols)


def sse(X, y):
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    r = y - X @ beta
    return float(r @ r), beta


def fit(models, arms, mc, ac, y, cov=None) -> dict:
    Xf = design(models, arms, mc, ac, cov)
    n, p = Xf.shape
    sse_f, beta = sse(Xf, y)
    df_res = n - p

    # drop the model dummies
    keep = [0] + list(range(len(models), Xf.shape[1]))
    Xr = Xf[:, keep]
    sse_r, _ = sse(Xr, y)

    df_model = len(models) - 1
    ss_model = sse_r - sse_f
    F = (ss_model / df_model) / (sse_f / df_res)
    return {
        "F_model": F,
        "df": (df_model, df_res),
        "p_F": float(stats.f.sf(F, df_model, df_res)),
        "ss_model": ss_model,
        "partial_R2_model": ss_model / sse_r if sse_r > 0 else np.nan,
        "sse_full": sse_f,
        "beta_cov": float(beta[-1]) if cov is not None else np.nan,
        "r2_total": 1 - sse_f / float(((y - y.mean()) ** 2).sum()),
    }


def perm_p(models, arms, mc, ac, y, cov, obs_F) -> float:
    """Permute model labels within arm, carrying (y, cov) with the wallet."""
    cnt = 0
    idx_by_arm = {a: np.where(ac == a)[0] for a in arms}
    for _ in range(NPERM):
        mc_p = mc.copy()
        for a in arms:
            ii = idx_by_arm[a]
            mc_p[ii] = RNG.permutation(mc[ii])
        f = fit(models, arms, mc_p, ac, y, cov)["F_model"]
        if f >= obs_F:
            cnt += 1
    return (cnt + 1) / (NPERM + 1)


def main() -> None:
    pd.set_option("display.width", 260, "display.max_columns", 40)
    w = pd.read_csv(os.path.join(DER, "c4_wallet_risk.csv"))
    # Primary risk measures are those on initial capital: a volatility or a
    # leverage computed against current equity rises when an account loses,
    # so regressing the return on it puts part of the dependent variable
    # into the covariate. See src/vol_fixed_denominator.py.
    fx = pd.read_csv(os.path.join(DER, "i6_vol_denominator.csv"))
    w = w.merge(fx[["tag", "vol_fixed", "leverage_fixed", "turnover_fixed"]],
                on="tag", how="left")
    models = sorted(w["model"].unique())
    arms = sorted(w["arm"].unique())
    mc = w["model"].to_numpy()
    ac = w["arm"].to_numpy()
    y = w["final_return_pct"].to_numpy(float)

    specs = [
        ("A: model + arm", None, None),
        ("B: + volatility on initial capital", "vol_fixed",
         w["vol_fixed"].to_numpy(float)),
        ("C: + gross exposure on initial capital", "leverage_fixed",
         w["leverage_fixed"].to_numpy(float)),
        ("D: + volatility on current equity", "daily_vol",
         w["daily_vol"].to_numpy(float)),
        ("E: + gross leverage on current equity", "mean_leverage",
         w["mean_leverage"].to_numpy(float)),
    ]
    rows = []
    base_ss = None
    for label, covname, cov in specs:
        r = fit(models, arms, mc, ac, y, cov)
        r["perm_p"] = perm_p(models, arms, mc, ac, y, cov, r["F_model"])
        if base_ss is None:
            base_ss = r["ss_model"]
        r["share_of_between_model_SS_removed"] = 1 - r["ss_model"] / base_ss
        rows.append({"specification": label, "covariate": covname or "-", **r})

    res = pd.DataFrame(rows)
    res["df"] = res["df"].astype(str)
    res.to_csv(os.path.join(DER, "r1_covariate.csv"), index=False)
    print("=== R1 model effect on final return, before and after a risk covariate ===\n")
    print(
        res[["specification", "F_model", "df", "p_F", "perm_p", "partial_R2_model",
             "ss_model", "share_of_between_model_SS_removed", "beta_cov", "r2_total"]]
        .to_string(index=False, float_format=lambda x: f"{x:,.4f}")
    )

    # how much of y the covariate explains on its own, net of arm
    for covname in ["vol_fixed", "leverage_fixed", "daily_vol",
                    "mean_leverage"]:
        cov = w[covname].to_numpy(float)
        arm_cols = list(range(len(models), len(models) + len(arms) - 1))
        X0 = design(models, arms, mc, ac)[:, [0] + arm_cols]
        s0, _ = sse(X0, y)
        s1, _ = sse(np.column_stack([X0, cov]), y)
        print(f"\n  {covname}: partial R^2 against arm only = {(s0 - s1) / s0:.3f}")
        print(f"  Spearman({covname}, final return) over the 32 wallets = "
              f"{stats.spearmanr(cov, y).statistic:.3f} "
              f"(p = {stats.spearmanr(cov, y).pvalue:.4f})")

    with open(os.path.join(DER, "r1_covariate.json"), "w") as fh:
        json.dump(rows, fh, indent=1, default=float)


if __name__ == "__main__":
    main()
