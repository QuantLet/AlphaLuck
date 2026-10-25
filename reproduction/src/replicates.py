"""Phase 3, Q2 extension: what the four parallel S1.5 competitions buy us.

Season 1.5 ran the same eight models, on the same prompt template
('TestPrompt1' / 'swing_trading'), over the same window, in four separate
competitions with four separate wallets each. That is a replicate design, and
it lets luck be measured directly rather than argued about:

  T5  the organiser's own ranking unit -- each model's equal-weight aggregate
      over its four wallets -- with paired block-bootstrap SEs and required
      season length.
  T6  variance decomposition of final return into between-model and
      within-model (across-replicate) components, with the intraclass
      correlation and a one-way F test. Within-model spread is pure luck:
      same model, same prompts, same window.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import analyse
import prov
import wallets

DER = os.path.join(prov.ROOT, "data", "derived")
DAY_MS = 86400 * 1000


def aggregate_daily(eq: pd.DataFrame, fills: pd.DataFrame) -> pd.DataFrame:
    """Equal-weight aggregate equity per model across its four competitions."""
    lo, hi = analyse.common_window(fills, "S15")
    e = eq[(eq["season"] == "S15") & (eq["t"] >= lo) & (eq["t"] <= hi)]
    out = {}
    for model, g in e.groupby("model"):
        per = []
        for comp, gg in g.groupby("competition_id"):
            gg = gg.sort_values("t")
            s = gg.set_index("t")["equity"]
            per.append(s.groupby(s.index // DAY_MS).last())
        wide = pd.concat(per, axis=1).ffill().dropna()
        out[model] = wide.sum(axis=1)  # $40k book
    return pd.DataFrame(out)


def main() -> None:
    fills = pd.read_parquet(os.path.join(DER, "fills.parquet"))
    eq = pd.read_parquet(os.path.join(DER, "equity.parquet"))
    desc = pd.read_csv(os.path.join(DER, "t1_descriptive.csv"))
    pd.set_option("display.width", 250, "display.max_columns", 60)

    # ---------------------------------------------------------------- T5
    agg = aggregate_daily(eq, fills)
    rets = agg.pct_change().dropna()
    rows = []
    for m in agg.columns:
        r = rets[m].to_numpy()
        sr, se = analyse.sharpe_se_lo(r)
        rows.append(
            {
                "model": m,
                "T_days": len(r),
                "agg_return_pct": 100 * (agg[m].iloc[-1] / 40000 - 1),
                "mean_daily_ret_pct": 100 * r.mean(),
                "sd_daily_ret_pct": 100 * r.std(ddof=1),
                "sharpe_daily": sr,
                "se_sharpe_daily": se,
                "sharpe_ann": sr * np.sqrt(365),
            }
        )
    t5 = pd.DataFrame(rows).sort_values("agg_return_pct", ascending=False)
    t5.to_csv(os.path.join(DER, "t5_s15_aggregate.csv"), index=False)
    print("=== T5 S1.5, organiser ranking unit: equal-weight aggregate of 4 competitions ===")
    print(t5.to_string(index=False, float_format=lambda x: f"{x:,.3f}"))

    srt = t5.reset_index(drop=True)
    pairs = [("best_vs_worst", srt["model"].iloc[0], srt["model"].iloc[-1])]
    gaps = srt["mean_daily_ret_pct"].diff().abs()
    j = int(gaps.iloc[1:].idxmin())
    pairs.append(("two_closest", srt["model"].iloc[j - 1], srt["model"].iloc[j]))
    pr = []
    for label, a, b in pairs:
        res = analyse.paired_bootstrap(rets[a].to_numpy(), rets[b].to_numpy())
        pr.append({"pair": label, "a": a, "b": b, **res})
    t5p = pd.DataFrame(pr)
    t5p.to_csv(os.path.join(DER, "t5b_s15_aggregate_pairs.csv"), index=False)
    print("\n=== T5b power on the aggregate ===")
    print(t5p.to_string(index=False, float_format=lambda x: f"{x:,.4f}"))

    # ---------------------------------------------------------------- T6
    d = desc[desc["season"] == "S15"][["model", "competition_id", "return_pct"]]
    piv = d.pivot(index="model", columns="competition_id", values="return_pct")
    grand = d["return_pct"].mean()
    k = piv.shape[1]
    means = piv.mean(axis=1)
    ss_between = k * ((means - grand) ** 2).sum()
    ss_within = ((piv.sub(means, axis=0)) ** 2).to_numpy().sum()
    df_b, df_w = len(piv) - 1, len(piv) * (k - 1)
    ms_b, ms_w = ss_between / df_b, ss_within / df_w
    F = ms_b / ms_w
    p = 1 - stats.f.cdf(F, df_b, df_w)
    var_model = max((ms_b - ms_w) / k, 0.0)
    icc = var_model / (var_model + ms_w) if (var_model + ms_w) > 0 else np.nan

    t6 = piv.copy()
    t6["mean"] = means
    t6["sd_across_replicates"] = piv.std(axis=1, ddof=1)
    t6["range"] = piv.max(axis=1) - piv.min(axis=1)
    t6 = t6.sort_values("mean", ascending=False)
    t6.to_csv(os.path.join(DER, "t6_replicate_dispersion.csv"))
    print("\n=== T6 same model, four independent competitions: final return % ===")
    print(t6.to_string(float_format=lambda x: f"{x:,.2f}"))
    print(
        f"\n  between-model MS = {ms_b:,.1f}   within-model MS = {ms_w:,.1f}"
        f"   F({df_b},{df_w}) = {F:,.2f}   p = {p:.3f}"
    )
    print(
        f"  sd within model (luck, same prompts) = {np.sqrt(ms_w):,.1f} pp"
        f"   sd between models (skill) = {np.sqrt(var_model):,.1f} pp"
    )
    print(f"  intraclass correlation (share of variance that is model) = {icc:.3f}")
    print(
        f"  replicates needed for the observed between-model spread to beat luck "
        f"at 80% power / 5%: {analyse.Z**2 * ms_w / (means.max() - means.min())**2 * 2:,.1f}"
    )

    with open(os.path.join(DER, "t6_anova.txt"), "w") as fh:
        fh.write(
            f"ms_between={ms_b}\nms_within={ms_w}\nF={F}\ndf=({df_b},{df_w})\n"
            f"p={p}\nsd_within_pp={np.sqrt(ms_w)}\nsd_between_pp={np.sqrt(var_model)}\n"
            f"icc={icc}\n"
        )


if __name__ == "__main__":
    main()
