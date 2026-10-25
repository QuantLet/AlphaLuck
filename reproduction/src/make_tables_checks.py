"""Emit the tables for robustness checks 1-3 (AUDIT.md sections 14-16)."""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import prov

DER = os.path.join(prov.ROOT, "data", "derived")
OUT = os.path.join(DER, "tables_checks.md")


def main() -> None:
    parts: list[str] = []
    A = parts.append

    # ---------------------------------------------------------------- check 1
    c1 = pd.read_csv(os.path.join(DER, "c1_identification.csv"))
    with open(os.path.join(DER, "c1_identification.json")) as fh:
        j1 = json.load(fh)
    A("### C1 How often the estimator returns rho_m > 1 when the model is TRUE\n")
    A(
        c1[["dist", "sigma", "iota_true", "rho_true", "median_count_gt1",
            "q05_count", "q95_count", "P_count_ge_11", "median_rho_hat",
            "mean_iota_hat"]]
        .rename(columns={
            "dist": "shocks", "sigma": "sigma across models",
            "iota_true": "true iota", "rho_true": "true rho_m",
            "median_count_gt1": "median # of 28 inadmissible",
            "q05_count": "5%", "q95_count": "95%",
            "P_count_ge_11": "P(>= 11, as observed)",
            "median_rho_hat": "median rho_m_hat",
            "mean_iota_hat": "mean iota_hat",
        })
        .to_markdown(index=False, floatfmt=".3f")
    )
    q = j1["pooled_quantiles"]
    A(
        f"\nObserved: **11 of 28** pairs daily with arm effects removed, 13 pooled, "
        f"15 at 4-hour frequency. Pooled over all 20 simulation cells the count has "
        f"median {q['50']:.0f} and a 5–95% range of {q['5']:.0f}–{q['95']:.0f}, with "
        f"P(count >= 11) = {j1['pooled_P_ge_11']:.3f} and "
        f"P(count >= 13) = {j1['pooled_P_ge_13']:.3f}."
    )

    # ---------------------------------------------------------------- check 2
    c2d = pd.read_csv(os.path.join(DER, "c2_decomposition.csv"))
    A("\n### C2a Daily decomposition under each rescaling (does rho_m > 1 persist?)\n")
    A(
        c2d[["scaling", "arms", "variant", "R", "median_iota", "median_rho_raw",
             "n_rho_gt1", "n_pairs", "n_omega2_neg", "median_B_over_A"]]
        .rename(columns={"n_rho_gt1": "pairs with rho_m>1",
                         "n_pairs": "pairs", "n_omega2_neg": "omega2<0",
                         "median_rho_raw": "median raw rho_m"})
        .to_markdown(index=False, floatfmt=".3f")
    )

    c2a = pd.read_csv(os.path.join(DER, "c2_anova.csv"))
    A("\n### C2b Final-return ANOVA as risk-taking is removed\n")
    A(
        c2a[["outcome", "arms", "icc_oneway", "icc_armFE", "F_model_armFE",
             "p_model_armFE", "F_arm", "p_arm"]]
        .rename(columns={"icc_oneway": "ICC one-way", "icc_armFE": "ICC arm-FE",
                         "F_model_armFE": "F model (7,21)",
                         "p_model_armFE": "p model", "F_arm": "F arm",
                         "p_arm": "p arm"})
        .to_markdown(index=False, floatfmt=".3f")
    )

    # ---------------------------------------------------------------- check 3
    c3 = pd.read_csv(os.path.join(DER, "c3_variance_shares.csv"))
    rows = []
    for out in c3["outcome"].unique():
        d = c3[c3["outcome"] == out].set_index("quantity")
        rows.append(
            {
                "outcome": out,
                "model": f"{d.loc['share_model','estimate']:.3f} "
                         f"[{d.loc['share_model','ci_lo']:.3f}, {d.loc['share_model','ci_hi']:.3f}]",
                "arm (rules)": f"{d.loc['share_arm','estimate']:.3f} "
                               f"[{d.loc['share_arm','ci_lo']:.3f}, {d.loc['share_arm','ci_hi']:.3f}]",
                "residual (interaction + luck)":
                    f"{d.loc['share_resid','estimate']:.3f} "
                    f"[{d.loc['share_resid','ci_lo']:.3f}, {d.loc['share_resid','ci_hi']:.3f}]",
                "F model (7,21)": f"{d.loc['F_model','estimate']:.2f}",
                "p model": f"{d.loc['p_model','estimate']:.3f}",
                "F arm (3,21)": f"{d.loc['F_arm','estimate']:.2f}",
                "p arm": f"{d.loc['p_arm','estimate']:.3f}",
            }
        )
    A("\n### C3 Two-way variance shares with 95% day-bootstrap intervals\n")
    A(pd.DataFrame(rows).to_markdown(index=False))

    with open(os.path.join(DER, "c3_summary.json")) as fh:
        j3 = json.load(fh)
    ss = pd.DataFrame(
        [
            {
                "outcome": k,
                "model": v["ss_share_model"],
                "arm (rules)": v["ss_share_arm"],
                "residual": v["ss_share_resid"],
            }
            for k, v in j3.items()
        ]
    )
    A("\n### C4 The same split as raw sums-of-squares shares (no truncation at zero)\n")
    A(ss.to_markdown(index=False, floatfmt=".3f"))

    # ---------------------------------------------------------------- check 4
    wt = pd.read_csv(os.path.join(DER, "c4_wallet_risk.csv"))
    METRICS = ["daily_vol", "mean_leverage", "share_in_market", "turnover_per_day"]
    A("\n### C5 Risk metrics by arm (mean over the 8 models)\n")
    A(
        wt.groupby("arm")[METRICS + ["final_return_pct"]]
        .mean()
        .rename(columns={"daily_vol": "daily vol", "mean_leverage": "mean gross lev",
                         "share_in_market": "share in market",
                         "turnover_per_day": "turnover / day",
                         "final_return_pct": "final return %"})
        .to_markdown(floatfmt=".3f")
    )

    st = pd.read_csv(os.path.join(DER, "c4_stats.csv"))
    A("\n### C6 Is each risk metric a model trait? Two-way ANOVA, arm-adjusted ICC, "
      "and whether the arms agree on the model ordering\n")
    A(
        st[["metric", "F_model", "p_model", "icc_armFE", "icc_lo", "icc_hi",
            "F_arm", "p_arm", "kendall_W", "p_W_perm"]]
        .rename(columns={"F_model": "F model (7,21)", "p_model": "p model",
                         "icc_armFE": "ICC arm-FE", "icc_lo": "ICC 2.5%",
                         "icc_hi": "ICC 97.5%", "F_arm": "F arm (3,21)",
                         "p_arm": "p arm", "kendall_W": "Kendall W",
                         "p_W_perm": "p (perm)"})
        .to_markdown(index=False, floatfmt=".4f")
    )

    rk = pd.read_csv(os.path.join(DER, "c4_ranks.csv"))
    arms = [c for c in rk.columns if c.startswith("arm")]
    for met, lab in [("mean_leverage", "mean gross leverage"),
                     ("daily_vol", "realised daily volatility")]:
        d = rk[rk["metric"] == met].sort_values("rank_sum")
        A(f"\n### C7{'a' if met == 'mean_leverage' else 'b'} Rank of each model "
          f"within each arm, {lab} (1 = least risk)\n")
        A(
            d[["model"] + arms + ["rank_sum", "mean_value"]]
            .to_markdown(index=False, floatfmt=".2f")
        )

    rc = pd.read_csv(os.path.join(DER, "c4_rankcorr.csv"))
    A("\n### C8 Rank correlation between a model's mean risk metric and its mean "
      "final return\n")
    A(
        rc[["metric", "spearman", "ci_lo", "ci_hi", "boot_sd", "P_rho_lt_0",
            "spearman_p_exact"]]
        .rename(columns={"spearman": "Spearman rho", "ci_lo": "2.5%",
                         "ci_hi": "97.5%", "boot_sd": "boot sd",
                         "P_rho_lt_0": "P(rho<0) in bootstrap",
                         "spearman_p_exact": "exact p"})
        .to_markdown(index=False, floatfmt=".3f")
    )
    with open(os.path.join(DER, "c4_summary.json")) as fh:
        j4 = json.load(fh)
    cst = j4["costs"]
    A(
        f"\nTrading costs over the same window: **${cst['total_fees_usd']:,.0f} of fees "
        f"across the 32 wallets on a $320,000 book in 13 days, 10.1% of capital**, "
        f"mean {cst['mean_cost_pct']:.1f}% per wallet net of "
        f"${cst['total_funding_usd']:,.0f} of funding received. "
        f"Spearman(cost, final return) = {cst['spearman']:.3f} "
        f"(exact p = {cst['spearman_p_exact']:.3f})."
    )

    with open(OUT, "w") as fh:
        fh.write("\n".join(parts) + "\n")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
