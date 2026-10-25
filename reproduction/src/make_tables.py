"""Emit wallets.csv and the markdown tables that go into AUDIT.md."""
from __future__ import annotations

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import analyse
import prov
import wallets

DER = os.path.join(prov.ROOT, "data", "derived")
OUT = os.path.join(DER, "tables.md")


def md(df: pd.DataFrame, cols=None, fmt="{:,.2f}", index=False) -> str:
    d = df[cols] if cols else df
    return d.to_markdown(index=index, floatfmt=".2f")


def main() -> None:
    fills = pd.read_parquet(os.path.join(DER, "fills.parquet"))
    recon = pd.read_parquet(os.path.join(DER, "recon.parquet"))
    desc = pd.read_csv(os.path.join(DER, "t1_descriptive.csv"))
    sim = pd.read_csv(os.path.join(DER, "t2_similarity.csv"))
    per = pd.read_csv(os.path.join(DER, "t3_precision_per_model.csv"))
    prs = pd.read_csv(os.path.join(DER, "t4_precision_pairs.csv"))
    t5 = pd.read_csv(os.path.join(DER, "t5_s15_aggregate.csv"))
    t5b = pd.read_csv(os.path.join(DER, "t5b_s15_aggregate_pairs.csv"))
    t6 = pd.read_csv(os.path.join(DER, "t6_replicate_dispersion.csv"))

    # wallets.csv
    reg = pd.DataFrame(wallets.registry())
    reg["tag"] = [wallets.tag(r) for r in wallets.registry()]
    st = recon.set_index("tag")["status"].to_dict()
    reg["reconciliation"] = reg["tag"].map(st)
    reg[
        [
            "season",
            "season_label",
            "competition_id",
            "run_id",
            "model",
            "address",
            "reconciliation",
            "source_kind",
            "source_url",
        ]
    ].to_csv(os.path.join(prov.ROOT, "wallets.csv"), index=False)

    parts = []
    A = parts.append

    # inventory
    inv = []
    for season, label in [("S1", "Alpha Arena S1 (crypto perps)"),
                          ("S15", "Alpha Arena S1.5 (tokenised US equities)")]:
        lo, hi = analyse.common_window(fills, season)
        lo_x, hi_x = analyse.common_window(fills, season, official=False)
        d = desc[desc["season"] == season]
        r = recon[recon["season"] == season]
        inv.append(
            {
                "arena-season": label,
                "wallets": len(d),
                "models": d["model"].nunique(),
                "competitions": d["competition_id"].nunique(),
                "common window (UTC, official)": f"{pd.Timestamp(lo, unit='ms'):%Y-%m-%d %H:%M} .. {pd.Timestamp(hi, unit='ms'):%Y-%m-%d %H:%M}",
                "days": round((hi - lo) / 86400000, 1),
                "on-chain end": f"{pd.Timestamp(hi_x, unit='ms'):%Y-%m-%d}",
                "trading days (min-max)": f"{d['trading_days'].min()}-{d['trading_days'].max()}",
                "fills": int(d["n_fills"].sum()),
                "round trips": int(d["n_roundtrips"].sum()),
                "reconciled": f"{(r['status'] == 'RECONCILED').sum()}/{len(r)}",
            }
        )
    A("### Inventory\n")
    A(pd.DataFrame(inv).to_markdown(index=False))

    A("\n### T1 Descriptive audit, per arena-season and model (official window)\n")
    A(
        desc[
            ["season", "competition_id", "model", "n_fills", "n_roundtrips", "n_coins",
             "trading_days", "share_in_market", "median_hold_h", "mean_leverage",
             "max_leverage", "fees_usd", "funding_usd", "return_pct", "max_drawdown_pct"]
        ].to_markdown(index=False, floatfmt=".2f")
    )

    A("\n### T2a Season 1 similarity, all 15 pairs\n")
    s1 = sim[(sim["season"] == "S1")]
    A(
        s1[["a", "b", "exposure_corr_agg", "exposure_corr_percoin_mean",
            "same_direction_share", "both_in_market_share", "pnl1h_corr"]]
        .to_markdown(index=False, floatfmt=".3f")
    )

    A("\n### T2b Season 1.5 similarity: different models vs the same model in another competition\n")
    cols = ["exposure_corr_agg", "exposure_corr_percoin_mean",
            "same_direction_share", "both_in_market_share", "pnl1h_corr"]
    s15 = sim[sim["season"] == "S15"]
    g = pd.DataFrame(
        [
            {
                "metric": c,
                "different models, same competition (mean)": s15[s15["group"] == "within_competition"][c].mean(),
                "sd": s15[s15["group"] == "within_competition"][c].std(),
                "same model, different competition (mean)": s15[s15["group"] == "across_competition"][c].mean(),
                "sd ": s15[s15["group"] == "across_competition"][c].std(),
            }
            for c in cols
        ]
    )
    A(f"n = 112 different-model pairs, 48 same-model pairs\n")
    A(g.to_markdown(index=False, floatfmt=".3f"))

    A("\n### T3 Per-model precision (daily returns, official window)\n")
    A(
        per[["season", "competition_id", "model", "T_days", "mean_daily_ret_pct",
             "sd_daily_ret_pct", "sharpe_daily", "se_sharpe_daily_lo2002",
             "sharpe_ann", "nw_lag"]].to_markdown(index=False, floatfmt=".3f")
    )

    A("\n### T4 Pairwise precision and required season length (single wallets)\n")
    A(prs.to_markdown(index=False, floatfmt=".4f"))

    A("\n### T5 Season 1.5 on the organiser's ranking unit (equal-weight over 4 competitions)\n")
    A(t5.to_markdown(index=False, floatfmt=".3f"))
    A("\n### T5b Required season length on that aggregate\n")
    A(t5b.to_markdown(index=False, floatfmt=".4f"))

    A("\n### T6 Same model, four independent competitions: final return %\n")
    A(t6.to_markdown(index=False, floatfmt=".2f"))
    A("\n" + open(os.path.join(DER, "t6_anova.txt")).read())

    A("\n### T7 Reconciliation, all 38 wallets\n")
    A(
        recon[["season", "competition_id", "model", "pub_equity", "recon_equity",
               "tips", "diff", "diff_pct", "n_fills", "n_roundtrips", "status"]]
        .to_markdown(index=False, floatfmt=".2f")
    )

    with open(OUT, "w") as fh:
        fh.write("\n".join(parts) + "\n")
    print(f"wrote {OUT} and wallets.csv")


if __name__ == "__main__":
    main()
