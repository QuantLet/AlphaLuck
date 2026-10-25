"""The adjacent continuation sample: does risk appetite survive the season end?

The wallets kept trading for 9-16 days after the organiser's official end
(2025-12-03T22:00Z), which gives an adjacent continuation sample. It is not a hold-out: the
accounts carry their positions, their equity and whatever operating state the
harness kept across the boundary, so continuity of behaviour is the null, not
the finding. For each S1.5 wallet we recompute mean gross leverage and
realised daily volatility there and ask whether the in-season ordering of the
models survives.

Gross leverage is reported two ways. Scaled by current equity it is what the
accounts faced, but an account that has lost money shows higher leverage
without having chosen more risk, so persistently low equity can manufacture
persistently high measured leverage. Scaled by initial capital the denominator
is fixed at 10,000 for every account and every day, so the measure moves only
when the position does. Both are reported; the second is the one that speaks
to a choice.

Two further checks the referee asked for: persistence after removing arm
effects, and sensitivity to dropping the first one and two days of the
continuation sample, where inherited positions matter most.

    (a) wallet-level rank correlation between in-season and post-season values,
        with a permutation p-value (labels shuffled overall, and stratified
        within arm as a robustness check);
    (b) the two-way (model, arm) ANOVA model effect and arm-adjusted ICC with
        its exact F-based interval, estimated in the post-season period alone;
    (c) Kendall's W for the model ordering across the two periods, i.e. two
        raters (periods) ranking eight items (models).

Did the rules change after the official end? Partly answerable. All 100
conversations the organiser's capped endpoint returns are dated 2025-12-06,
i.e. *after* the official end, and they carry the same prompt_name
('TestPrompt1'), the same skill ('swing_trading') and the same arm-3-only
peer-standings block as the arm structure implies. So the rule structure is
unchanged in the post-season period. What cannot be determined is the
converse: because no in-season prompt was captured, the prompts cannot be
compared directly between the two periods, and nothing public states whether
the harness was left running deliberately or simply not switched off.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import analyse
import prov
import wallets as W

DER = os.path.join(prov.ROOT, "data", "derived")
RNG = np.random.default_rng(20261019)
NPERM = 20000
DAY_MS = 86_400_000
ALPHA = 0.05
INITIAL_CAPITAL = 10_000.0
METRICS = ["mean_leverage", "mean_leverage_init", "daily_vol"]


def window_metrics(lo: int, hi: int) -> pd.DataFrame:
    """Risk metrics for every S1.5 wallet over [lo, hi]."""
    pan = pd.read_parquet(os.path.join(DER, "panel.parquet"))
    eq = pd.read_parquet(os.path.join(DER, "equity.parquet"))
    fills = pd.read_parquet(os.path.join(DER, "fills.parquet"))

    e = eq[(eq["season"] == "S15") & (eq["t"] >= lo) & (eq["t"] <= hi)]
    p = pan[(pan["season"] == "S15") & (pan["t"] >= lo) & (pan["t"] <= hi)]
    f = fills[(fills["season"] == "S15") & (fills["time"] >= lo)
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
        eqs = s.reindex(gross.index).ffill()
        lev = (gross / eqs.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan)
        wf = f[f["tag"] == tag]
        rows.append({
            "tag": tag,
            "model": g["model"].iloc[0],
            "arm": int(g["competition_id"].iloc[0]),
            "mean_leverage": float(lev.mean()),
            # fixed denominator: moves only when the position moves
            "mean_leverage_init": float((gross / INITIAL_CAPITAL).mean()),
            "daily_vol": float(r.std(ddof=1)) if len(r) > 1 else np.nan,
            "n_days": int(len(r)) + 1,
            "n_fills": int(len(wf)),
            "final_return_pct": 100 * float(s.iloc[-1] / s.iloc[0] - 1),
        })
    return pd.DataFrame(rows).sort_values(["arm", "model"]).reset_index(drop=True)


def anova_icc(y: np.ndarray) -> dict:
    n, k = y.shape
    grand = y.mean()
    rm, cm = y.mean(axis=1), y.mean(axis=0)
    ss_m = k * ((rm - grand) ** 2).sum()
    ss_a = n * ((cm - grand) ** 2).sum()
    ss_e = ((y - grand) ** 2).sum() - ss_m - ss_a
    df_m, df_a, df_e = n - 1, k - 1, (n - 1) * (k - 1)
    ms_m, ms_a, ms_e = ss_m / df_m, ss_a / df_a, ss_e / df_e
    F = ms_m / ms_e
    v = max((ms_m - ms_e) / k, 0.0)
    icc = v / (v + ms_e) if (v + ms_e) > 0 else np.nan
    FL = F / stats.f.ppf(1 - ALPHA / 2, df_m, df_e)
    FU = F * stats.f.ppf(1 - ALPHA / 2, df_e, df_m)
    return {"F_model": F, "p_model": float(stats.f.sf(F, df_m, df_e)),
            "icc_armFE": icc,
            "icc_lo": (FL - 1) / (FL + k - 1), "icc_hi": (FU - 1) / (FU + k - 1),
            "F_arm": ms_a / ms_e, "p_arm": float(stats.f.sf(ms_a / ms_e, df_a, df_e))}


def kendall_w_two_periods(a: np.ndarray, b: np.ndarray) -> dict:
    """Two raters (periods) ranking n models."""
    n = len(a)
    ranks = np.column_stack([stats.rankdata(a), stats.rankdata(b)])
    m = 2
    Ri = ranks.sum(axis=1)
    S = ((Ri - Ri.mean()) ** 2).sum()
    Wst = 12 * S / (m**2 * (n**3 - n))
    chi2 = m * (n - 1) * Wst
    return {"kendall_W": Wst, "chi2": chi2,
            "p_chi2": float(stats.chi2.sf(chi2, n - 1))}


def main() -> None:
    pd.set_option("display.width", 260, "display.max_columns", 40)
    fills = pd.read_parquet(os.path.join(DER, "fills.parquet"))
    in_lo, in_hi = analyse.common_window(fills, "S15")                 # official
    _, on_hi = analyse.common_window(fills, "S15", official=False)     # on-chain
    post_lo, post_hi = W.S15_OFFICIAL_END_MS, on_hi

    print(f"in-season   {pd.Timestamp(in_lo, unit='ms', tz='UTC')} .. "
          f"{pd.Timestamp(in_hi, unit='ms', tz='UTC')}")
    print(f"post-season {pd.Timestamp(post_lo, unit='ms', tz='UTC')} .. "
          f"{pd.Timestamp(post_hi, unit='ms', tz='UTC')}  "
          f"({(post_hi - post_lo)/DAY_MS:.1f} days)\n")

    ins = window_metrics(in_lo, in_hi).set_index("tag")
    post = window_metrics(post_lo, post_hi).set_index("tag")
    tags = [t for t in ins.index if t in post.index]
    ins, post = ins.loc[tags], post.loc[tags]

    print(f"wallets with data in both periods: {len(tags)} of {len(ins)}")
    print(f"post-season days per wallet: min {post['n_days'].min()}, "
          f"median {int(post['n_days'].median())}, max {post['n_days'].max()}")
    print(f"post-season fills: {int(post['n_fills'].sum()):,} "
          f"(in-season {int(ins['n_fills'].sum()):,})")

    comb = pd.DataFrame({
        "model": ins["model"], "arm": ins["arm"],
        **{f"in_{m}": ins[m] for m in METRICS},
        **{f"post_{m}": post[m] for m in METRICS},
        "post_days": post["n_days"], "post_fills": post["n_fills"],
    }).reset_index()
    comb.to_csv(os.path.join(DER, "p1_persistence_wallets.csv"), index=False)

    models = sorted(ins["model"].unique())
    arms = sorted(ins["arm"].unique())
    out = {"windows": {
        "in_lo": int(in_lo), "in_hi": int(in_hi),
        "post_lo": int(post_lo), "post_hi": int(post_hi),
        "post_days": float((post_hi - post_lo) / DAY_MS),
        "post_days_min": int(post["n_days"].min()),
        "post_fills": int(post["n_fills"].sum()),
        "in_fills": int(ins["n_fills"].sum()),
    }, "rows": []}

    for met in METRICS:
        x = ins[met].to_numpy(float)
        y = post[met].to_numpy(float)
        rho = stats.spearmanr(x, y).statistic

        # (a) permutation: shuffle the post-season labels
        cnt = sum(1 for _ in range(NPERM)
                  if stats.spearmanr(x, RNG.permutation(y)).statistic >= rho)
        p_overall = (cnt + 1) / (NPERM + 1)
        # stratified within arm
        idx = {a: np.where(ins["arm"].to_numpy() == a)[0] for a in arms}
        cnt2 = 0
        for _ in range(NPERM):
            yp = y.copy()
            for a in arms:
                ii = idx[a]
                yp[ii] = RNG.permutation(y[ii])
            if stats.spearmanr(x, yp).statistic >= rho:
                cnt2 += 1
        p_strat = (cnt2 + 1) / (NPERM + 1)

        # (b) post-season ANOVA
        grid = (post.reset_index().pivot(index="model", columns="arm", values=met)
                .loc[models, arms].to_numpy(float))
        av = anova_icc(grid)
        grid_in = (ins.reset_index().pivot(index="model", columns="arm", values=met)
                   .loc[models, arms].to_numpy(float))
        av_in = anova_icc(grid_in)

        # (c) Kendall W across the two periods, on model means
        kw = kendall_w_two_periods(grid_in.mean(axis=1), grid.mean(axis=1))

        # arm-adjusted: remove the arm mean from both series before ranking,
        # so the correlation cannot be carried by the arms alone
        def demean_by_arm(v):
            df = pd.DataFrame({"v": v, "arm": ins["arm"].to_numpy()})
            return (df["v"] - df.groupby("arm")["v"].transform("mean")).to_numpy()

        xa, ya = demean_by_arm(x), demean_by_arm(y)
        rho_arm = stats.spearmanr(xa, ya).statistic
        cnt3 = 0
        for _ in range(NPERM):
            yp = y.copy()
            for a in arms:
                ii = idx[a]
                yp[ii] = RNG.permutation(y[ii])
            if stats.spearmanr(xa, demean_by_arm(yp)).statistic >= rho_arm:
                cnt3 += 1
        p_arm_adj = (cnt3 + 1) / (NPERM + 1)

        # sensitivity: drop the first one and two days of the continuation
        # sample, where inherited positions dominate
        drop = {}
        for k in (1, 2):
            pk = window_metrics(post_lo + k * DAY_MS, post_hi)
            pk = pk.set_index("tag").reindex(tags)
            yk = pk[met].to_numpy(float)
            ok = np.isfinite(yk) & np.isfinite(x)
            drop[f"drop{k}_spearman"] = float(
                stats.spearmanr(x[ok], yk[ok]).statistic)
            drop[f"drop{k}_n"] = int(ok.sum())

        out["rows"].append({
            "metric": met,
            "spearman_arm_adjusted": float(rho_arm),
            "perm_p_arm_adjusted": p_arm_adj,
            **drop,
            "spearman_wallet": float(rho),
            "perm_p_overall": p_overall,
            "perm_p_stratified": p_strat,
            "spearman_model_means": float(
                stats.spearmanr(grid_in.mean(axis=1), grid.mean(axis=1)).statistic),
            "post_F_model": av["F_model"], "post_p_model": av["p_model"],
            "post_icc": av["icc_armFE"], "post_icc_lo": av["icc_lo"],
            "post_icc_hi": av["icc_hi"],
            "post_F_arm": av["F_arm"], "post_p_arm": av["p_arm"],
            "in_F_model": av_in["F_model"], "in_icc": av_in["icc_armFE"],
            "kendall_W_periods": kw["kendall_W"], "p_W": kw["p_chi2"],
        })

    res = pd.DataFrame(out["rows"])
    res.to_csv(os.path.join(DER, "p1_persistence.csv"), index=False)
    print("\n=== P1 persistence of risk appetite past the official end ===")
    print(res.to_string(index=False, float_format=lambda v: f"{v:,.4f}"))

    print("\n--- model means, in-season vs post-season ---")
    for met in METRICS:
        a = ins.groupby("model")[met].mean()
        b = post.groupby("model")[met].mean()
        d = pd.DataFrame({"in": a, "post": b,
                          "in_rank": a.rank(), "post_rank": b.rank()})
        print(f"\n{met}")
        print(d.sort_values("in_rank").to_string(float_format=lambda v: f"{v:,.3f}"))

    with open(os.path.join(DER, "p1_persistence.json"), "w") as fh:
        json.dump(out, fh, indent=1, default=float)


if __name__ == "__main__":
    main()
