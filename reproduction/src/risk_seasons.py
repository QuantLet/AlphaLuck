"""Pre-work A2: does a model's risk appetite carry across seasons?

Check 4 established that leverage and volatility are stable model traits across
the four Season-1.5 arms. Those arms share a window, an asset class and a
harness, so the natural follow-up is whether the trait survives a change of all
three: Season 1 is crypto perpetuals over 17 days in October 2025, Season 1.5 is
tokenised US equities over 13 days in November-December 2025.

Four models appear in both seasons under the same version string
(claude-sonnet-4-5, grok-4, deepseek-chat-v3.1, qwen3-max). Two appear as
different versions (gpt-5 -> gpt-5.1, gemini-2.5-pro -> gemini-3-pro-preview);
they are reported separately as a looser "same family" match, since a version
change is a different model and conflating them would overstate the test.

For each model-season: mean gross leverage, realised daily volatility, share of
time in market, turnover per day. S1.5 values are the mean over the model's four
arms. Reported with Spearman and Pearson correlation across seasons, with an
exact p-value, and a permutation p from relabelling models within Season 1.5.
With n = 4 strict matches this is a weak test by construction and is reported as
such.
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

import analyse
import prov

DER = os.path.join(prov.ROOT, "data", "derived")
DAY_MS = 86_400_000
METRICS = ["mean_leverage", "daily_vol", "share_in_market", "turnover_per_day"]

# version-change pairs, kept apart from the strict matches
FAMILY = {"gpt-5": "gpt-5.1", "gemini-2.5-pro": "gemini-3-pro-preview"}


def wallet_risk(season: str) -> pd.DataFrame:
    fills = pd.read_parquet(os.path.join(DER, "fills.parquet"))
    pan = pd.read_parquet(os.path.join(DER, "panel.parquet"))
    eq = pd.read_parquet(os.path.join(DER, "equity.parquet"))
    lo, hi = analyse.common_window(fills, season)

    e = eq[(eq["season"] == season) & (eq["t"] >= lo) & (eq["t"] <= hi)]
    p = pan[(pan["season"] == season) & (pan["t"] >= lo) & (pan["t"] <= hi)]
    f = fills[(fills["season"] == season) & (fills["time"] >= lo)
              & (fills["time"] <= hi)]

    rows = []
    for tag, g in e.groupby("tag"):
        g = g.sort_values("t")
        s = g.set_index("t")["equity"]
        dayend = s.groupby(s.index // DAY_MS).last()
        r = dayend.pct_change().dropna()

        wp = p[p["tag"] == tag]
        grp = wp.groupby("t")
        gross = grp["signed_notional"].apply(lambda v: v.abs().sum())
        inm = grp["signed_size"].apply(lambda v: (v.abs() > 1e-12).any())
        eqs = s.reindex(gross.index).ffill()
        lev = (gross / eqs.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan)

        wf = f[f["tag"] == tag]
        ndays = pd.to_datetime(wf["time"], unit="ms", utc=True).dt.date.nunique()
        notional = (wf["sz"].abs() * wf["px"]).sum()

        rows.append(
            {
                "season": season,
                "competition_id": int(g["competition_id"].iloc[0]),
                "model": g["model"].iloc[0],
                "tag": tag,
                "mean_leverage": float(lev.mean()),
                "daily_vol": float(r.std(ddof=1)),
                "share_in_market": float(inm.mean()),
                "turnover_per_day": float(notional / (eqs.mean() * max(ndays, 1))),
                "final_return_pct": 100 * float(s.iloc[-1] / s.iloc[0] - 1),
                "n_days": ndays,
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    pd.set_option("display.width", 260, "display.max_columns", 40)
    w1, w15 = wallet_risk("S1"), wallet_risk("S15")
    per = pd.concat([w1, w15], ignore_index=True)
    per.to_csv(os.path.join(DER, "a2_wallet_risk_seasons.csv"), index=False)

    a = w1.set_index("model")[METRICS + ["final_return_pct"]]
    b = w15.groupby("model")[METRICS + ["final_return_pct"]].mean()
    a["season"], b["season"] = "S1", "S1.5 (mean of 4 arms)"
    comb = pd.concat([a.reset_index(), b.reset_index()])
    comb = comb[["model", "season"] + METRICS + ["final_return_pct"]]
    comb.to_csv(os.path.join(DER, "a2_risk_seasons.csv"), index=False)
    print("=== A2a risk metrics by model and season ===")
    print(comb.to_string(index=False, float_format=lambda x: f"{x:,.3f}"))

    strict = sorted(set(a.index) & set(b.index))
    family = [(k, v) for k, v in FAMILY.items() if k in a.index and v in b.index]
    print(f"\nstrict matches (same version string): {strict}")
    print(f"family matches (version changed): {family}")

    rng = np.random.default_rng(20261014)
    out = []
    for label, pairs in [("strict (same version)", [(m, m) for m in strict]),
                         ("strict + family", [(m, m) for m in strict] + family)]:
        x_models = [p[0] for p in pairs]
        y_models = [p[1] for p in pairs]
        for met in METRICS:
            x = a.loc[x_models, met].to_numpy(float)
            y = b.loc[y_models, met].to_numpy(float)
            sp = stats.spearmanr(x, y)
            pe = stats.pearsonr(x, y)
            # permutation: relabel the S1.5 models
            obs = sp.statistic
            cnt = 0
            NP = 20000
            for _ in range(NP):
                if stats.spearmanr(x, rng.permutation(y)).statistic >= obs:
                    cnt += 1
            out.append(
                {
                    "match_set": label,
                    "n": len(pairs),
                    "metric": met,
                    "spearman": obs,
                    "spearman_p_exact": float(sp.pvalue),
                    "perm_p_one_sided": (cnt + 1) / (NP + 1),
                    "pearson": float(pe.statistic),
                    "S1_mean": float(x.mean()),
                    "S15_mean": float(y.mean()),
                    "S15_over_S1": float(y.mean() / x.mean()) if x.mean() else np.nan,
                }
            )
    cor = pd.DataFrame(out)
    cor.to_csv(os.path.join(DER, "a2_crossseason_corr.csv"), index=False)
    print("\n=== A2b cross-season correlation of each risk metric ===")
    print(cor.to_string(index=False, float_format=lambda x: f"{x:,.3f}"))

    with open(os.path.join(DER, "a2_risk_crossseason.json"), "w") as fh:
        json.dump(
            {
                "correlations": out,
                "common_models": strict,
                "n_common": len(strict),
                "family_pairs": family,
                "S1_days": int(w1["n_days"].max()),
                "S15_days": int(w15["n_days"].max()),
            },
            fh,
            indent=1,
            default=float,
        )

    print("\n--- rank of each model on mean gross leverage, by season ---")
    rk = pd.DataFrame(
        {
            "S1": a["mean_leverage"].rank(),
            "S1.5": b["mean_leverage"].rank(),
        }
    ).dropna()
    rk["S1_value"] = a["mean_leverage"]
    rk["S1.5_value"] = b["mean_leverage"]
    print(rk.sort_values("S1").to_string(float_format=lambda x: f"{x:,.2f}"))


if __name__ == "__main__":
    main()
