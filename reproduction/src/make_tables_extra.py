"""Emit tables for AUDIT.md sections 18+ (pre-work A and referee items 1-5)."""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import prov

DER = os.path.join(prov.ROOT, "data", "derived")
OUT = os.path.join(DER, "tables_extra.md")
PNL = ["exposure_pnl", "timing_pnl", "slippage", "fees", "funding", "net_pnl"]
NICE = {"exposure_pnl": "exposure", "timing_pnl": "timing", "slippage": "slippage",
        "fees": "fees", "funding": "funding", "net_pnl": "net"}


def _opt(name):
    p = os.path.join(DER, name)
    return p if os.path.exists(p) else None


def main() -> None:
    parts: list[str] = []
    A = parts.append

    # ------------------------------------------------------- A1: P&L decomposition
    d = pd.read_csv(os.path.join(DER, "a1_pnl_decomposition.csv"))
    with open(os.path.join(DER, "a1_pnl_summary.json")) as fh:
        j = json.load(fh)

    tot = pd.DataFrame(
        [{"season": s, "book $": 60000 if s == "S1" else 320000,
          **{NICE[c]: v for c, v in j["totals"][s].items()}}
         for s in ["S1", "S15"]]
    )
    tot["slippage"] = -tot["slippage"]
    tot["fees"] = -tot["fees"]
    tot["net % of book"] = 100 * tot["net"] / tot["book $"]
    A("### X1 P&L decomposition, season totals (signed contributions, USD)\n")
    A(tot.to_markdown(index=False, floatfmt=",.0f"))
    A(f"\nThe identity *equity change = exposure + timing − slippage − fees + funding* "
      f"closes to at most {j['identity_max_gap_pct']:.2f}% of a $10,000 book per wallet.")

    s15 = d[d["season"] == "S15"]
    bym = s15.groupby("model")[PNL].sum().rename(columns=NICE)
    bym["slippage"] = -bym["slippage"]
    bym["fees"] = -bym["fees"]
    bym["net % of $40k"] = 100 * bym["net"] / 40000
    bym = bym.sort_values("net", ascending=False)
    A("\n### X2 S1.5 P&L decomposition by model (four wallets each, $40,000 book)\n")
    A(bym.to_markdown(floatfmt=",.0f"))

    bya = s15.groupby("competition_id")[PNL].sum().rename(columns=NICE)
    bya["slippage"] = -bya["slippage"]
    bya["fees"] = -bya["fees"]
    bya["net % of $80k"] = 100 * bya["net"] / 80000
    A("\n### X3 S1.5 P&L decomposition by arm (eight wallets each, $80,000 book)\n")
    A(bya.to_markdown(floatfmt=",.0f"))

    s1 = d[d["season"] == "S1"].copy()
    s1b = s1.set_index("model")[PNL].rename(columns=NICE)
    s1b["slippage"] = -s1b["slippage"]
    s1b["fees"] = -s1b["fees"]
    s1b["net % of $10k"] = 100 * s1b["net"] / 10000
    s1b = s1b.sort_values("net", ascending=False)
    A("\n### X4 Season 1 P&L decomposition by model ($10,000 book each)\n")
    A(s1b.to_markdown(floatfmt=",.0f"))

    # ------------------------------------------------- A2: S1 vs S1.5 risk traits
    if _opt("a2_risk_seasons.csv"):
        r = pd.read_csv(os.path.join(DER, "a2_risk_seasons.csv"))
        A("\n### X5 Risk metrics by model and season\n")
        A(r.to_markdown(index=False, floatfmt=".3f"))
    if _opt("a2_risk_crossseason.json"):
        with open(os.path.join(DER, "a2_risk_crossseason.json")) as fh:
            j2 = json.load(fh)
        A("\n### X6 Does a model's risk appetite carry across seasons?\n")
        A(pd.DataFrame(j2["correlations"]).to_markdown(index=False, floatfmt=".3f"))
        A(f"\nModels common to both seasons: {', '.join(j2['common_models'])} "
          f"(n = {j2['n_common']}). Season 1 is crypto perpetuals over "
          f"{j2['S1_days']} days; Season 1.5 is tokenised US equities over "
          f"{j2['S15_days']} days, so this is a cross-asset, cross-window test.")

    # ------------------------------------------- R1: does risk absorb the model effect
    if _opt("r1_covariate.csv"):
        r1 = pd.read_csv(os.path.join(DER, "r1_covariate.csv"))
        A("\n### X7 Does risk account for the model effect in returns?\n")
        A(r1.to_markdown(index=False, floatfmt=".4f"))

    # --------------------------------------------- R2: permutation p for every ANOVA
    if _opt("r2_permutation.csv"):
        r2 = pd.read_csv(os.path.join(DER, "r2_permutation.csv"))
        A("\n### X8 Permutation p-values beside the F-based ones "
          "(model labels permuted within arm, 10,000 draws)\n")
        A(r2.to_markdown(index=False, floatfmt=".4f"))

    # ------------------------------------------------- R3: wallet-level risk-return
    if _opt("r3_wallet_rankcorr.csv"):
        r3 = pd.read_csv(os.path.join(DER, "r3_wallet_rankcorr.csv"))
        A("\n### X9 Wallet-level risk-return relation, within arm, n = 32\n")
        A(r3.to_markdown(index=False, floatfmt=".4f"))

    # ----------------------------------------------- R4: serial dependence, horizon
    if _opt("r4_horizon.csv"):
        r4 = pd.read_csv(os.path.join(DER, "r4_horizon.csv"))
        A("\n### X10 Required horizon for a Sharpe gap of 1 at R = 1, "
          "under long-run variances\n")
        A(r4.to_markdown(index=False, floatfmt=".3f"))
    if _opt("r4_autocorr.csv"):
        ac = pd.read_csv(os.path.join(DER, "r4_autocorr.csv"))
        A("\n### X11 Autocorrelation of daily return differences across the 28 pairs\n")
        A(ac.to_markdown(index=False, floatfmt=".4f"))

    # --------------------------------------------- P1: out-of-window persistence
    if _opt("p1_persistence.csv"):
        pp = pd.read_csv(os.path.join(DER, "p1_persistence.csv"))
        with open(os.path.join(DER, "p1_persistence.json")) as fh:
            jp = json.load(fh)
        w = jp["windows"]
        A("\n### X12 Does risk appetite persist past the official season end?\n")
        A(
            pp[["metric", "spearman_wallet", "perm_p_overall", "perm_p_stratified",
                "spearman_model_means", "kendall_W_periods"]]
            .rename(columns={
                "spearman_wallet": "rho wallets (n=32)",
                "perm_p_overall": "perm p",
                "perm_p_stratified": "perm p (within arm)",
                "spearman_model_means": "rho model means (n=8)",
                "kendall_W_periods": "Kendall W across periods"})
            .to_markdown(index=False, floatfmt=".4f")
        )
        A("\n### X13 Two-way ANOVA in the post-season period alone\n")
        A(
            pp[["metric", "in_F_model", "in_icc", "post_F_model", "post_p_model",
                "post_icc", "post_icc_lo", "post_icc_hi", "post_F_arm", "post_p_arm"]]
            .rename(columns={
                "in_F_model": "F model (in-season)", "in_icc": "ICC (in-season)",
                "post_F_model": "F model (post)", "post_p_model": "p (post)",
                "post_icc": "ICC (post)", "post_icc_lo": "ICC 2.5%",
                "post_icc_hi": "ICC 97.5%", "post_F_arm": "F arm (post)",
                "post_p_arm": "p arm (post)"})
            .to_markdown(index=False, floatfmt=".4f")
        )
        A(f"\nPost-season window {pd.Timestamp(w['post_lo'], unit='ms', tz='UTC'):%Y-%m-%d %H:%M} "
          f"to {pd.Timestamp(w['post_hi'], unit='ms', tz='UTC'):%Y-%m-%d %H:%M} "
          f"({w['post_days']:.1f} days, {w['post_days_min']} trading days per "
          f"wallet, {w['post_fills']:,} fills against {w['in_fills']:,} in-season).")

    with open(OUT, "w") as fh:
        fh.write("\n".join(parts) + "\n")
    print(f"wrote {OUT} ({len(parts)} blocks)")


if __name__ == "__main__":
    main()
