"""Everything the referee asked about the inference, in one place.

Four things:

1. A registry of every test the letter reports: its null, the unit that is
   permuted, the dependence that permutation preserves, the number of draws
   and the sidedness. Written out as a table for the online appendix, so that
   a reader does not have to infer any of it from a p-value.

2. A sensitivity analysis for the risk-return associations that permutes
   *whole model profiles*. Each model's four arm values form a profile; the
   association is between a model's risk profile and its return profile, and
   the null is that the pairing between them is arbitrary. Permuting which
   risk profile goes with which return profile keeps each model's cross-arm
   structure intact, which permuting accounts within arms does not. All 8! =
   40,320 pairings are enumerated, so the p-value is exact under that null.

3. Leave-one-model-out for the model-effect tests and the risk-return
   associations: with eight models a single one can carry a result, and the
   range over the eight deletions says whether it does.

4. Holm correction across the reported tests, as one family of eight: the
   four model-effect tests of Table 2 and the four risk-return associations.

The ICC estimand is also defined here rather than left implicit. See
`icc_note()`.

Writes data/derived/i4_inference.{csv,json} and the appendix table.
"""
from __future__ import annotations

import itertools
import json
import os
import sys

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import prov
import vol_fixed_denominator as vol_denom

DER = os.path.join(prov.ROOT, "data", "derived")
# Primary measures are those on initial capital: a risk measure divided by
# current equity rises when an account loses, so it carries part of the
# outcome it is being related to. See src/vol_fixed_denominator.py.
RISK = ["vol_fixed", "leverage_fixed", "share_in_market", "turnover_fixed"]
NICE = {"vol_fixed": "Realised volatility",
        "leverage_fixed": "Gross exposure",
        "share_in_market": "Share of time in market",
        "turnover_fixed": "Turnover per day"}


def icc_note() -> dict:
    """What the ICC is here, and why a lower limit can be negative."""
    return {
        "estimand": (
            "Ratio of the between-model variance component to the sum of the "
            "between-model and residual components in a two-way layout with "
            "arm fixed effects and one account per model-arm cell, i.e. "
            "ICC(3,1) in the Shrout-Fleiss scheme (McGraw and Wong case 3A)."),
        "model_effects": (
            "Models are treated as random for the purpose of forming the "
            "ratio, arms as fixed. The eight models are not a sample from a "
            "population of models -- they are the eight the organiser "
            "selected -- so the ratio is read as a descriptive partition of "
            "variance among these eight implementations and not as an "
            "estimate of a population reliability."),
        "interval": (
            "Exact F-based interval of Shrout and Fleiss (1979), inverting "
            "the distribution of the ratio of mean squares. It is exact under "
            "that model's assumptions -- additivity of model and arm effects, "
            "normal and homoscedastic residuals -- and not merely because the "
            "formula is closed-form."),
        "negative_lower_limit": (
            "The interval is computed on the variance-ratio scale and then "
            "mapped to the ICC scale. When the model mean square is below the "
            "residual mean square the implied between-model variance is "
            "negative, and the mapped lower limit is negative with it. A "
            "variance cannot be negative; the limit should be read as 'not "
            "distinguishable from zero', and it is reported untruncated so "
            "that the width of the interval is not misrepresented."),
    }


def registry() -> pd.DataFrame:
    """Null, unit, preserved dependence, draws and sidedness for each test."""
    rows = [
        ("Model effect on each risk measure (Table 2)",
         "No difference between models, given arm effects",
         "Model labels, permuted within arm",
         "Arm composition; each arm keeps one account per model",
         "20,000", "One-sided on $F$"),
        ("Kendall's $W$ across arms (Table 2)",
         "Model ranks in different arms are unrelated",
         "Ranks within each arm, permuted independently",
         "The set of ranks in each arm",
         "20,000", "One-sided on $W$"),
        ("Risk-return rank correlation, accounts",
         "No association between a risk measure and the return, given arm",
         "Accounts, permuted within arm",
         "Arm means of both variables",
         "20,000", "Two-sided, $|\\rho|$"),
        ("Risk-return, whole model profiles",
         "The pairing of a model's risk profile with its return profile is "
         "arbitrary",
         "The eight model profiles, re-paired against one another",
         "Each model's cross-arm structure, on both variables",
         "40,320 (exact)", "Two-sided, $|\\rho|$"),
        ("Rank association with the continuation sample",
         "In-season and continuation values are unrelated",
         "Continuation-sample values, permuted within arm",
         "Arm composition",
         "20,000", "Upper tail of Spearman $\\rho$"),
        ("Arm effect on each risk measure",
         "No difference between arms, given model effects",
         "Arm labels, permuted within model",
         "Each model's set of four values",
         "20,000", "One-sided on $F$"),
    ]
    return pd.DataFrame(rows, columns=[
        "Test", "Null hypothesis", "Permuted unit", "Dependence preserved",
        "Draws", "Sidedness"])


def profile_permutation(w: pd.DataFrame, metric: str) -> dict:
    """Exact test pairing model risk profiles against model return profiles."""
    piv_x = w.pivot(index="model", columns="arm", values=metric)
    piv_y = w.pivot(index="model", columns="arm", values="final_return_pct")
    models = list(piv_x.index)
    X, Y = piv_x.to_numpy(float), piv_y.to_numpy(float)

    # Twice the centred midranks are integers, including tied ranks.  When
    # all arm denominators match, the mean Spearman statistic is proportional
    # to an integer rank-product sum.  Compare those sums exactly: comparing
    # separately rounded spearmanr floats used to exclude equal permutations.
    n, n_arms = X.shape
    xr = np.rint(2 * stats.rankdata(X, axis=0) - (n + 1)).astype(np.int64)
    yr = np.rint(2 * stats.rankdata(Y, axis=0) - (n + 1)).astype(np.int64)
    denom_sq = (xr * xr).sum(axis=0) * (yr * yr).sum(axis=0)
    if np.any(denom_sq == 0):
        raise ValueError("Profile Spearman correlation requires nonconstant arms")
    denoms = np.sqrt(denom_sq)
    obs_products = (xr * yr).sum(axis=0)
    obs = float(np.mean(obs_products / denoms))
    perms = np.array(list(itertools.permutations(range(n))))
    products = (xr[perms] * yr).sum(axis=1)
    if np.all(denom_sq == denom_sq[0]):
        vals = products.sum(axis=1)
        extreme = np.abs(vals) >= abs(obs_products.sum())
    else:
        # Differing tie patterns introduce square-root normalisers.  Include
        # numerical ties conservatively at a tolerance of 100 machine eps;
        # this is many orders below distinct statistics in this 8-model data.
        vals = np.mean(products / denoms, axis=1)
        tolerance = 100 * np.finfo(float).eps * max(1.0, abs(obs))
        extreme = np.abs(vals) >= abs(obs) - tolerance
    p = float(np.mean(extreme))
    return {"metric": metric, "obs": obs, "p_profile": p,
            "n_perm": len(vals)}


def loo(w: pd.DataFrame, metric: str) -> dict:
    """Leave one model out: range of the F statistic and the correlation."""
    models = sorted(w["model"].unique())
    Fs, rhos = [], []
    for drop in models:
        s = w[w["model"] != drop]
        piv = s.pivot(index="model", columns="arm", values=metric).to_numpy(float)
        k, a = piv.shape
        grand = piv.mean()
        ss_m = a * ((piv.mean(axis=1) - grand) ** 2).sum()
        ss_a = k * ((piv.mean(axis=0) - grand) ** 2).sum()
        ss_t = ((piv - grand) ** 2).sum()
        ss_e = ss_t - ss_m - ss_a
        df_m, df_e = k - 1, (k - 1) * (a - 1)
        Fs.append((ss_m / df_m) / (ss_e / df_e))
        rhos.append(float(np.mean([
            stats.spearmanr(s[s["arm"] == arm][metric],
                            s[s["arm"] == arm]["final_return_pct"]).statistic
            for arm in sorted(s["arm"].unique())])))
    return {"metric": metric,
            "F_min": float(np.min(Fs)), "F_max": float(np.max(Fs)),
            "F_drop_worst": models[int(np.argmin(Fs))],
            "rho_min": float(np.min(rhos)), "rho_max": float(np.max(rhos)),
            "rho_drop_worst": models[int(np.argmax(rhos))]}


def holm(pvals: dict) -> dict:
    """Holm-Bonferroni over one family."""
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    n, out, running = len(items), {}, 0.0
    for i, (k, p) in enumerate(items):
        adj = min(1.0, max(running, (n - i) * p))
        running = adj
        out[k] = adj
    return out


def main() -> None:
    pd.set_option("display.width", 260, "display.max_columns", 40)
    w = pd.read_csv(os.path.join(DER, "c4_wallet_risk.csv"))
    fx = pd.read_csv(os.path.join(DER, "i6_vol_denominator.csv"))
    w = w.merge(fx[["tag", "vol_fixed", "leverage_fixed", "turnover_fixed"]],
                on="tag", how="left")
    vd = json.load(open(os.path.join(DER, "i6_vol_denominator.json")))
    rc = pd.read_csv(os.path.join(DER, "r3_wallet_rankcorr.csv")).set_index("metric")

    print("=== whole-model-profile permutation (exact, 8! pairings) ===\n")
    prof = [profile_permutation(w, m) for m in RISK]
    pf = pd.DataFrame(prof)
    print(pf.to_string(index=False, float_format=lambda v: f"{v:,.4f}"))

    print("\n=== leave one model out ===\n")
    lo = pd.DataFrame([loo(w, m) for m in RISK])
    print(lo.to_string(index=False, float_format=lambda v: f"{v:,.3f}"))

    # Holm across the eight reported tests
    # model-effect p-values: permutation, on the primary measure
    fam = {}
    for m in RISK:
        if m in vd:
            fam[f"F:{m}"] = float(vd[m]["p_perm"])
        else:
            # c4_stats.p_model is a parametric F-reference p-value.  Use
            # the same within-arm permutation test as the other risk measures,
            # with an explicit local seed independent of prior module calls.
            grid = w.pivot(index="model", columns="arm", values=m).to_numpy(float)
            observed = vol_denom.anova_icc(grid)["F_model"]
            fam[f"F:{m}"] = vol_denom.perm_F(
                grid, observed, rng=np.random.default_rng(20261009))
    # two-sided, because the direction of each association was not
    # prespecified; this is the conservative choice and the one the family
    # correction is applied to
    for m in RISK:
        if m in vd:
            fam[f"rho:{m}"] = float(vd[m]["assoc_p_two_sided"])
        elif m in rc.index:
            fam[f"rho:{m}"] = float(rc.loc[m, "perm_p_two_sided"])
    adj = holm(fam)
    print("\n=== Holm across the reported behavioural and association tests "
          f"(family of {len(fam)}) ===\n")
    print(f"{'test':<30}{'raw p':>10}{'Holm p':>10}  survives 0.05")
    for k in sorted(fam, key=lambda z: fam[z]):
        print(f"  {k:<28}{fam[k]:>10.4f}{adj[k]:>10.4f}"
              f"{'   yes' if adj[k] < 0.05 else '   no'}")

    out = {"icc": icc_note(),
           "profile": prof,
           "loo": lo.to_dict("records"),
           "holm": {"family_size": len(fam),
                    "raw": fam, "adjusted": adj,
                    "n_survive": int(sum(v < 0.05 for v in adj.values()))}}
    with open(os.path.join(DER, "i4_inference.json"), "w") as fh:
        json.dump(out, fh, indent=1, default=float)
    pd.concat([pf, lo], axis=1).to_csv(
        os.path.join(DER, "i4_inference.csv"), index=False)
    registry().to_csv(os.path.join(DER, "i4_registry.csv"), index=False)
    print(f"\nwrote i4_inference.json, i4_inference.csv, i4_registry.csv")


if __name__ == "__main__":
    main()
