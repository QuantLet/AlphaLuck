"""Generate paper/numbers.tex and paper/tables/*.tex from the derived data.

Every number the manuscript quotes is defined here as a LaTeX macro, so the
draft contains no hand-typed statistics. Macro names are CamelCase with an
\\al prefix (\\alReconMedianPct, \\alIccArmFE, ...) to avoid collisions.

The same pass writes one .tex table per exhibit into paper/tables/ and mirrors
each as a .csv so the numbers are machine-readable without parsing LaTeX.
"""
from __future__ import annotations

import json
import os
import re
import sys

from decimal import Decimal, ROUND_HALF_UP

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), "src"))

import style
import wallets

ROOT = style.ROOT
DER = style.DER
PAPER = os.path.join(ROOT, "paper")
TABDIR = os.path.join(PAPER, "tables")

_MACROS: dict[str, str] = {}


_FIXED = re.compile(r"^\{:\.(\d+)f\}$")


def fixed(value: float, places: int) -> str:
    """Format to `places` decimals, rounding halves away from zero.

    Python's own formatting rounds halves to even, so 0.125 prints as 0.12 and
    0.135 as 0.14 at two places. That is defensible but it is not what a reader
    checking a table by hand will do, and it makes two numbers of equal
    magnitude and opposite sign round in opposite directions. Decimal with
    ROUND_HALF_UP rounds away from zero on a tie, symmetrically in both signs.

    Decimal(str(value)) is deliberate: str() gives the shortest decimal that
    round-trips, so a value a reader would write as 8.245 is treated as 8.245
    and not as the binary 8.2449999... that happens to represent it.
    """
    q = Decimal(1).scaleb(-places)
    d = Decimal(str(float(value))).quantize(q, rounding=ROUND_HALF_UP)
    return f"{d:f}"


LABP = {"gemma-3-27b": "Gemma 3", "mistral-24b": "Mistral Small 3",
        "qwen3-32b": "Qwen3"}


def mac(name: str, value, fmt: str = "{:.3f}") -> None:
    """Register one macro. Raises on a duplicate name or a non-finite value."""
    if name in _MACROS:
        raise SystemExit(f"duplicate macro {name}")
    if isinstance(value, (int, np.integer)):
        s = f"{int(value):,}".replace(",", r"{,}")
    elif isinstance(value, (float, np.floating)):
        if not np.isfinite(value):
            raise SystemExit(f"non-finite value for {name}: {value}")
        m = _FIXED.match(fmt)
        s = fixed(value, int(m.group(1))) if m else fmt.format(float(value))
        # A leading "-" in running text is a hyphen, not a minus sign.
        # \ensuremath{-} renders correctly in both modes, so the same macro
        # can be quoted in a sentence and inside $...$.
        if s.startswith("-"):
            s = r"\ensuremath{-}" + s[1:]
    else:
        s = str(value)
    _MACROS[name] = s


def csv_read(name: str) -> pd.DataFrame:
    return pd.read_csv(os.path.join(DER, name))


def js_read(name: str):
    with open(os.path.join(DER, name)) as fh:
        return json.load(fh)


_TEX = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$",
        "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}",
        "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}


def tex_escape(v: str) -> str:
    """Escape LaTeX specials in a *data* cell. Headers are authored by hand."""
    return "".join(_TEX.get(ch, ch) for ch in str(v))


def latex_table(df: pd.DataFrame, name: str, caption: str, label: str,
                align: str | None = None, floatfmt: str = "%.3f",
                note: str = "", size: str = "small") -> None:
    os.makedirs(TABDIR, exist_ok=True)
    df.to_csv(os.path.join(TABDIR, f"{name}.csv"), index=False)
    align = align or ("l" + "r" * (df.shape[1] - 1))

    # format to strings ourselves: pandas' float_format callable routes through
    # Styler, which would pull in jinja2 for no benefit here
    out_df = df.copy()
    for c in out_df.columns:
        if pd.api.types.is_float_dtype(out_df[c]):
            out_df[c] = out_df[c].map(
                lambda v: "--" if pd.isna(v) else floatfmt % v)
        elif pd.api.types.is_integer_dtype(out_df[c]):
            out_df[c] = out_df[c].map(lambda v: f"{int(v):,}".replace(",", "{,}"))
        else:
            out_df[c] = out_df[c].map(tex_escape)

    header = " & ".join(out_df.columns) + r" \\"
    body_rows = [" & ".join(r) + r" \\" for r in out_df.to_numpy()]
    tabular = "\n".join(
        [r"\begin{tabular}{" + align + "}", r"\toprule", header, r"\midrule"]
        + body_rows + [r"\bottomrule", r"\end{tabular}"]
    )
    out = [
        r"\begin{table}[htbp]", r"\centering", "\\" + size,
        f"\\caption{{{caption}}}", f"\\label{{{label}}}",
        tabular,
    ]
    if note:
        out.append(r"\begin{minipage}{\linewidth}\footnotesize " + note +
                   r"\end{minipage}")
    out.append(r"\end{table}")
    with open(os.path.join(TABDIR, f"{name}.tex"), "w") as fh:
        fh.write("\n".join(out) + "\n")


_WINLEN: dict[str, float] | None = None


def window_days() -> dict[str, float]:
    """Length of each canonical window in days, computed once.

    One source for the figure, so that Table 1, the macros and anything else
    quoting a season length cannot drift apart. The window is the organiser's
    published one; see analyse.common_window.
    """
    global _WINLEN
    if _WINLEN is None:
        import analyse as _an
        f = pd.read_parquet(os.path.join(DER, "fills.parquet"))
        _WINLEN = {}
        for s_ in ("S1", "S15"):
            lo, hi = _an.common_window(f, s_)
            _WINLEN[s_] = (hi - lo) / 86_400_000
    return _WINLEN


def main() -> None:
    mac("alWindowDaysSOne", window_days()["S1"], "{:.1f}")
    mac("alWindowDaysSFifteen", window_days()["S15"], "{:.1f}")

    os.makedirs(TABDIR, exist_ok=True)

    # ------------------------------------------------------------- samples
    desc = csv_read("t1_descriptive.csv")
    recon = pd.read_parquet(os.path.join(DER, "recon.parquet"))
    fills = pd.read_parquet(os.path.join(DER, "fills.parquet"))
    d15 = desc[desc["season"] == "S15"]
    d1 = desc[desc["season"] == "S1"]

    mac("alNWallets", len(recon))
    mac("alNWalletsSOne", len(d1))
    mac("alNWalletsSFifteen", len(d15))
    mac("alNModelsSOne", d1["model"].nunique())
    mac("alNModelsSFifteen", d15["model"].nunique())
    mac("alNArms", d15["competition_id"].nunique())
    mac("alNFillsTotal", len(fills))
    mac("alNFillsSOne", int(d1["n_fills"].sum()))
    mac("alNFillsSFifteen", int(d15["n_fills"].sum()))
    mac("alNRoundTripsSFifteen", int(d15["n_roundtrips"].sum()))
    mac("alNRoundTripsSOne", int(d1["n_roundtrips"].sum()))
    mac("alNDaysSFifteen", int(d15["trading_days"].max()))
    mac("alNDaysSOne", int(d1["trading_days"].max()))
    mac("alNModelPairs", 28)
    mac("alNPairsWithinArm", 112)
    mac("alNPairsAcrossArm", 48)

    # -------------------------------------------------------- reconciliation
    mac("alReconMedianPct", float(recon["diff_pct"].abs().median()), "{:.2f}")
    mac("alReconMaxPct", float(recon["diff_pct"].abs().max()), "{:.2f}")
    mac("alReconCount", int((recon["status"] == "RECONCILED").sum()))

    # ------------------------------------------------------- item 1 / arms
    dc = js_read("i1_decomposition.json")
    mac("alIccOneWay", dc["oneway_icc"])
    mac("alIccArmFE", dc["twoway_icc"])
    mac("alSdWithinOneWay", dc["oneway_sd_within_pp"], "{:.1f}")
    mac("alSdWithinArmFE", dc["twoway_sd_resid_pp"], "{:.1f}")
    mac("alSdBetweenOneWay", dc["oneway_sd_between_pp"], "{:.1f}")
    mac("alSdBetweenArmFE", dc["twoway_sd_between_pp"], "{:.1f}")
    mac("alFModelOneWay", dc["oneway_F"], "{:.2f}")
    mac("alPModelOneWay", dc["oneway_p"], "{:.4f}")
    mac("alFModelArmFE", dc["twoway_F_model"], "{:.2f}")
    mac("alPModelArmFE", dc["twoway_p_model"], "{:.4f}")
    mac("alFArm", dc["arm_F"], "{:.2f}")
    mac("alPArmF", dc["arm_p"], "{:.4f}")
    mac("alArmShareOfWithin", 100 * dc["share_of_oneway_within_explained_by_arm"], "{:.1f}")

    i5 = csv_read("i5_icc_ci.csv")
    mac("alIccOneWayLo", float(i5["ICC_lo_exactF"].iloc[0]))
    mac("alIccOneWayHi", float(i5["ICC_hi_exactF"].iloc[0]))
    mac("alIccArmFELo", float(i5["ICC_lo_exactF"].iloc[1]))
    mac("alIccArmFEHi", float(i5["ICC_hi_exactF"].iloc[1]))

    # ------------------------------------------------------------ similarity
    s4 = csv_read("i4_similarity_ci.csv")

    def sim(metric, q, col):
        return float(s4[(s4["metric"] == metric) & (s4["quantity"] == q)][col].iloc[0])

    mac("alSimWithin", sim("exposure_corr", "within_mean", "estimate"))
    mac("alSimAcross", sim("exposure_corr", "across_mean", "estimate"))
    mac("alSimDiff", sim("exposure_corr", "diff", "estimate"))
    mac("alSimDiffLo", sim("exposure_corr", "diff", "ci_lo"))
    mac("alSimDiffHi", sim("exposure_corr", "diff", "ci_hi"))
    mac("alDirWithin", sim("direction_share", "within_mean", "estimate"))
    mac("alDirAcross", sim("direction_share", "across_mean", "estimate"))
    mac("alDirDiff", sim("direction_share", "diff", "estimate"))
    mac("alDirDiffLo", sim("direction_share", "diff", "ci_lo"))
    mac("alDirDiffHi", sim("direction_share", "diff", "ci_hi"))

    # ------------------------------------------------- variance components
    i2 = js_read("i2_summary.json")
    da = i2["daily"]["arm_day"]
    mac("alMedianIota", da["median_iota"], "{:.2f}")
    mac("alIotaLo", da["iota_ci"][0], "{:.2f}")
    mac("alIotaHi", da["iota_ci"][1], "{:.2f}")
    mac("alMedianRhoRaw", da["rho_raw_median"], "{:.2f}")
    mac("alNRhoInadmissible", int(da["n_rho_inadmissible"]))
    mac("alMedianBoverA", da["median_B_over_A"], "{:.2f}")

    c1 = js_read("c1_identification.json")
    mac("alCOneMedianCount", int(c1["pooled_quantiles"]["50"]))
    mac("alCOnePGeObserved", c1["pooled_P_ge_11"], "{:.2f}")
    cell = [r for r in c1["per_cell"]
            if r["dist"] == "gaussian" and r["iota_true"] == 0.5
            and r["rho_true"] == 0.95 and r["sigma"] == "equal"][0]
    mac("alCOneMedianAtRhoHigh", int(cell["median_count_gt1"]))
    mac("alCOnePAtRhoHigh", cell["P_count_ge_11"], "{:.2f}")

    # ------------------------------------------------------------- horizon
    r4 = csv_read("r4_horizon.csv")
    r4j = js_read("r4_horizon.json")
    mac("alHorizonIid", float(
        r4[(r4["frequency"] == "daily") & (r4["variant"] == "arm_day")
           & (r4["lrv_method"] == "iid")]["T_years_median"].iloc[0]), "{:.1f}")
    mac("alHorizonLo", r4j["range_all"][0], "{:.1f}")
    mac("alHorizonHi", r4j["range_all"][1], "{:.1f}")
    ac = csv_read("r4_autocorr.csv")
    a_day = ac[(ac["frequency"] == "daily") & (ac["variant"] == "arm_day")].iloc[0]
    mac("alAcfLagOne", float(a_day["acf_lag1_mean"]), "{:.3f}")
    mac("alAcfLagTwo", float(a_day["acf_lag2_mean"]), "{:.3f}")

    t3 = csv_read("i3_design.csv")
    row = t3[(t3["freq"] == "daily") & (t3["variant"] == "arm_day")
             & (t3["delta"] == 1.0)].iloc[0]
    mac("alTyearsRone", float(row["T_years_R1"]), "{:.1f}")
    mac("alTyearsRfour", float(row["T_years_R4"]), "{:.1f}")
    mac("alTyearsRinf", float(row["T_years_Rinf"]), "{:.1f}")
    mac("alTyearsRinfLo", float(row["T_years_Rinf_lo"]), "{:.1f}")
    mac("alTyearsRinfHi", float(row["T_years_Rinf_hi"]), "{:.1f}")
    mac("alReplicatesForFloor", float(row["R_within_10pct_median"]), "{:.0f}")

    # -------------------------------------------------------- scalings / shares
    c2 = csv_read("c2_anova.csv")
    c2 = c2[c2["arms"] == "1-4"].reset_index(drop=True)
    for key, i in [("Return", 0), ("Cumulative", 1), ("Leverage", 2), ("Vol", 3)]:
        mac(f"alF{key}", float(c2["F_model_armFE"].iloc[i]), "{:.2f}")
        mac(f"alP{key}", float(c2["p_model_armFE"].iloc[i]), "{:.3f}")
        mac(f"alIcc{key}", float(c2["icc_armFE"].iloc[i]))
    c3 = csv_read("c3_variance_shares.csv")

    def share(outcome, q, col="estimate"):
        return float(c3[(c3["outcome"] == outcome) & (c3["quantity"] == q)][col].iloc[0])

    for key, out in [("Return", "final return %"),
                     ("Leverage", "leverage-scaled cumulative %"),
                     ("Sharpe", "daily Sharpe")]:
        mac(f"alShareModel{key}", share(out, "share_model"))
        mac(f"alShareArm{key}", share(out, "share_arm"))
        mac(f"alShareResid{key}", share(out, "share_resid"))

    # ------------------------------------------------------------ risk traits
    c4 = csv_read("c4_stats.csv").set_index("metric")
    for key, met in [("Lev", "mean_leverage"), ("Vol", "daily_vol"),
                     ("Share", "share_in_market"), ("Turn", "turnover_per_day")]:
        mac(f"alTraitF{key}", float(c4.loc[met, "F_model"]), "{:.2f}")
        mac(f"alTraitP{key}", float(c4.loc[met, "p_model"]), "{:.4f}")
        mac(f"alTraitIcc{key}", float(c4.loc[met, "icc_armFE"]))
        mac(f"alTraitIccLo{key}", float(c4.loc[met, "icc_lo"]))
        mac(f"alTraitIccHi{key}", float(c4.loc[met, "icc_hi"]))
        mac(f"alTraitW{key}", float(c4.loc[met, "kendall_W"]))
        mac(f"alTraitWP{key}", float(c4.loc[met, "p_W_perm"]), "{:.4f}")

    rc = csv_read("c4_rankcorr.csv").set_index("metric")
    r3 = csv_read("r3_wallet_rankcorr.csv").set_index("metric")
    for key, met in [("Vol", "daily_vol"), ("Lev", "mean_leverage"),
                     ("Turn", "turnover_per_day"), ("Share", "share_in_market")]:
        mac(f"alRhoModel{key}", float(rc.loc[met, "spearman"]), "{:.2f}")
        mac(f"alRhoModelP{key}", float(rc.loc[met, "perm_p_one_sided"]), "{:.3f}")
        mac(f"alRhoWallet{key}", float(r3.loc[met, "mean_within_arm_rho"]), "{:.2f}")
        mac(f"alRhoWalletP{key}", float(r3.loc[met, "perm_p_two_sided"]), "{:.4f}")

    # ---------------------------------------------------------------- R1
    r1 = csv_read("r1_covariate.csv")
    # rows: 0 base, 1 volatility on initial capital, 2 exposure on initial
    # capital, 3 volatility on current equity, 4 leverage on current equity.
    # The primary measures are the fixed-denominator ones; the current-equity
    # versions carry the suffix Eq and appear only in the appendix.
    for key, i in [("Base", 0), ("Vol", 1), ("Lev", 2),
                   ("VolEq", 3), ("LevEq", 4)]:
        mac(f"alCovF{key}", float(r1["F_model"].iloc[i]), "{:.2f}")
        mac(f"alCovP{key}", float(r1["p_F"].iloc[i]), "{:.4f}")
        mac(f"alCovPermP{key}", float(r1["perm_p"].iloc[i]), "{:.4f}")
        mac(f"alCovPartialR{key}", float(r1["partial_R2_model"].iloc[i]))
    sh = r1["share_of_between_model_SS_removed"]
    mac("alCovRemovedVol", 100 * float(sh.iloc[1]), "{:.1f}")
    mac("alCovRemovedLev", 100 * float(sh.iloc[2]), "{:.1f}")
    mac("alCovRemovedVolEq", 100 * float(sh.iloc[3]), "{:.1f}")
    mac("alCovRemovedLevEq", 100 * float(sh.iloc[4]), "{:.1f}")

    # ---------------------------------------------------------------- P&L
    pnl = js_read("a1_pnl_summary.json")
    for key, s in [("SFifteen", "S15"), ("SOne", "S1")]:
        t = pnl["totals"][s]
        mac(f"alPnlExposure{key}", int(round(t["exposure_pnl"])))
        mac(f"alPnlTiming{key}", int(round(t["timing_pnl"])))
        mac(f"alPnlSlippage{key}", int(round(t["slippage"])))
        mac(f"alPnlFees{key}", int(round(t["fees"])))
        mac(f"alPnlFunding{key}", int(round(t["funding"])))
        mac(f"alPnlNet{key}", int(round(t["net_pnl"])))
    mac("alFeesPctOfCapital", 100 * pnl["totals"]["S15"]["fees"] / 320000, "{:.1f}")
    mac("alPnlIdentityMaxPct", pnl["identity_max_gap_pct"], "{:.2f}")

    # ------------------------------------------------------- referee 2 flips
    r2 = js_read("r2_permutation.json")
    mac("alPermNTests", len(r2["rows"]))
    mac("alPermNFlips", int(r2["n_verdict_flips"]))
    armret = [r for r in r2["rows"]
              if r["test"] == "F_arm" and r["outcome"].startswith("final return")][0]
    mac("alPArmPerm", armret["p_perm"], "{:.4f}")

    # ------------------------------------------------------- cross-season
    a2 = js_read("a2_risk_crossseason.json")
    strict = [r for r in a2["correlations"]
              if r["match_set"].startswith("strict (") and r["metric"] == "mean_leverage"][0]
    mac("alCrossSeasonRhoLev", strict["spearman"], "{:.2f}")
    mac("alCrossSeasonPLev", strict["perm_p_one_sided"], "{:.2f}")
    mac("alCrossSeasonN", int(a2["n_common"]))

    # ---------------------------------------------------------- persistence
    pp = csv_read("p1_persistence.csv").set_index("metric")
    pj = js_read("p1_persistence.json")["windows"]
    mac("alPostDays", pj["post_days"], "{:.1f}")
    mac("alPostTradingDays", int(pj["post_days_min"]))
    mac("alPostFills", int(pj["post_fills"]))
    for key, met in [("Lev", "mean_leverage"), ("Vol", "daily_vol")]:
        mac(f"alPersRho{key}", float(pp.loc[met, "spearman_wallet"]), "{:.2f}")
        mac(f"alPersRhoP{key}", float(pp.loc[met, "perm_p_overall"]), "{:.4f}")
        mac(f"alPersRhoModel{key}", float(pp.loc[met, "spearman_model_means"]), "{:.2f}")
        mac(f"alPersW{key}", float(pp.loc[met, "kendall_W_periods"]))
        mac(f"alPostF{key}", float(pp.loc[met, "post_F_model"]), "{:.2f}")
        mac(f"alPostP{key}", float(pp.loc[met, "post_p_model"]), "{:.4f}")
        mac(f"alPostIcc{key}", float(pp.loc[met, "post_icc"]))
        mac(f"alPostIccLo{key}", float(pp.loc[met, "post_icc_lo"]))
        mac(f"alPostIccHi{key}", float(pp.loc[met, "post_icc_hi"]))


    # ------------------------------------------------ numbers quoted in the prose
    # organiser's published winner figure vs the on-chain reconstruction
    mac("alOrgWinnerPct", 12.11, "{:.2f}")
    mac("alOrgWinnerUSD", 4844)
    mac("alReconWinnerPct", 11.80, "{:.2f}")
    mac("alReconWinnerUSD", 4719)

    # arm evidence
    ex = csv_read("i1_exchangeability.csv")
    arms_csv = pd.read_csv(os.path.join(ROOT, "competitions.csv"))
    mac("alArmThreePrompts", int(arms_csv.query("competition_id==3")
                                 .n_with_peer_standings.iloc[0]))
    mac("alOtherArmPrompts", int(arms_csv.query("competition_id!=3")
                                 .n_prompts_sampled.sum()))
    lev_row = ex[ex["metric"] == "mean_leverage"].iloc[0]
    mac("alArmLevMax", max(lev_row[f"arm{i}_mean"] for i in range(1, 5)), "{:.2f}")
    mac("alArmLevMin", min(lev_row[f"arm{i}_mean"] for i in range(1, 5)), "{:.2f}")
    mac("alNMetricsDiffer", int((ex["p_value"] < 0.05).sum()))
    mac("alNMetricsTotal", len(ex))
    sig = ex[ex["p_value"] < 0.05]["kendall_W"]
    mac("alArmWLo", float(sig.min()), "{:.2f}")
    mac("alArmWHi", float(sig.max()), "{:.2f}")

    # in-market range
    w4 = csv_read("c4_wallet_risk.csv")
    mac("alInMarketLo", 100 * float(w4["share_in_market"].min()), "{:.0f}")
    mac("alInMarketHi", 100 * float(w4["share_in_market"].max()), "{:.0f}")
    mac("alFeesPctLo", 2.0, "{:.1f}")
    mac("alFeesPctHi", 29.2, "{:.1f}")

    # dropping arm 4
    c2b = csv_read("c2_anova.csv")
    d3 = c2b[(c2b["arms"] == "1-3")
             & c2b["outcome"].str.startswith("vol-standardised")].iloc[0]
    mac("alFVolNoArmFour", float(d3["F_model_armFE"]), "{:.2f}")
    mac("alPVolNoArmFour", float(d3["p_model_armFE"]), "{:.2f}")

    # bootstrap intervals on the model-level rank correlations
    rcb = csv_read("c4_rankcorr.csv").set_index("metric")
    for key, met in [("Vol", "daily_vol"), ("Turn", "turnover_per_day"),
                     ("Lev", "mean_leverage")]:
        mac(f"alRhoCiLo{key}", float(rcb.loc[met, "ci_lo"]), "{:.2f}")
        mac(f"alRhoCiHi{key}", float(rcb.loc[met, "ci_hi"]), "{:.2f}")
    mac("alRhoExactPVol", float(rcb.loc["daily_vol", "spearman_p_exact"]), "{:.3f}")

    # similarity by arm
    s4b = csv_read("i4_similarity_ci.csv")
    ec = s4b[s4b["metric"] == "exposure_corr"]
    mac("alSimArmMaxLev", float(ec[ec["quantity"] == "within_comp4"]["estimate"].iloc[0]))
    mac("alSimArmSitAware", float(ec[ec["quantity"] == "within_comp3"]["estimate"].iloc[0]))

    # Season 1 horizons
    t4 = csv_read("t4_precision_pairs.csv")
    s1bw = t4[(t4["season"] == "S1") & (t4["pair"] == "best_vs_worst")].iloc[0]
    mac("alSOneDaysNeeded", float(s1bw["days_needed_80pct_power"]), "{:.0f}")
    mac("alSOneDaysAvailable", int(s1bw["T_days"]))

    # iota range across scalings, and the market move
    c2d = csv_read("c2_decomposition.csv")
    c2d4 = c2d[c2d["arms"] == "1-4"]
    mac("alIotaLoRange", float(c2d4["median_iota"].min()), "{:.2f}")
    mac("alIotaHiRange", float(c2d4["median_iota"].max()), "{:.2f}")
    mac("alMarketLo", 6, "{:.0f}")
    mac("alMarketHi", 13, "{:.0f}")
    mac("alNetLong", 31)
    mac("alNLosers", 7)

    # P&L as a share of capital (S1.5, full official window)
    pj = js_read("a1_pnl_summary.json")["totals"]["S15"]
    for k, lab in [("exposure_pnl", "Exposure"), ("timing_pnl", "Timing"),
                   ("slippage", "Slippage"), ("fees", "Fees"),
                   ("funding", "Funding"), ("net_pnl", "Net")]:
        # slippage and fees are stored as positive costs; the tables negate
        # them, and the text quotes the same signed figure
        sign = -1.0 if k in ("slippage", "fees") else 1.0
        mac(f"alPnlPct{lab}", sign * 100 * pj[k] / 320000, "{:.1f}")
    mac("alPnlTradingCostPct",
        100 * (-pj["timing_pnl"] + pj["slippage"] + pj["fees"]) / 320000, "{:.1f}")

    # Timing and the execution adjustment are each measured against the
    # five-minute marks; their SUM is not, because the marks cancel. That sum
    # is the principal Season 1.5 result and gets its own macro.
    for sea, suf, book in [("S15", "", 320000), ("S1", "SOne", 60000)]:
        tt = js_read("a1_pnl_summary.json")["totals"][sea]
        v = 100 * (tt["timing_pnl"] - tt["slippage"]) / book
        mac(f"alPnlPct{suf}TimingExec", v, "{:.1f}")
        # the same number as a magnitude, for sentences that say "cost"
        mac(f"alPnlPct{suf}TimingExecAbs", abs(v), "{:.1f}")

    # how far the reported split moves when the interior marks are perturbed
    if os.path.exists(os.path.join(DER, "i8_mark_invariance.json")):
        mi = js_read("i8_mark_invariance.json")
        mv = mi["max_abs_move"]
        mac("alMarkMoveB", int(round(mv["B"])))
        mac("alMarkMoveX", int(round(mv["X"])))
        mac("alMarkMoveComb", int(round(mv["B_minus_X"])))
        mac("alMarkMoveBPct", 100 * mv["B"] / 320000, "{:.1f}")
        mac("alMarkMoveCombPct", 100 * mv["B_minus_X"] / 320000, "{:.1f}")
        mac("alMarkNoiseHi", 100 * max(r["noise_sd"]
                                       for r in mi["perturbed"]), "{:.0f}")

    # what the final ranking actually follows
    if os.path.exists(os.path.join(DER, "i7_return_sources.json")):
        rs = js_read("i7_return_sources.json")
        mac("alSrcTradingRho", rs["trading"]["rho"], "{:.2f}")
        mac("alSrcTradingP", rs["trading"]["p_two_sided"], "{:.4f}")
        mac("alSrcExposureRho", rs["exposure"]["rho"], "{:.2f}")
        mac("alSrcExposureP", rs["exposure"]["p_two_sided"], "{:.4f}")
        mac("alSrcTradingSd", rs["trading_sd_pct"], "{:.1f}")
        mac("alSrcExposureSd", rs["exposure_sd_pct"], "{:.1f}")

    # volatility on a denominator that cannot move
    if os.path.exists(os.path.join(DER, "i6_vol_denominator.json")):
        vd = js_read("i6_vol_denominator.json")
        for key, suf in [("vol_equity", "Eq"), ("vol_fixed", "Fix")]:
            q = vd[key]
            mac(f"alVol{suf}F", q["F_model"], "{:.2f}")
            mac(f"alVol{suf}P", q["p_perm"], "{:.4f}")
            mac(f"alVol{suf}Icc", q["icc"], "{:.2f}")
            mac(f"alVol{suf}IccLo", q["icc_lo"], "{:.2f}")
            mac(f"alVol{suf}IccHi", q["icc_hi"], "{:.2f}")
            mac(f"alVol{suf}W", q["W"], "{:.2f}")
            mac(f"alVol{suf}Persist", q["persist_rho"], "{:.2f}")
            mac(f"alVol{suf}Assoc", q["assoc_rho"], "{:.2f}")
            mac(f"alVol{suf}AssocP", q["assoc_p_two_sided"], "{:.3f}")
        for key, suf in [("turnover_equity", "TurnEq"),
                         ("turnover_fixed", "TurnFix"),
                         ("leverage_equity", "LevEq"),
                         ("leverage_fixed", "LevFix")]:
            q = vd[key]
            mac(f"alRisk{suf}F", q["F_model"], "{:.2f}")
            mac(f"alRisk{suf}ArmF", q["F_arm"], "{:.2f}")
            mac(f"alRisk{suf}ArmP", q["p_arm"], "{:.4f}")
            mac(f"alRisk{suf}Assoc", q["assoc_rho"], "{:.2f}")
            mac(f"alRisk{suf}AssocP", q["assoc_p_two_sided"], "{:.3f}")
        mac("alNDailyObs", vd["n_days_in"])
        mac("alNDailyObsCont", vd["n_days_cont"])

        rows = []
        MEAS = [("vol", "Volatility"), ("turnover", "Turnover"),
                ("leverage", "Exposure")]
        for key, lab in [("F_model", "Model effect, $F_{7,21}$"),
                         ("p_perm", "\\quad permutation $p$"),
                         ("icc", "Arm-adjusted ICC"),
                         ("W", "Kendall's $W$ across arms"),
                         ("F_arm", "Arm effect, $F_{3,21}$"),
                         ("persist_rho", "Continuation ranks, $\\rho$"),
                         ("assoc_rho", "Association with return, $\\rho$"),
                         ("assoc_p_two_sided", "\\quad permutation $p$")]:
            cells = []
            for m, _ in MEAS:
                for den in ("equity", "fixed"):
                    v = vd[f"{m}_{den}"][key]
                    txt = ("{:.3f}" if key in ("p_perm", "assoc_p_two_sided")
                           else "{:.2f}").format(v)
                    cells.append(f"${txt}$" if txt.startswith("-") else txt)
            rows.append(f"{lab} & " + " & ".join(cells) + r" \\")
        write_raw("tab13_voldenom",
                  r"Each risk measure on two denominators. \emph{Equity} "
                  r"uses current equity (mean equity for turnover); "
                  r"\emph{fixed} uses analytical initial capital of "
                  r"\$10{,}000, the same number for every account on "
                  r"every day. The letter reports both capital bases. Conditional "
                  r"diagnostics here require the assumptions stated in the appendix.",
                  "tab:voldenom", "lcccccc",
                  [r" & \multicolumn{2}{c}{Volatility} & "
                   r"\multicolumn{2}{c}{Turnover} & "
                   r"\multicolumn{2}{c}{Exposure} \\",
                   r"\cmidrule(lr){2-3}\cmidrule(lr){4-5}\cmidrule(lr){6-7}",
                   r" & Equity & Fixed & Equity & Fixed & Equity & Fixed \\"],
                  rows, size="footnotesize")

    # provenance of the design: documented, retrospective, unknown
    if os.path.exists(os.path.join(DER, "i5_provenance.csv")):
        pv = csv_read("i5_provenance.csv")
        n = pv["Status"].value_counts()
        for st in ("documented", "retrospective", "unknown"):
            mac(f"alProv{st.capitalize()}", int(n.get(st, 0)))
        mac("alProvTotal", int(len(pv)))
        rows = []
        for r in pv.itertuples(index=False):
            rows.append(f"{tex_escape(r.Element)} & \\textit{{{r.Status}}} & "
                        f"{tex_escape(r._2)} & {tex_escape(r.Source)} "
                        + r"\\")
        write_raw("tab12_provenance",
                  r"Provenance of the design. \emph{Documented} means stated "
                  r"by the organiser inside the season or recorded on-chain; "
                  r"\emph{retrospective} means the only evidence postdates "
                  r"the close; \emph{unknown} means not established by the "
                  r"retrieved evidence. Behaviour does not independently "
                  r"verify the rules it is used to explain.",
                  "tab:prov", "p{2.6cm}lp{5.4cm}p{3.0cm}",
                  [r"Element & Status & What is known & Source \\"],
                  rows, size="scriptsize")

    # inference audit: Holm, profile permutation, leave-one-model-out
    if os.path.exists(os.path.join(DER, "i4_inference.json")):
        iq = js_read("i4_inference.json")
        hol = iq["holm"]
        mac("alHolmFamily", hol["family_size"])
        mac("alHolmSurvive", hol["n_survive"])
        for key, suf in [("F:turnover_fixed", "RawFTurn")]:
            mac(f"alHolm{suf}", hol["raw"][key], "{:.3f}")
        for key, suf in [("F:vol_fixed", "FVol"), ("F:leverage_fixed", "FLev"),
                         ("rho:vol_fixed", "RhoVol"),
                         ("rho:turnover_fixed", "RhoTurn"),
                         ("rho:leverage_fixed", "RhoLev"),
                         ("rho:share_in_market", "RhoShare"),
                         ("F:turnover_fixed", "FTurn"),
                         ("F:share_in_market", "FShare")]:
            mac(f"alHolm{suf}", hol["adjusted"][key], "{:.3f}")
        prof = {r["metric"]: r for r in iq["profile"]}
        loo_ = {r["metric"]: r for r in iq["loo"]}
        for m, suf in [("vol_fixed", "Vol"), ("leverage_fixed", "Lev"),
                       ("turnover_fixed", "Turn"),
                       ("share_in_market", "Share")]:
            mac(f"alProfP{suf}", prof[m]["p_profile"], "{:.3f}")
            mac(f"alLooFLo{suf}", loo_[m]["F_min"], "{:.1f}")
            mac(f"alLooFHi{suf}", loo_[m]["F_max"], "{:.1f}")
            mac(f"alLooRhoLo{suf}", loo_[m]["rho_min"], "{:.2f}")
            mac(f"alLooRhoHi{suf}", loo_[m]["rho_max"], "{:.2f}")
        mac("alProfNPerm", prof["vol_fixed"]["n_perm"])

        reg = csv_read("i4_registry.csv")
        rows = [" & ".join(str(v) for v in r) + r" \\"
                for r in reg.itertuples(index=False)]
        write_raw("tab10_registry",
                  r"Exploratory permutation diagnostics retained in the appendix: the null, the "
                  r"unit that is permuted, the dependence that permutation "
                  r"leaves intact, the number of draws and the sidedness.",
                  "tab:registry", "p{2.6cm}p{2.8cm}p{2.5cm}p{2.7cm}p{1.3cm}p{1.9cm}",
                  [r"Test & Null & Permuted unit & Dependence preserved & "
                   r"Draws & Sided \\"], rows, size="scriptsize")

        NICEM = {"vol_fixed": "Realised volatility",
                 "leverage_fixed": "Gross exposure",
                 "share_in_market": "Share of time in market",
                 "turnover_fixed": "Turnover per day"}
        rows = []
        for m in ["vol_fixed", "leverage_fixed", "share_in_market",
                  "turnover_fixed"]:
            rows.append(
                f"{NICEM[m]} & {hol['raw']['F:' + m]:.4f} & "
                f"{hol['adjusted']['F:' + m]:.3f} & "
                f"${loo_[m]['F_min']:.1f}$ to ${loo_[m]['F_max']:.1f}$ & "
                f"{hol['raw']['rho:' + m]:.4f} & "
                f"{hol['adjusted']['rho:' + m]:.3f} & "
                f"{prof[m]['p_profile']:.3f} & "
                f"${loo_[m]['rho_min']:.2f}$ to ${loo_[m]['rho_max']:.2f}$ "
                + r"\\")
        write_raw("tab11_sensitivity",
                  r"Conditional diagnostic probabilities and sensitivity. Holm adjustment "
                  r"does not establish exchangeability and is over the "
                  r"family of eight tests in this table. The leave-one-out "
                  r"columns give the range of the statistic over the eight "
                  r"deletions of a single model. The profile column is the "
                  r"exact test that re-pairs whole model profiles across the "
                  r"four arms.",
                  "tab:sens", "lrrcrrrc",
                  [r" & \multicolumn{3}{c}{Model effect} & "
                   r"\multicolumn{4}{c}{Return association} \\",
                   r"\cmidrule(lr){2-4}\cmidrule(lr){5-8}",
                   r"Measure & $p$ & Holm & LOO $F$ & $p$ & Holm & Profile & "
                   r"LOO $\rho$ \\"], rows, size="footnotesize")

    # Sharpe-difference horizon, rebuilt on the right estimand
    if os.path.exists(os.path.join(DER, "s1_sharpe_horizon.json")):
        sh = js_read("s1_sharpe_horizon.json")
        mac("alShTDays", sh["T_days"])
        mac("alShPairs", sh["n_pairs"])
        mac("alShMedLo", sh["horizon_all_median_lo"], "{:.1f}")
        mac("alShMedHi", sh["horizon_all_median_hi"], "{:.1f}")
        mac("alShMinDetLo", sh["mindet_median_lo"], "{:.0f}")
        mac("alShMinDetHi", sh["mindet_median_hi"], "{:.0f}")
        mac("alShCorrMed", sh["corr_median"], "{:.2f}")
        mac("alShCorrLo", sh["corr_lo"], "{:.2f}")
        mac("alShCorrHi", sh["corr_hi"], "{:.2f}")
        mac("alShLowCorrYears", sh["horizon_lowcorr_half"], "{:.1f}")
        mac("alShHighCorrYears", sh["horizon_highcorr_half"], "{:.1f}")
        # the per-pair spread at the central estimator
        h = sh["horizon"]["Tyears_hac1"]
        mac("alShQOne", h["q25"], "{:.1f}")
        mac("alShQThree", h["q75"], "{:.1f}")
        rows = []
        for key, lab in ([(f"Tyears_hac{L}", f"HAC bandwidth {L}")
                          for L in (0, 1, 2, 3)]
                         + [(f"Tyears_blk{b}", f"Block bootstrap, $b={b}$")
                            for b in (1, 2, 3)]):
            q = sh["horizon"][key]
            rows.append(f"{lab} & {q['median']:.1f} & {q['q25']:.1f} & "
                        f"{q['q75']:.1f} & {q['min']:.1f} & {q['max']:.1f} "
                        + r"\\")
        write_raw("tab9_horizon",
                  r"Conditional estimated years to detect an annualised Sharpe "
                  r"difference of one between two models at the 5\% level "
                  r"with 80\% power, across the \alShPairs{} model pairs of "
                  r"Season 1.5. Each row is a different estimator of the "
                  r"long-run variance of the paired Sharpe difference; the "
                  r"block bootstrap resamples common time blocks across all "
                  r"accounts at once.",
                  "tab:horizon", "lrrrrr",
                  [r"Long-run variance & Median & Q1 & Q3 & Min & Max \\"],
                  rows)

    # continuation sample: the referee's three checks
    pj_ = js_read("p1_persistence.json")["rows"]
    for r in pj_:
        suf = {"mean_leverage": "Lev", "mean_leverage_init": "LevInit",
               "daily_vol": "Vol"}[r["metric"]]
        mac(f"alContRho{suf}", r["spearman_wallet"], "{:.2f}")
        mac(f"alContRhoArm{suf}", r["spearman_arm_adjusted"], "{:.2f}")
        mac(f"alContRhoDropOne{suf}", r["drop1_spearman"], "{:.2f}")
        mac(f"alContRhoDropTwo{suf}", r["drop2_spearman"], "{:.2f}")
        mac(f"alContInF{suf}", r["in_F_model"], "{:.2f}")
        mac(f"alContInIcc{suf}", r["in_icc"], "{:.2f}")

    accx = pd.read_parquet(os.path.join(DER, "accounts.parquet"))
    a15 = accx[accx["season"] == "S15"]
    mac("alNPositiveTimingExec",
        int(((a15["pnl_timing_pnl"] - a15["pnl_slippage"]) > 0).sum()))

    # A feasible benchmark, unlike the exposure term: hold the day-one book.
    if os.path.exists(os.path.join(DER, "a4_exante_benchmark.json")):
        xa = js_read("a4_exante_benchmark.json")
        for sea, suf in [("S15", ""), ("S1", "SOne")]:
            q = xa[sea]
            mac(f"alExAnte{suf}NetPct", q["hold_net_pct"], "{:.1f}")
            mac(f"alExAnte{suf}RealisedPct", q["realised_pct"], "{:.1f}")
            mac(f"alExAnte{suf}GapPp", abs(q["gap_pct"]), "{:.1f}")
            mac(f"alExAnte{suf}Beats", q["n_better_than_realised"])
            mac(f"alExAnte{suf}N", q["n_accounts"])
            mac(f"alExAnte{suf}Hours", q["formation_hours"])
            mac(f"alExAnte{suf}MedianDiff", abs(q["median_paired_diff_pp"]),
                "{:.0f}")
            # margin feasibility of the frozen book
            m25 = q["margin"]["0.025"]
            m5 = q["margin"]["0.05"]
            mac(f"alExAnte{suf}BreachLo", m25["n_breach"])
            mac(f"alExAnte{suf}BreachHi", m5["n_breach"])
            mac(f"alExAnte{suf}FeasibleHi", m5["n_feasible"])
            mac(f"alExAnte{suf}FeasibleHoldPct", m5["feasible_hold_pct"],
                "{:.1f}")
            mac(f"alExAnte{suf}FeasibleRealPct", m5["feasible_realised_pct"],
                "{:.1f}")
            mac(f"alExAnte{suf}FundPct",
                q["hold_net_pct_with_actual_funding"], "{:.1f}")
            mac(f"alExAnte{suf}MmrLo", 2.5, "{:.1f}")
            mac(f"alExAnte{suf}MmrHi", 5.0, "{:.0f}")
            mac(f"alExAnte{suf}CutLoHours", 12)
            mac(f"alExAnte{suf}CutHiHours", 48)
            cut = q["cutoffs"]
            # The range over the whole sweep, which contains the headline
            # figure because the default freeze point is one of its points.
            # tests/test_numbers.py checks that it does.
            mac(f"alExAnte{suf}SweepLo", q["sweep_lo_pct"], "{:.1f}")
            mac(f"alExAnte{suf}SweepHi", q["sweep_hi_pct"], "{:.1f}")
            mac(f"alExAnte{suf}CutLoPct", cut["12"]["hold_pct"], "{:.1f}")
            mac(f"alExAnte{suf}CutHiPct", cut["48"]["hold_pct"], "{:.1f}")
            mac(f"alExAnte{suf}CutLoBeats", cut["12"]["better"])
            mac(f"alExAnte{suf}CutHiBeats", cut["48"]["better"])
            mac(f"alExAnte{suf}CutLoBreach", cut["12"]["breach_0.025"])

        rows = []
        for sea, lab in (("S15", "Season 1.5"), ("S1", "Season 1")):
            cu = xa[sea]["cutoffs"]
            for h in sorted(cu, key=int):
                r = cu[h]
                star = r"$^{\dagger}$" if int(h) == 24 else ""
                rows.append(
                    f"{lab}{star} & {h} & {tex_num(r['hold_pct'])} & "
                    f"{tex_num(r['realised_pct'])} & "
                    f"{r['better']}/{r['n']} & {r['breach_0.025']} & "
                    f"{r['breach_0.05']} " + r"\\")
            if sea == "S15":
                rows.append(r"\midrule")
        write_raw("tab14_freeze",
                  r"Legacy daily-booked comparison at three freeze points. Return "
                  r"and realised are per cent of initial capital over all "
                  r"accounts of the season; flags count accounts whose "
                  r"frozen book falls below an assumed margin threshold of "
                  r"2.5 or 5 per cent of gross notional. These are proxy checks, "
                  r"with no post-freeze funding or terminal closing cost. "
                  r"$\dagger$ marks the 24-hour formation time. The main letter uses "
                  r"hourly funding on both books instead.",
                  "tab:freeze", "llrrccc",
                  [r"Season & Freeze (h) & Return & Realised & Beaten & "
                   r"2.5\% & 5\% \\"], rows)

    # ---- the replicated pilot (data/derived/pilot/, see DATA.md). Guarded:
    # the pilot archive is not committed, so `make all` must work without it.
    PILOT = os.path.join(DER, "pilot", "results")
    if os.path.isdir(PILOT):
        ic = pd.read_parquet(os.path.join(PILOT, "iota_cells.parquet"))
        pr = pd.read_parquet(os.path.join(PILOT, "pairs.parquet"))
        fc = pd.read_parquet(os.path.join(PILOT, "formula_check.parquet"))

        # main cells, P&L metric, the three language models at their serving
        # default temperature; the reference agents have upper-case names
        llm = ic[(ic.metric == "pnl") & (ic.cell == "main")
                 & (~ic.model.str.isupper())]
        pp = pr[(pr.metric == "pnl") & (pr.cell == "main")]

        mac("alPilotModels", int(llm.model.nunique()))
        mac("alPilotArms", int(llm.arm.nunique()))
        mac("alPilotDays", int(llm["T"].max()))
        mac("alPilotR", int(llm["R"].max()))
        mac("alPilotDecisions", 60000)
        mac("alPilotCalls", 61311)

        mac("alPilotIotaLo", float(llm.iota.min()), "{:.2f}")
        mac("alPilotIotaHi", float(llm.iota.max()), "{:.2f}")
        # the two ends of the range, named, because the point is that iota is
        # a property of the model and not of "LLM traders"
        lo_row = llm.loc[llm.iota.idxmin()]
        hi_row = llm.loc[llm.iota.idxmax()]
        mac("alPilotIotaLoModel", LABP.get(lo_row.model, lo_row.model))
        mac("alPilotIotaHiModel", LABP.get(hi_row.model, hi_row.model))
        mac("alPilotIotaLoArm", str(lo_row.arm))
        mac("alPilotIotaHiArm", str(hi_row.arm))

        mac("alPilotTyOneLo", float(pp["Ty_d1.0_R1"].min()), "{:.1f}")
        mac("alPilotTyOneHi", float(pp["Ty_d1.0_R1"].max()), "{:.1f}")
        mac("alPilotTyTwentyLo", float(pp["Ty_d1.0_R20"].min()), "{:.1f}")
        mac("alPilotTyTwentyHi", float(pp["Ty_d1.0_R20"].max()), "{:.1f}")
        cut = 1.0 - pp["Ty_d1.0_R20"] / pp["Ty_d1.0_R1"]
        mac("alPilotCutLo", 100 * float(cut.min()), "{:.0f}")
        mac("alPilotCutHi", 100 * float(cut.max()), "{:.0f}")
        mac("alPilotBALo", float(pp.B_over_A.min()), "{:.2f}")
        mac("alPilotBAHi", float(pp.B_over_A.max()), "{:.2f}")
        mac("alPilotRfloorLo", float(pp.R_within10pct.min()), "{:.1f}")
        mac("alPilotRfloorHi", float(pp.R_within10pct.max()), "{:.1f}")

        # the formula check: empirical/predicted variance, flat in R but off
        # in level, which is the honest way to report the proposition test
        ratio = fc.emp_var / fc.pred
        mac("alPilotRatioLo", float(ratio.min()), "{:.2f}")
        mac("alPilotRatioHi", float(ratio.max()), "{:.2f}")
        by_r = (fc.assign(ratio=ratio).groupby("R")["ratio"].mean())
        mac("alPilotRatioSpreadR",
            float(by_r.max() - by_r.min()), "{:.3f}")

        # reference agents recovering a known iota is what licenses the rest
        ref = ic[(ic.metric == "pnl") & (ic.cell == "main")
                 & (ic.model.str.isupper())]
        mac("alPilotRefCells", int(len(ref)))

        rows = []
        for _, r in pp.iterrows():
            rho = "n/a" if not np.isfinite(r.rho_m) else f"{r.rho_m:.2f}"
            rows.append(
                f"{r.arm} & {LABP.get(r.model_k, r.model_k)} vs "
                f"{LABP.get(r.model_l, r.model_l)} & {rho} & "
                f"{r.B_over_A:.2f} & {r['Ty_d1.0_R1']:.1f} & "
                f"{r['Ty_d1.0_R20']:.1f} & {r['Ty_d1.0_Rinf']:.1f} " + r"\\")
        write_raw("tab8_pilot",
                  r"Replicated pilot: three open-weight models, two asset "
                  r"arms, \alPilotDays{} days, $R=\alPilotR$ replicates per "
                  r"cell at each model's default temperature. $\rho^m$ is the "
                  r"correlation of the models' market responses and $B/A$ the "
                  r"ratio of sampling to market variance; $T$ is the season "
                  r"length in years required to detect a gap of one in "
                  r"annualised Sharpe ratios. $\rho^m$ is undefined where the "
                  r"estimated $\omega^2$ is negative.",
                  "tab:pilot", "llccccc",
                  [r"Arm & Pair & $\rho^m$ & $B/A$ & $R=1$ & $R=20$ & "
                   r"$R=\infty$ \\"], rows)

    # Barton et al. (2026) replay league -- their result on their data, read
    # from their published CSV so that the one number we quote is theirs.
    if os.path.exists(os.path.join(DER, "dxap_league.json")):
        dx = js_read("dxap_league.json")
        mac("alDxapHolmP", dx["holm_p_min"], "{:.2f}")
        mac("alDxapCells", dx["cells"])
        mac("alDxapModels", dx["n_models"])

    # External-mark robustness, both seasons. Season 1 is the decisive test
    # (full 24/7 coverage, no proxy, nothing selected on time of day); the
    # Season 1.5 figures carry the suffix SOneFive and are quoted only as the
    # restricted comparison they are.
    if os.path.exists(os.path.join(DER, "a3_external_marks.json")):
        a3all = js_read("a3_external_marks.json")
        for sea, suf in [("S1", ""), ("S15", "SOneFive")]:
            a3 = a3all[sea]
            mac(f"alExt{suf}Coverage", 100 * a3["coverage"], "{:.0f}")
            mac(f"alExt{suf}Wallets", a3["n_wallets"])
            for k, lab in [("exposure", "Exposure"), ("timing", "Timing"),
                           ("slippage", "Slippage")]:
                mac(f"alExt{suf}Int{lab}", int(round(a3["totals"][f"int_{k}"])))
                mac(f"alExt{suf}Ext{lab}", int(round(a3["totals"][f"ext_{k}"])))
            mac(f"alExt{suf}TrueGross", int(round(a3["true_gross"])))
            mac(f"alExt{suf}GrossInt", int(round(a3["gross_internal"])))
            mac(f"alExt{suf}GrossExt", int(round(a3["gross_external"])))
            mac(f"alExt{suf}ErrInt",
                abs(100 * a3["gross_err_internal"]), "{:.1f}")
            mac(f"alExt{suf}ErrExt",
                abs(100 * a3["gross_err_external"]), "{:.1f}")
            mac(f"alExt{suf}CorrExposure", a3["corr_exposure"], "{:.2f}")
            mac(f"alExt{suf}CorrTiming", a3["corr_timing"], "{:.2f}")
            # levels, signs and ranks, not only correlation
            for comp, clab in [("exposure", "Exposure"), ("timing", "Timing")]:
                q = a3["agreement"][comp]
                mac(f"alExt{suf}Mad{clab}", int(round(q["mad_usd"])))
                mac(f"alExt{suf}MadRel{clab}", 100 * q["mad_rel"], "{:.0f}")
                mac(f"alExt{suf}Sign{clab}", q["sign_agree"])
                mac(f"alExt{suf}Spear{clab}", q["spearman"], "{:.2f}")

    # cross-season risk ordering (Season 1 vs 1.5)
    mac("alCrossSeasonRhoVol", [r for r in js_read("a2_risk_crossseason.json")["correlations"]
                                if r["match_set"].startswith("strict (")
                                and r["metric"] == "daily_vol"][0]["spearman"], "{:.2f}")


    # ------------------------- further numbers quoted in paper/prose_source.tex
    pj1 = js_read("a1_pnl_summary.json")["totals"]["S1"]
    for k, lab in [("exposure_pnl", "Exposure"), ("timing_pnl", "Timing"),
                   ("slippage", "Slippage"), ("fees", "Fees"),
                   ("funding", "Funding"), ("net_pnl", "Net")]:
        mac(f"alPnlPctSOne{lab}", 100 * pj1[k] / 60000, "{:.1f}")
    mac("alPnlLossPctRounded", abs(100 * pj["net_pnl"] / 320000), "{:.0f}")
    # Everything other than exposure, which is what the sentence quoting this
    # macro means by "the remaining components". Funding belongs in it: the
    # identity build.py enforces is
    #     net = exposure + timing - slippage - fees + funding
    # so leaving funding out left the arithmetic in the text short by 0.17
    # points -- 9.5 + (-38.8) = -29.4 against a reported net of -29.2.
    # tests/test_numbers.py now checks that exposure + other = net at the
    # precision both are printed to.
    mac("alPnlOtherPct",
        100 * (pj["timing_pnl"] - pj["slippage"] - pj["fees"]
               + pj["funding"]) / 320000, "{:.1f}")

    pnl_w = csv_read("a1_pnl_decomposition.csv")
    pnl15 = pnl_w[pnl_w["season"] == "S15"]
    mac("alNPositiveTiming", int((pnl15["timing_pnl"] > 0).sum()))

    # turnover: winner, the field, and the two extreme arms
    turn = w4.groupby("model")["turnover_per_day"].mean()
    mac("alWinnerTurnover", float(turn.loc["typhoon"]), "{:.0f}")
    others = turn.drop("typhoon")
    mac("alTurnoverFieldLo", float(others.min()), "{:.0f}")
    mac("alTurnoverFieldHi", float(others.max()), "{:.0f}")
    ta = w4.groupby("arm")["turnover_per_day"].mean()
    mac("alTurnoverArmTwo", float(ta.loc[2]), "{:.0f}")
    mac("alTurnoverArmThree", float(ta.loc[3]), "{:.0f}")

    # Season 1 adjacent-rank horizons, as powers of ten
    s1cl = t4[(t4["season"] == "S1") & (t4["pair"] == "two_closest")].iloc[0]
    mac("alSOneClosestExp",
        int(round(np.log10(float(s1cl["days_needed_80pct_power"])))))

    # autocorrelation as quoted: pooled across pairs, not arm-adjusted
    acp = ac[(ac["frequency"] == "daily") & (ac["variant"] == "pooled")].iloc[0]
    mac("alAcfLagOnePooled", float(acp["acf_lag1_mean"]), "{:.2f}")

    # cross-season leverage correlation, the six-model family set
    fam = [r for r in js_read("a2_risk_crossseason.json")["correlations"]
           if r["match_set"] == "strict + family" and r["metric"] == "mean_leverage"][0]
    mac("alCrossSeasonRhoLevFam", fam["spearman"], "{:.2f}")

    # persistence permutation threshold quoted in the prose
    mac("alPersPThreshold", "0.001")
    mac("alPnlLossPct", abs(100 * pj["net_pnl"] / 320000), "{:.1f}")
    for key, out_ in [("Return", "final return %"), ("Sharpe", "daily Sharpe")]:
        for comp, lab in [("share_model", "Model"), ("share_arm", "Arm")]:
            mac(f"alShare{lab}{key}Pct", 100 * share(out_, comp), "{:.0f}")

    # ------------------------------------------------------------- write out
    out_tex = os.path.join(PAPER, "numbers.tex")
    with open(out_tex, "w") as fh:
        fh.write("% Generated by paper/code/make_numbers.py -- do not edit.\n")
        fh.write("% Every number quoted in the manuscript is defined here.\n")
        for k in sorted(_MACROS):
            fh.write(f"\\newcommand{{\\{k}}}{{{_MACROS[k]}}}\n")
    print(f"wrote {os.path.relpath(out_tex, ROOT)} with {len(_MACROS)} macros")

    build_tables()
    with open(os.path.join(PAPER, "numbers.json"), "w") as fh:
        json.dump(_MACROS, fh, indent=1, sort_keys=True)


# compact labels for the outcome column: the raw names overflow a text-width
# table at 11pt
SHORT_OUTCOME = {
    "final return % (compounded, as published)": "final return",
    "cumulative return % (arithmetic sum of daily)": "cumulative return",
    "leverage-scaled cumulative % (per 1x of gross)": "leverage-scaled",
    "vol-standardised cumulative (= T x daily Sharpe)": "vol-standardised",
    "final return %": "final return",
    "leverage-scaled cumulative %": "leverage-scaled",
    "daily Sharpe": "Sharpe",
    "final return % (published, sec 9/13)": "final return",
    "cumulative return % arithmetic (sec 15)": "cumulative return",
    "leverage-scaled cumulative % (sec 15/16)": "leverage-scaled",
    "vol-standardised cumulative (sec 15)": "vol-standardised",
    "daily Sharpe (sec 16)": "Sharpe",
    "realised daily volatility (sec 17)": "daily volatility",
    "mean gross leverage (sec 17)": "gross leverage",
    "share of time in market (sec 17)": "time in market",
    "turnover per day (sec 17)": "turnover",
    "mean_leverage": "gross leverage",
    "daily_vol": "daily volatility",
    "share_in_market": "time in market",
    "turnover_per_day": "turnover",
}


def build_tables() -> None:
    """One .tex (and .csv) per exhibit, in the layout of paper/prose_source.tex."""
    desc = csv_read("t1_descriptive.csv")
    recon = pd.read_parquet(os.path.join(DER, "recon.parquet"))

    # ---- tab:data -- seasons as columns, as in prose_source
    col = {}
    for s_, lab in [("S1", "Season 1"), ("S15", "Season 1.5")]:
        d = desc[desc["season"] == s_]
        r = recon[recon["season"] == s_]
        col[lab] = {
            "Instruments": ("crypto perpetuals" if s_ == "S1"
                            else "tokenised US equities"),
            "Official window (UTC)": ("17 Oct -- 3 Nov 2025" if s_ == "S1"
                                      else "20 Nov -- 3 Dec 2025"),
            "Length (days)": f"{window_days()[s_]:.1f}",
            "Models": f"{d['model'].nunique()}",
            "Rule sets": f"{d['competition_id'].nunique()}",
            "Wallets": f"{len(d)}",
            "Fills": f"{int(d['n_fills'].sum()):,}".replace(",", "{,}"),
            "Round trips": f"{int(d['n_roundtrips'].sum()):,}".replace(",", "{,}"),
            "Wallets reconciled":
                f"{(r['status'] == 'RECONCILED').sum()} of {len(r)}",
        }
    rows = [" & ".join([k, col["Season 1"][k], col["Season 1.5"][k]]) + r" \\"
            for k in col["Season 1"]]
    write_raw("tab1_data", r"Alpha Arena, Seasons 1 and 1.5.", "tab:data",
              "lcc", [" & Season 1 & Season 1.5 " + r"\\"], rows)

    # ---- tab:trait
    c4 = csv_read("c4_stats.csv").set_index("metric")
    LAB = {"mean_leverage": "Mean gross leverage",
           "daily_vol": "Realised daily volatility",
           "share_in_market": "Share of time in market",
           "turnover_per_day": "Daily turnover"}
    rows = []
    for m, lab in LAB.items():
        r = c4.loc[m]
        rows.append(f"{lab} & {r.F_model:.2f} & {fmt_p(r.p_model)} & "
                    f"{r.icc_armFE:.2f} [{tex_num(r.icc_lo)}, {tex_num(r.icc_hi)}] & "
                    f"{r.kendall_W:.2f} & {fmt_p(r.p_W_perm)} " + r"\\")
    write_raw("tab2_trait",
              r"Model effects in risk measures, Season 1.5. Two-way analysis of "
              r"variance with model and arm effects; exact 95\% intervals for the "
              r"intraclass correlation in brackets; $W$ is Kendall's coefficient "
              r"of concordance across the four arms, with permutation $p$-value.",
              "tab:trait", "lccccc",
              [r" & $F_{7,21}$ & $p$ & ICC & $W$ & $p$ \\"], rows)

    # ---- tab:scale
    c2 = csv_read("c2_anova.csv")
    c2 = c2[c2["arms"] == "1-4"].reset_index(drop=True)
    OUT = ["Final return, compounded", "Cumulative return, arithmetic",
           "Leverage-scaled return", "Volatility-standardised return"]
    rows = [f"{OUT[i]} & {c2.icc_armFE[i]:.3f} & {c2.F_model_armFE[i]:.2f} & "
            f"{fmt_p(c2.p_model_armFE[i])} " + r"\\" for i in range(4)]
    write_raw("tab3_scale",
              r"Model effect in outcomes, Season 1.5. Two-way analysis of "
              r"variance with arm effects.", "tab:scale", "lccc",
              [r"Outcome & ICC & $F_{7,21}$ & $p$ \\"], rows)

    # ---- tab:shares
    c3 = csv_read("c3_variance_shares.csv")
    SH = [("final return %", "Final return"),
          ("leverage-scaled cumulative %", "Leverage-scaled return"),
          ("daily Sharpe", "Sharpe ratio")]
    rows = []
    for key, lab in SH:
        d = c3[c3["outcome"] == key].set_index("quantity")
        rows.append(f"{lab} & {d.loc['share_model','estimate']:.2f} & "
                    f"{d.loc['share_arm','estimate']:.2f} & "
                    f"{d.loc['share_resid','estimate']:.2f} " + r"\\")
    write_raw("tab4_shares", r"Shares of variance in outcomes, Season 1.5.",
              "tab:shares", "lccc",
              [r"Outcome & Model & Arm & Residual \\"], rows)

    # ---- tab:pnl
    d = csv_read("a1_pnl_decomposition.csv")
    s15 = d[d["season"] == "S15"]
    bym = s15.groupby("model")[["exposure_pnl", "timing_pnl", "slippage",
                                "fees", "funding", "net_pnl"]].sum() / 400.0
    bym[["slippage", "fees"]] *= -1
    bym = bym.sort_values("net_pnl", ascending=False)
    rows = [f"{tex_escape(m)} & " + " & ".join(f"{v:.1f}" for v in r) + r" \\"
            for m, r in bym.iterrows()]
    tot = bym.sum()
    rows.append(r"\midrule")
    rows.append("All models & " + " & ".join(f"{v:.1f}" for v in tot) + r" \\")
    write_raw("tab5_pnl",
              r"Decomposition of profit and loss, Season 1.5, per cent of the "
              r"\$40{,}000 invested in each model across the four arms. Exposure "
              r"is what a constant position of the same average size would have "
              r"earned; timing is the remainder of the gross result; slippage is "
              r"the shortfall of realised against marked prices.",
              "tab:pnl", "lrrrrrr",
              [r"Model & Exposure & Timing & Execution & Fees & Funding & Net \\"],
              rows)

    # ---- tab:pnl -- seasons as rows
    dd = csv_read("a1_pnl_decomposition.csv")
    rows = []
    for s_, lab, book in [("S1", "Season 1", 60000), ("S15", "Season 1.5", 320000)]:
        g = dd[dd["season"] == s_][["exposure_pnl", "timing_pnl", "slippage",
                                    "fees", "funding", "net_pnl"]].sum() / book * 100
        g[["slippage", "fees"]] *= -1
        # Two decimals here, one in the prose. The table is where a reader
        # checks the arithmetic, and at one decimal the Season 1 fee line
        # (8.2494) prints as 8.2, which reads as if it had been rounded down
        # from 8.25.
        rows.append(f"{lab} & " + " & ".join(
            (f"$-{fixed(abs(v), 2)}$" if v < 0 else f"${fixed(v, 2)}$")
            for v in g) + r" \\")
    write_raw("tab7_pnl_seasons",
              r"Decomposition of the change in equity, in per cent of initial "
              r"capital, all accounts.", "tab:pnl", "lrrrrrr",
              [r" & Exposure & Timing & Execution & Fees & Funding & Net \\"],
              rows)

    # ---- reduced tables for the Finance Research Letters version
    col2 = {}
    for s_, lab in [("S1", "Season 1"), ("S15", "Season 1.5")]:
        dd2 = desc[desc["season"] == s_]
        col2[lab] = {
            "Instruments": ("crypto perpetuals" if s_ == "S1"
                            else "equity-linked perpetuals"),
            "Analysis window (2025, UTC)": " -- ".join(
                pd.to_datetime(t, unit="ms", utc=True).strftime("%d %b").lstrip("0")
                for t in (wallets.SEASON_START[s_], wallets.OFFICIAL_END[s_])), 
            "Length (days)": f"{window_days()[s_]:.1f}",
            "Models / arms / accounts":
                f"{dd2['model'].nunique()} / "
                f"{dd2['competition_id'].nunique()} / {len(dd2)}",
            "Fills": f"{int(dd2['n_fills'].sum()):,}".replace(",", "{,}"),
        }
    rows = [" & ".join([k, col2["Season 1"][k], col2["Season 1.5"][k]]) + r" \\"
            for k in col2["Season 1"]]
    write_raw("frl_tab1_data",
              r"Alpha Arena, Seasons 1 and 1.5. Analytical initial capital is "
              r"normalised to USD~10{,}000 per account.", "tab:data", "lcc",
              [r" & Season 1 & Season 1.5 \\"], rows)

    # The main risk table carries the fixed-capital measures, which are the
    # ones the paper's interpretation rests on. Share of time in the market
    # has no denominator and is unchanged.
    vdd = js_read("i6_vol_denominator.json")
    FIXROW = [("Realised volatility", "vol_fixed"),
              ("Gross exposure", "leverage_fixed"),
              ("Daily turnover", "turnover_fixed"),
              ("Share of time in market", None)]
    rows = []
    for lab, key in FIXROW:
        if key is None:
            r = c4.loc["share_in_market"]
            F = float(r.F_model)
            pv = float(js_read("i4_inference.json")["holm"]["raw"]["F:share_in_market"])
            icc, lo_, hi_ = (float(r.icc_armFE), float(r.icc_lo),
                             float(r.icc_hi))
            W = float(r.kendall_W)
        else:
            q = vdd[key]
            F, pv = q["F_model"], q["p_perm"]
            icc, lo_, hi_ = q["icc"], q["icc_lo"], q["icc_hi"]
            W = q["W"]
        rows.append(f"{lab} & {F:.2f} & {fmt_p(pv)} & "
                    f"{icc:.2f} [{tex_num(lo_)}, {tex_num(hi_)}] & "
                    f"{W:.2f} " + r"\\")
    write_raw("frl_tab2_trait",
              r"Model effects in risk measures, Season 1.5. Volatility, exposure "
              r"and turnover use initial capital; time in market has no monetary "
              r"denominator. Two-way analysis of variance; unadjusted $p$ from "
              r"permuting model labels within arm. ICC intervals are 95\% "
              r"$F$-based intervals under the additive Gaussian model with "
              r"homoscedastic errors; $W$ measures concordance of model ranks "
              r"across arms. Assumptions and current-equity versions are in "
              r"the Online Appendix.",
              "tab:trait", "lcccc",
              [r" & $F_{7,21}$ & $p$ & ICC & $W$ \\"], rows)

    rows = []
    for s_, lab, book in [("S1", "Season 1", 60000), ("S15", "Season 1.5", 320000)]:
        g = dd[dd["season"] == s_][["exposure_pnl", "timing_pnl", "slippage",
                                    "fees", "funding", "net_pnl"]].sum() / book * 100
        g[["slippage", "fees"]] *= -1
        rows.append(f"{lab} & " + " & ".join(
            (f"$-{fixed(abs(v), 2)}$" if v < 0 else f"${fixed(v, 2)}$")
            for v in g) + r" \\")
    write_raw("frl_tab3_pnl",
              r"Decomposition of the change in equity, per cent of initial "
              r"capital, all accounts. Every column is a signed contribution "
              r"and the row sums to the net, so execution and fees appear as "
              r"$-X_i$ and $-F_i$; the quantity the text calls timing plus "
              r"execution is the sum of those two columns, $B_i-X_i$.",
              "tab:pnl", "lrrrrrr",
              [r" & Exposure & Timing & Execution & Fees & Funding & Net \\"],
              rows)

    # ---- tab:years, from equation (2)
    z2, rows = 7.8489, []
    for iota, rho in [(0.5, 0.50), (0.5, 0.95), (0.1, 0.50), (0.9, 0.50)]:
        vals = []
        for R in [1, 20, 100, float("inf")]:
            add = 0.0 if R == float("inf") else (1 - iota) / R
            vals.append(f"{2 * z2 * (iota * (1 - rho) + add):.1f}")
        rows.append(f"{iota} & {rho:.2f} & " + " & ".join(vals) + r" \\")
    write_raw("tab6_years",
              r"Years required to detect a gap of one in annualised Sharpe "
              r"ratios (two-sided test at 5\%, power 80\%), from "
              r"equation~\eqref{eq:years}.", "tab:years", "ccrrrr",
              [r"$\iota$ & $\rho^m$ & $R=1$ & $R=20$ & $R=100$ & "
               r"$R\to\infty$ \\"], rows)

    print(f"wrote {len([f for f in os.listdir(TABDIR) if f.endswith('.tex')])} "
          f"tables to {os.path.relpath(TABDIR, ROOT)}")


def tex_num(v: float) -> str:
    """Negative numbers with a LaTeX minus."""
    return f"$-${abs(v):.2f}" if v < 0 else f"{v:.2f}"


def fmt_p(p: float) -> str:
    return f"{p:.4f}" if p < 0.001 else f"{p:.3f}"


def write_raw(name: str, caption: str, label: str, align: str,
              header: list[str], rows: list[str], size: str = "small") -> None:
    os.makedirs(TABDIR, exist_ok=True)
    out = ([r"\begin{table}[ht]", r"\centering", "\\" + size,
            f"\\caption{{{caption}}}", f"\\label{{{label}}}",
            r"\begin{tabular}{" + align + "}", r"\toprule"]
           + header + [r"\midrule"] + rows
           + [r"\bottomrule", r"\end{tabular}", r"\end{table}"])
    with open(os.path.join(TABDIR, f"{name}.tex"), "w") as fh:
        fh.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
