"""Item 1: are the four Season-1.5 competitions true replicates?

Primary sources (all recorded in competitions.csv):

1. The organiser's own front-end bundle carries a per-competition title,
   subtitle and description. The UI indexes competitions from 2 (index 1 is the
   "Aggregate Index" chart), so API `competition_id` c maps to bundle keys
   u[c] and p[c+1]/d[c+1]. Both keyings agree, and the mapping is pinned
   independently by source 2 below.
     src: https://www.alphaarena.ai/_next/static/chunks/pages/_app-16433bc4d70bcfd6.js
2. /api/conversations carries the verbatim prompt each model received. Competition
   3 -- and only competition 3 -- appends a "# CURRENT STATE OF COMPETITION"
   block listing every model's account value, return, Sharpe and drawdown with a
   "**YOU**" marker (25/25 of its prompts; 0/75 elsewhere). That is exactly the
   bundle's "Situational Awareness" arm, which fixes the index offset.
     src: https://www.alphaarena.ai/api/conversations
3. The market-data half of the prompt is identical across arms: after removing
   the leaderboard block, 12 of 13 distinct market snapshots are shared by two
   or more competitions and 8 by all four. The arms differ in instructions and
   in the competitive information, not in the market feed.

Conclusion: the four competitions are four deliberately different treatment
arms, not replicates. This module also tests that empirically, pooled over
models, using the models as blocks (Friedman) since every model appears in
every arm.
"""
from __future__ import annotations

import json
import os
import re
import sys

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import analyse
import prov

DER = os.path.join(prov.ROOT, "data", "derived")

# From the organiser's bundle; see docstring for the index mapping.
ARMS = {
    1: {
        "arm_label": "1: New Baseline",
        "title": "New Baseline",
        "subtitle": "Trades equities, ingests news/sentiment data, wider action space",
        "description": "Upgrades include: ability to trade US equities, news/sentiment data",
    },
    2: {
        "arm_label": "2: Monk Mode",
        "title": "Monk Mode",
        "subtitle": (
            "New experimental system prompt & harness, ~50% shorter than baseline, "
            "more opinionated guardrails on trading thresholds and risk management"
        ),
        "description": (
            "Emphasis on capital preservation, survival, and stronger risk "
            "management practices"
        ),
    },
    3: {
        "arm_label": "3: Situational Awareness",
        "title": "Situational Awareness",
        "subtitle": "Awareness of competition & leaderboard + other model's positions",
        "description": (
            "This competition makes the models aware of the competition, their "
            "current rank, and the PnL of the other models"
        ),
    },
    4: {
        "arm_label": "4: Max Leverage",
        "title": "Max Leverage",
        "subtitle": "Max leverage on every trade, max capital efficiency, tests risk management",
        "description": (
            "This competition forces the models to take max leverage on every "
            "trade. Maximizing capital efficiency and testing risk mgmt"
        ),
    },
}

LEADERBOARD_BLOCK = "# CURRENT STATE OF COMPETITION"
CAPITAL_MARK = "# CURRENT AVAILABLE CAPITAL"


def prompt_evidence() -> pd.DataFrame:
    """Per competition: how many prompts carry the peer-standings block."""
    with open(os.path.join(prov.RAW, "nof1/conversations.json")) as fh:
        conv = json.load(fh)["conversations"]
    rows = []
    for comp in sorted({x["competition_id"] for x in conv}):
        g = [x for x in conv if x["competition_id"] == comp]
        rows.append(
            {
                "competition_id": comp,
                "n_prompts_sampled": len(g),
                "n_with_peer_standings": sum(
                    1 for x in g if LEADERBOARD_BLOCK in x["user_prompt"]
                ),
                "prompt_name": sorted({x["prompt_name"] for x in g}),
                "skill": sorted({x["skill"] for x in g}),
                "mean_prompt_chars": int(np.mean([len(x["user_prompt"]) for x in g])),
            }
        )
    return pd.DataFrame(rows)


def wallet_metrics() -> pd.DataFrame:
    """Behavioural metrics per (model, competition) on the official S1.5 window."""
    fills = pd.read_parquet(os.path.join(DER, "fills.parquet"))
    pan = pd.read_parquet(os.path.join(DER, "panel.parquet"))
    eq = pd.read_parquet(os.path.join(DER, "equity.parquet"))
    rt = pd.read_parquet(os.path.join(DER, "roundtrips.parquet"))
    lo, hi = analyse.common_window(fills, "S15")

    out = []
    for tag, g in fills[(fills["season"] == "S15")].groupby("tag"):
        w = g[(g["time"] >= lo) & (g["time"] <= hi)]
        if w.empty:
            continue
        p = pan[(pan["tag"] == tag) & (pan["t"] >= lo) & (pan["t"] <= hi)]
        e = eq[(eq["tag"] == tag) & (eq["t"] >= lo) & (eq["t"] <= hi)].sort_values("t")
        r = rt[(rt["tag"] == tag) & (rt["entry_time"] >= lo) & (rt["exit_time"] <= hi)]

        grp = p.groupby("t")
        gross = grp["signed_notional"].apply(lambda s: s.abs().sum())
        eqs = e.set_index("t")["equity"].reindex(gross.index).ffill()
        lev = (gross / eqs.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan)
        days = pd.to_datetime(w["time"], unit="ms", utc=True).dt.date.nunique()

        # instrument mix: share of total gross exposure by coin
        mix = (
            p.assign(absn=p["signed_notional"].abs())
            .groupby("coin")["absn"]
            .sum()
        )
        mix = mix / mix.sum() if mix.sum() > 0 else mix
        hhi = float((mix**2).sum())

        out.append(
            {
                "competition_id": int(g["competition_id"].iloc[0]),
                "model": g["model"].iloc[0],
                "tag": tag,
                "mean_leverage": float(lev.mean()),
                "median_leverage": float(lev.median()),
                "p95_leverage": float(lev.quantile(0.95)),
                "mean_gross_notional": float(gross.mean()),
                "roundtrips_per_day": len(r) / days if days else np.nan,
                "fills_per_day": len(w) / days if days else np.nan,
                "median_hold_h": float(r["hold_ms"].median() / 3.6e6) if len(r) else np.nan,
                "instrument_hhi": hhi,
                "share_index_xyz100": float(mix.get("xyz:XYZ100", 0.0)),
                "n_coins": int(w["coin"].nunique()),
            }
        )
    return pd.DataFrame(out).sort_values(["competition_id", "model"])


METRICS = [
    "mean_leverage",
    "median_leverage",
    "p95_leverage",
    "mean_gross_notional",
    "roundtrips_per_day",
    "fills_per_day",
    "median_hold_h",
    "instrument_hhi",
    "share_index_xyz100",
]


def exchangeability(m: pd.DataFrame) -> pd.DataFrame:
    """Friedman test across the 4 arms with the 8 models as blocks."""
    rows = []
    for met in METRICS:
        piv = m.pivot(index="model", columns="competition_id", values=met).dropna()
        arrs = [piv[c].to_numpy() for c in sorted(piv.columns)]
        stat, p = stats.friedmanchisquare(*arrs)
        k, n = len(arrs), len(piv)
        W = stat / (n * (k - 1))  # Kendall's W
        rows.append(
            {
                "metric": met,
                "n_models": n,
                **{f"arm{c}_mean": piv[c].mean() for c in sorted(piv.columns)},
                "friedman_chi2": stat,
                "p_value": p,
                "kendall_W": W,
                "max_over_min_arm_mean": piv.mean().max() / piv.mean().min()
                if piv.mean().min() > 0
                else np.nan,
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- decomposition
def decomposition() -> dict:
    """Redo the final-return variance split with a competition fixed effect.

    The audit's original T6 was a one-way model y_kr = mu + alpha_k + eps_kr,
    which charges the arm differences to "luck". Since the arms are deliberately
    different (above), the honest version adds an arm main effect:
        y_kr = mu + alpha_k + gamma_r + eps_kr
    with 8 models, 4 arms, one observation per cell: df 7 / 3 / 21.
    """
    desc = pd.read_csv(os.path.join(DER, "t1_descriptive.csv"))
    d = desc[desc["season"] == "S15"]
    piv = d.pivot(index="model", columns="competition_id", values="return_pct")
    y = piv.to_numpy(float)
    n, k = y.shape  # 8 models, 4 arms
    grand = y.mean()
    rm = y.mean(axis=1)
    cm = y.mean(axis=0)

    ss_model = k * ((rm - grand) ** 2).sum()
    ss_arm = n * ((cm - grand) ** 2).sum()
    ss_tot = ((y - grand) ** 2).sum()
    ss_within = ((y - rm[:, None]) ** 2).sum()   # one-way residual
    ss_resid = ss_tot - ss_model - ss_arm        # two-way residual

    df_model, df_arm = n - 1, k - 1
    df_within, df_resid = n * (k - 1), (n - 1) * (k - 1)
    ms_model, ms_arm = ss_model / df_model, ss_arm / df_arm
    ms_within, ms_resid = ss_within / df_within, ss_resid / df_resid

    def icc(ms_b, ms_e):
        vm = max((ms_b - ms_e) / k, 0.0)
        return vm, (vm / (vm + ms_e) if vm + ms_e > 0 else np.nan)

    vm1, icc1 = icc(ms_model, ms_within)
    vm2, icc2 = icc(ms_model, ms_resid)

    res = {
        "n_models": n,
        "n_arms": k,
        "oneway_ms_model": ms_model,
        "oneway_ms_within": ms_within,
        "oneway_F": ms_model / ms_within,
        "oneway_p": float(1 - stats.f.cdf(ms_model / ms_within, df_model, df_within)),
        "oneway_sd_within_pp": float(np.sqrt(ms_within)),
        "oneway_sd_between_pp": float(np.sqrt(vm1)),
        "oneway_icc": icc1,
        "arm_ms": ms_arm,
        "arm_F": ms_arm / ms_resid,
        "arm_p": float(1 - stats.f.cdf(ms_arm / ms_resid, df_arm, df_resid)),
        "arm_effects_pp": {int(c): float(v - grand) for c, v in zip(piv.columns, cm)},
        "twoway_ms_resid": ms_resid,
        "twoway_F_model": ms_model / ms_resid,
        "twoway_p_model": float(1 - stats.f.cdf(ms_model / ms_resid, df_model, df_resid)),
        "twoway_sd_resid_pp": float(np.sqrt(ms_resid)),
        "twoway_sd_between_pp": float(np.sqrt(vm2)),
        "twoway_icc": icc2,
        "share_of_oneway_within_explained_by_arm": ss_arm / ss_within,
    }
    with open(os.path.join(DER, "i1_decomposition.json"), "w") as fh:
        json.dump(res, fh, indent=1)
    return res


def print_decomposition(r: dict) -> None:
    print("\n=== I1d final-return decomposition, with and without an arm effect ===")
    print(f"  one-way (audit T6):  sd_within {r['oneway_sd_within_pp']:.1f}pp  "
          f"sd_between {r['oneway_sd_between_pp']:.1f}pp  ICC {r['oneway_icc']:.3f}  "
          f"F(7,24)={r['oneway_F']:.2f} p={r['oneway_p']:.4f}")
    print(f"  arm main effect:     F(3,21)={r['arm_F']:.2f} p={r['arm_p']:.4f}   "
          "effects (pp vs grand mean): "
          + ", ".join(f"arm{c}:{v:+.1f}" for c, v in r["arm_effects_pp"].items()))
    print(f"  two-way (arm FE):    sd_resid  {r['twoway_sd_resid_pp']:.1f}pp  "
          f"sd_between {r['twoway_sd_between_pp']:.1f}pp  ICC {r['twoway_icc']:.3f}  "
          f"F(7,21)={r['twoway_F_model']:.2f} p={r['twoway_p_model']:.4f}")
    print(f"  arm differences account for "
          f"{100*r['share_of_oneway_within_explained_by_arm']:.1f}% of what the "
          "one-way model called within-model variance")


def main() -> None:
    ev = prompt_evidence()
    print("=== I1a prompt evidence per competition ===")
    print(ev.to_string(index=False))

    arms = pd.DataFrame(
        [{"competition_id": c, **v} for c, v in ARMS.items()]
    ).merge(ev, on="competition_id")
    arms["source_bundle"] = (
        "https://www.alphaarena.ai/_next/static/chunks/pages/_app-16433bc4d70bcfd6.js"
    )
    arms["source_prompts"] = "https://www.alphaarena.ai/api/conversations"
    arms.to_csv(os.path.join(prov.ROOT, "competitions.csv"), index=False)

    m = wallet_metrics()
    m.to_csv(os.path.join(DER, "i1_wallet_metrics.csv"), index=False)
    print("\n=== I1b behavioural metrics, arm means (pooled over the 8 models) ===")
    print(
        m.groupby("competition_id")[METRICS]
        .mean()
        .to_string(float_format=lambda x: f"{x:,.3f}")
    )

    ex = exchangeability(m)
    ex.to_csv(os.path.join(DER, "i1_exchangeability.csv"), index=False)
    print("\n=== I1c Friedman test across arms, models as blocks ===")
    print(ex.to_string(index=False, float_format=lambda x: f"{x:,.4f}"))

    sig = ex[ex["p_value"] < 0.05]["metric"].tolist()
    print(f"\nmetrics differing across arms at 5%: {sig}")

    print_decomposition(decomposition())


if __name__ == "__main__":
    main()
