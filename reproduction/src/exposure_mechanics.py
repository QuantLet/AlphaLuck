"""How much of the equity-denominator exposure association is arithmetic?

Gross exposure on current equity factors as

    gross_t / E_t = (gross_t / C) * (C / E_t).

The second factor rises whenever an account loses, so a negative association
between exposure on current equity and the final return can arise without
any change in positions. Three checks separate the two channels:

    (a) the wealth factor alone, mean_t C / E_t, against the final return;
    (b) exposure over the previous date-end equity, which removes the
        same-day loss from the denominator but not earlier losses;
    (c) exposure in the first 24 hours of the window, before losses
        accumulate, on both denominators;
    (d) the same first-day exposure against the return after the first
        day only, (E_T - E_24) / C and E_T / E_24 - 1, so that the outcome
        excludes the window in which exposure is measured.

Each measure gets the same within-arm Spearman association with the final
return (and permutation p) as the published measures in
vol_fixed_denominator.py, and the exact test of inference_audit.py that
re-pairs whole model profiles (40,320 permutations), which keeps each
model's four accounts together. Nothing upstream is changed.

Writes data/derived/exposure_mechanics.{csv,json}.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import analyse
import inference_audit
import prov
import vol_fixed_denominator as vfd

DER = os.path.join(prov.ROOT, "data", "derived")
DAY_MS = vfd.DAY_MS
C = vfd.INITIAL_CAPITAL
FIRST_DAY_MS = 24 * 3_600_000


def frame(lo: int, hi: int) -> pd.DataFrame:
    eq = pd.read_parquet(os.path.join(DER, "equity.parquet"))
    e = eq[(eq["season"] == "S15") & (eq["t"] >= lo) & (eq["t"] <= hi)].copy()
    e["day"] = (e["t"] - lo) // DAY_MS
    pan = pd.read_parquet(os.path.join(DER, "panel.parquet"))
    pp = pan[(pan["season"] == "S15") & (pan["t"] >= lo) & (pan["t"] <= hi)]
    gross = (pp.assign(absn=pp["signed_notional"].abs())
             .groupby(["tag", "t"])["absn"].sum().rename("gross").reset_index())
    eqs = e.sort_values("t")[["tag", "t", "equity"]]
    g = pd.merge_asof(gross.sort_values("t"), eqs, on="t", by="tag")
    g["day"] = (g["t"] - lo) // DAY_MS
    # previous date-end equity; day 0 uses the opening equity
    dayend = e.sort_values("t").groupby(["tag", "day"])["equity"].last()
    opening = e.sort_values("t").groupby("tag")["equity"].first()
    prev = dayend.groupby(level=0).shift(1)
    prev = prev.fillna(opening.reindex(prev.index.get_level_values(0)).set_axis(prev.index))
    g = g.join(prev.rename("prev_equity"), on=["tag", "day"])
    if g[["equity", "prev_equity"]].isna().any().any():
        raise ValueError("Equity missing on the exposure grid")
    g["lev_eq"] = g["gross"] / g["equity"]
    g["lev_fx"] = g["gross"] / C
    g["lev_prev"] = g["gross"] / g["prev_equity"]
    g["wealth"] = C / g["equity"]
    first = g[g["t"] < lo + FIRST_DAY_MS]
    meta = e.groupby("tag")[["model", "competition_id"]].first()
    final = dayend.groupby(level=0).last() / C - 1.0
    e24 = e[e["t"] <= lo + FIRST_DAY_MS].sort_values("t").groupby("tag")["equity"].last()
    end = dayend.groupby(level=0).last()
    out = pd.DataFrame({
        "leverage_equity": g.groupby("tag")["lev_eq"].mean(),
        "leverage_fixed": g.groupby("tag")["lev_fx"].mean(),
        "leverage_prev_dayend": g.groupby("tag")["lev_prev"].mean(),
        "wealth_factor": g.groupby("tag")["wealth"].mean(),
        "leverage_equity_day1": first.groupby("tag")["lev_eq"].mean(),
        "leverage_fixed_day1": first.groupby("tag")["lev_fx"].mean(),
        "final_return": final,
        "after_day1_fixed": (end - e24) / C,
        "after_day1_equity": end / e24 - 1.0,
    }).join(meta)
    return out.rename(columns={"competition_id": "arm"}).reset_index()


def main() -> None:
    fills = pd.read_parquet(os.path.join(DER, "fills.parquet"))
    lo, hi = analyse.common_window(fills, "S15")
    d = frame(lo, hi)
    published = pd.read_csv(os.path.join(DER, "i6_vol_denominator.csv"))
    check = d.merge(published, on="tag", suffixes=("", "_pub"))
    worst = float(max((check.leverage_equity - check.leverage_equity_pub).abs().max(),
                      (check.leverage_fixed - check.leverage_fixed_pub).abs().max()))
    if len(check) != 32 or worst > 1e-9:
        raise ValueError(f"Does not reproduce the published exposure measures: {worst}")
    d.to_csv(os.path.join(DER, "exposure_mechanics.csv"), index=False)
    out = {"reproduces_published_max_abs": worst}
    for col in ("leverage_equity", "leverage_fixed", "leverage_prev_dayend",
                "wealth_factor", "leverage_equity_day1", "leverage_fixed_day1"):
        r = vfd.within_arm_rho(d, col)
        prof = inference_audit.profile_permutation(
            d.assign(final_return_pct=100 * d["final_return"]), col)
        out[col] = {"assoc_rho": r["rho"], "assoc_p_two_sided": r["p_two_sided"],
                    "profile_rho": prof["obs"], "profile_p": prof["p_profile"]}
        print(f"{col:24s} rho = {r['rho']:+.3f}  p = {r['p_two_sided']:.3f}  "
              f"profile p = {prof['p_profile']:.3f}")
    # (d) outcome after the first day only; appended after the published
    # tests so the shared permutation stream leaves them unchanged
    for outcome in ("after_day1_fixed", "after_day1_equity"):
        w = d.assign(final_return=d[outcome])
        for col in ("leverage_equity_day1", "leverage_fixed_day1"):
            r = vfd.within_arm_rho(w, col)
            prof = inference_audit.profile_permutation(
                w.assign(final_return_pct=100 * w["final_return"]), col)
            out[f"{col}__{outcome}"] = {"assoc_rho": r["rho"], "assoc_p_two_sided": r["p_two_sided"],
                                        "profile_rho": prof["obs"], "profile_p": prof["p_profile"]}
            print(f"{col:24s} vs {outcome:18s} rho = {r['rho']:+.3f}  "
                  f"p = {r['p_two_sided']:.3f}  profile p = {prof['p_profile']:.3f}")
    out["day1_rank_corr_eq_fixed"] = float(
        d[["leverage_equity_day1", "leverage_fixed_day1"]].corr("spearman").iloc[0, 1])
    with open(os.path.join(DER, "exposure_mechanics.json"), "w") as fh:
        json.dump(out, fh, indent=1, default=float)


if __name__ == "__main__":
    main()
