"""Referee item 3: the risk-return relation at wallet level, n = 32 not n = 8.

Section 17 correlated eight model means. That throws away the within-arm
variation and leaves only six degrees of freedom. Here the unit is the wallet and
the comparison is made *inside* each arm, so arm effects cannot drive it:

    (a) mean of the four within-arm Spearman correlations (8 wallets each)
    (b) pooled correlation of within-arm-centred ranks, all 32 wallets

Inference is a stratified permutation test: the final-return values are permuted
*within* each arm, independently across arms, 10,000 draws, which is the exact
randomisation null for "no association between risk and return inside an arm".
Two-sided p-values are reported since the direction is not assumed a priori,
alongside the one-sided value matching the negative direction found in section 17.
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
RNG = np.random.default_rng(20261017)
NPERM = 10000
METRICS = ["daily_vol", "mean_leverage", "turnover_per_day", "share_in_market"]


def within_arm_stats(x: np.ndarray, y: np.ndarray, arm: np.ndarray, arms) -> dict:
    per = []
    cx, cy = np.empty_like(x), np.empty_like(y)
    for a in arms:
        ii = arm == a
        rx = stats.rankdata(x[ii])
        ry = stats.rankdata(y[ii])
        per.append(np.corrcoef(rx, ry)[0, 1])
        cx[ii] = rx - rx.mean()
        cy[ii] = ry - ry.mean()
    pooled = float(np.corrcoef(cx, cy)[0, 1])
    return {"mean_within_arm_rho": float(np.mean(per)),
            "pooled_centred_rank_rho": pooled,
            "per_arm": [float(v) for v in per]}


def main() -> None:
    pd.set_option("display.width", 260, "display.max_columns", 40)
    w = pd.read_csv(os.path.join(DER, "c4_wallet_risk.csv"))
    arms = sorted(w["arm"].unique())
    arm = w["arm"].to_numpy()
    y = w["final_return_pct"].to_numpy(float)

    rows = []
    for met in METRICS:
        x = w[met].to_numpy(float)
        obs = within_arm_stats(x, y, arm, arms)

        # stratified permutation: shuffle returns inside each arm
        idx = {a: np.where(arm == a)[0] for a in arms}
        draws_m = np.empty(NPERM)
        draws_p = np.empty(NPERM)
        for b in range(NPERM):
            yp = y.copy()
            for a in arms:
                ii = idx[a]
                yp[ii] = RNG.permutation(y[ii])
            s = within_arm_stats(x, yp, arm, arms)
            draws_m[b] = s["mean_within_arm_rho"]
            draws_p[b] = s["pooled_centred_rank_rho"]

        def pvals(obs_v, draws):
            one = (np.sum(draws <= obs_v) + 1) / (NPERM + 1)   # H1: negative
            two = (np.sum(np.abs(draws) >= abs(obs_v)) + 1) / (NPERM + 1)
            return one, two

        o1, t1 = pvals(obs["mean_within_arm_rho"], draws_m)
        o2, t2 = pvals(obs["pooled_centred_rank_rho"], draws_p)
        rows.append(
            {
                "metric": met,
                "mean_within_arm_rho": obs["mean_within_arm_rho"],
                "perm_p_one_sided": o1,
                "perm_p_two_sided": t1,
                "pooled_centred_rank_rho": obs["pooled_centred_rank_rho"],
                "pooled_perm_p_one_sided": o2,
                "pooled_perm_p_two_sided": t2,
                "naive_spearman_all32": float(stats.spearmanr(x, y).statistic),
                "naive_p_all32": float(stats.spearmanr(x, y).pvalue),
                **{f"rho_arm{a}": v for a, v in zip(arms, obs["per_arm"])},
            }
        )

    res = pd.DataFrame(rows)
    res.to_csv(os.path.join(DER, "r3_wallet_rankcorr.csv"), index=False)
    print("=== R3 risk-return rank correlation at wallet level, within arm (n = 32) ===\n")
    print(
        res[["metric", "mean_within_arm_rho", "perm_p_one_sided", "perm_p_two_sided",
             "pooled_centred_rank_rho", "pooled_perm_p_two_sided",
             "naive_spearman_all32"]]
        .to_string(index=False, float_format=lambda x: f"{x:,.4f}")
    )
    print("\nper-arm rank correlations:")
    print(
        res[["metric"] + [f"rho_arm{a}" for a in arms]]
        .to_string(index=False, float_format=lambda x: f"{x:,.3f}")
    )
    with open(os.path.join(DER, "r3_wallet_rankcorr.json"), "w") as fh:
        json.dump({"nperm": NPERM, "rows": rows}, fh, indent=1, default=float)


if __name__ == "__main__":
    main()
