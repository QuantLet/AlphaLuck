"""Emit the follow-up tables (items 1-5) spliced into AUDIT.md sections 9-13."""
from __future__ import annotations

import itertools
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import prov

DER = os.path.join(prov.ROOT, "data", "derived")
OUT = os.path.join(DER, "tables_followup.md")


def main() -> None:
    parts: list[str] = []
    A = parts.append

    # ---------------------------------------------------------------- item 1
    arms = pd.read_csv(os.path.join(prov.ROOT, "competitions.csv"))
    A("### F1 The four competitions are four treatment arms (organiser's own descriptions)\n")
    A(
        arms[["competition_id", "title", "subtitle", "n_prompts_sampled",
              "n_with_peer_standings"]]
        .rename(columns={"n_prompts_sampled": "prompts_seen",
                         "n_with_peer_standings": "with_peer_standings"})
        .to_markdown(index=False)
    )

    ex = pd.read_csv(os.path.join(DER, "i1_exchangeability.csv"))
    A("\n### F2 Behavioural metrics by arm, pooled over the 8 models (Friedman, models as blocks)\n")
    A(
        ex[["metric", "arm1_mean", "arm2_mean", "arm3_mean", "arm4_mean",
            "max_over_min_arm_mean", "friedman_chi2", "p_value", "kendall_W"]]
        .to_markdown(index=False, floatfmt=".4f")
    )

    with open(os.path.join(DER, "i1_decomposition.json")) as fh:
        dc = json.load(fh)
    A("\n### F3 Final-return decomposition, with and without an arm fixed effect\n")
    dec = pd.DataFrame(
        [
            {
                "specification": "one-way (audit T6): arms treated as replicates",
                "sd_within_model_pp": dc["oneway_sd_within_pp"],
                "sd_between_model_pp": dc["oneway_sd_between_pp"],
                "ICC": dc["oneway_icc"],
                "F_model": dc["oneway_F"],
                "df": "(7,24)",
                "p_model": dc["oneway_p"],
            },
            {
                "specification": "two-way: arm fixed effect removed",
                "sd_within_model_pp": dc["twoway_sd_resid_pp"],
                "sd_between_model_pp": dc["twoway_sd_between_pp"],
                "ICC": dc["twoway_icc"],
                "F_model": dc["twoway_F_model"],
                "df": "(7,21)",
                "p_model": dc["twoway_p_model"],
            },
        ]
    )
    A(dec.to_markdown(index=False, floatfmt=".3f"))
    A(
        f"\nArm main effect: F(3,21) = {dc['arm_F']:.2f}, p = {dc['arm_p']:.4f}. "
        "Arm effects on final return, percentage points against the grand mean: "
        + ", ".join(f"arm {c} {v:+.1f}" for c, v in dc["arm_effects_pp"].items())
        + f". Arm differences account for "
        f"{100*dc['share_of_oneway_within_explained_by_arm']:.1f}% of what the "
        "one-way model charged to within-model luck."
    )

    # ---------------------------------------------------------------- item 2
    with open(os.path.join(DER, "i2_summary.json")) as fh:
        s2 = json.load(fh)

    for how, lbl in [("pooled", "pooled"), ("arm_day", "arm effects removed")]:
        c = pd.read_csv(os.path.join(DER, f"i2_components_daily_{how}.csv"))
        A(f"\n### F4{'a' if how == 'pooled' else 'b'} Daily variance components per model "
          f"[{lbl}], R=4, T=13\n")
        A(
            c[["model", "mean_daily_pct", "tau_pct", "omega_pct", "iota",
               "iota_lo", "iota_hi", "iota_jk_min", "iota_jk_max"]]
            .rename(columns={
                "mean_daily_pct": "mean_daily_%",
                "tau_pct": "tau_% (replicate sd)",
                "omega_pct": "omega_% (path sd)",
                "iota_lo": "iota_2.5%",
                "iota_hi": "iota_97.5%",
                "iota_jk_min": "iota_jk_lo",
                "iota_jk_max": "iota_jk_hi",
            })
            .to_markdown(index=False, floatfmt=".3f")
        )

    rows = []
    for freq in ["daily", "4h"]:
        for how in ["pooled", "arm_level", "arm_day"]:
            s = s2[freq][how]
            rows.append(
                {
                    "frequency": freq,
                    "variant": how,
                    "T_periods": s2[freq]["T"],
                    "median_iota": s["median_iota"],
                    "iota_CI_lo": s["iota_ci"][0],
                    "iota_CI_hi": s["iota_ci"][1],
                    "median_rho_m": s["median_rho_m"],
                    "median_B_over_A": s["median_B_over_A"],
                    "pairs_with_rho_m>1": f"{s['n_rho_inadmissible']}/{s['n_pairs']}",
                    "raw_rho_m_median": s["rho_raw_median"],
                    "raw_rho_m_max": s["rho_raw_max"],
                    "omega2<0": s["n_omega2_negative"],
                }
            )
    A("\n### F5 Variance-component summary, and the admissibility diagnostic\n")
    A(pd.DataFrame(rows).to_markdown(index=False, floatfmt=".3f"))

    pw = pd.read_csv(os.path.join(DER, "i2_pairs_daily_arm_day.csv"))
    A("\n### F6 Pairwise quantities, daily, arm effects removed (28 pairs)\n")
    A(
        pw[["rho_m", "A", "B", "B_over_A"]]
        .describe()
        .loc[["mean", "25%", "50%", "75%", "min", "max"]]
        .to_markdown(floatfmt=".4f")
    )

    # ---------------------------------------------------------------- item 3
    t3 = pd.read_csv(os.path.join(DER, "i3_design.csv"))
    A("\n### F7 Years needed to detect an annualised Sharpe gap, per pair "
      "(median over 28 pairs; 'year' = 252 trading days)\n")
    cols = ["freq", "variant", "delta", "T_years_R1", "T_years_R1_direct",
            "T_years_R4", "T_years_R20", "T_years_R100", "T_years_Rinf",
            "R_within_10pct_median"]
    A(
        t3[cols]
        .rename(columns={
            "T_years_R1_direct": "T_years_R1 (no decomposition)",
            "R_within_10pct_median": "R for within 10% of floor",
        })
        .to_markdown(index=False, floatfmt=".2f")
    )

    d = t3[t3["freq"] == "daily"]
    ci_rows = []
    for r in d.itertuples():
        ci_rows.append(
            {
                "variant": r.variant,
                "delta": r.delta,
                "R=1": f"{r.T_years_R1:.2f} [{r.T_years_R1_lo:.2f}, {r.T_years_R1_hi:.2f}]",
                "R=4 (this arena)": f"{r.T_years_R4:.2f} [{r.T_years_R4_lo:.2f}, {r.T_years_R4_hi:.2f}]",
                "R=20": f"{r.T_years_R20:.2f} [{r.T_years_R20_lo:.2f}, {r.T_years_R20_hi:.2f}]",
                "R=inf (floor)": f"{r.T_years_Rinf:.2f} [{r.T_years_Rinf_lo:.2f}, {r.T_years_Rinf_hi:.2f}]",
            }
        )
    A("\n### F8 The same, daily, with 95% bootstrap intervals\n")
    A(pd.DataFrame(ci_rows).to_markdown(index=False))

    # ---------------------------------------------------------------- item 4
    s4 = pd.read_csv(os.path.join(DER, "i4_similarity_ci.csv"))

    def block(met, keys, rename=None):
        d = s4[(s4["metric"] == met) & (s4["quantity"].isin(keys))].copy()
        d["quantity"] = pd.Categorical(d["quantity"], categories=keys, ordered=True)
        d = d.sort_values("quantity")
        if rename:
            d["quantity"] = d["quantity"].map(rename).astype(str)
        return d[["quantity", "estimate", "ci_lo", "ci_hi", "boot_sd"]].to_markdown(
            index=False, floatfmt=".4f"
        )

    A("\n### F9 Headline similarity with 95% day-bootstrap intervals\n")
    names = {
        "within_mean": "different models, same arm",
        "across_mean": "same model, different arm",
        "diff": "difference",
    }
    for met, lab in [("exposure_corr", "aggregate signed-exposure correlation"),
                     ("direction_share", "same-direction share")]:
        A(f"\n**{lab}**\n")
        A(block(met, list(names), names))

    models = sorted(
        q.split("__", 1)[1]
        for q in s4[s4["quantity"].str.startswith("within__")]["quantity"].unique()
    )
    A("\n### F10 Similarity by model (exposure correlation)\n")
    rows = []
    for m in models:
        w = s4[(s4["metric"] == "exposure_corr") & (s4["quantity"] == f"within__{m}")].iloc[0]
        a = s4[(s4["metric"] == "exposure_corr") & (s4["quantity"] == f"across__{m}")].iloc[0]
        rows.append(
            {
                "model": m,
                "vs other models, same arm": f"{w.estimate:.3f} [{w.ci_lo:.3f}, {w.ci_hi:.3f}]",
                "vs itself, other arms": f"{a.estimate:.3f} [{a.ci_lo:.3f}, {a.ci_hi:.3f}]",
                "difference": f"{w.estimate - a.estimate:+.3f}",
            }
        )
    A(pd.DataFrame(rows).to_markdown(index=False))

    comps = [1, 2, 3, 4]
    A("\n### F11 Similarity by arm, so item 1's rule differences are visible\n")
    A("\n**different-model pairs, within each arm**\n")
    A(block("exposure_corr", [f"within_comp{c}" for c in comps],
            {f"within_comp{c}": f"arm {c}" for c in comps}))
    A("\n**same-model pairs, by which two arms**\n")
    keys = [f"across_c{a}c{b}" for a, b in itertools.combinations(comps, 2)]
    A(block("exposure_corr", keys,
            {f"across_c{a}c{b}": f"arms {a}+{b}" for a, b in itertools.combinations(comps, 2)}))

    # ---------------------------------------------------------------- item 5
    i5 = pd.read_csv(os.path.join(DER, "i5_icc_ci.csv"))
    A("\n### F12 ICC of S1.5 final returns, exact F-based 95% interval\n")
    A(
        i5[["model", "F", "df", "p_value", "ICC", "ICC_lo_exactF", "ICC_hi_exactF",
            "sd_model_pp", "sd_err_pp"]]
        .rename(columns={"model": "specification", "ICC_lo_exactF": "ICC_2.5%",
                         "ICC_hi_exactF": "ICC_97.5%"})
        .to_markdown(index=False, floatfmt=".3f")
    )

    with open(OUT, "w") as fh:
        fh.write("\n".join(parts) + "\n")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
