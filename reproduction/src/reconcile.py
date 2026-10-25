"""Phase 2 validation: reconstructed equity vs the organiser's published figures.

Two independent organiser series are used as targets:
  S1   nof1.ai/api/account-totals captured 2025-11-12 (Wayback) -- hourly
       dollar_equity per model, plus nof1.ai/api/leaderboard final equity.
  S15  www.alphaarena.ai/api/account-totals -- hourly dollar_equity per run.

The comparison is made at the organiser's own last timestamp inside the season
window, against the reconstructed 5-minute equity curve at the nearest grid
point at or before it. A wallet whose gap exceeds the tolerance is flagged
unverified and dropped from Phase 3.
"""
from __future__ import annotations

import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import prov
import wallets

DER = os.path.join(prov.ROOT, "data", "derived")
TOL_PCT = 5.0  # |reconstructed - published| / published, in percent


def organiser_targets() -> pd.DataFrame:
    """Published equity per (season, competition, model), with its timestamp."""
    rows = []

    with open(os.path.join(prov.RAW, "nof1_s1/account-totals.json")) as fh:
        s1 = json.load(fh)["accountTotals"]
    df = pd.DataFrame(s1)
    df = df[df["model_id"] != "buynhold_btc"]
    df["t_ms"] = (df["timestamp"] * 1000).astype("int64")
    df = df[df["t_ms"] <= wallets.S1_END_MS]
    for model, g in df.groupby("model_id"):
        g = g.sort_values("t_ms")
        last = g.iloc[-1]
        rows.append(
            {
                "season": "S1",
                "competition_id": 1,
                "model": model,
                "pub_t_ms": int(last["t_ms"]),
                "pub_equity": float(last["dollar_equity"]),
                "pub_n": len(g),
                "pub_source": "nof1.ai/api/account-totals @Wayback 20251112224724",
            }
        )

    with open(os.path.join(prov.RAW, "nof1/account-totals.json")) as fh:
        s15 = json.load(fh)["accountTotals"]
    df = pd.DataFrame(s15)
    df["t_ms"] = (df["timestamp"] * 1000).astype("int64")
    runmap = {
        r["run_id"]: (r["competition_id"], wallets._norm(r["model_id"]))
        for r in json.load(
            open(os.path.join(prov.RAW, "nof1/since-inception-values.json"))
        )["sinceInceptionValues"]
    }
    for run_id, g in df.groupby("run_id"):
        if run_id not in runmap:
            continue
        comp, model = runmap[run_id]
        g = g.sort_values("t_ms")
        last = g.iloc[-1]
        rows.append(
            {
                "season": "S15",
                "competition_id": comp,
                "model": model,
                "pub_t_ms": int(last["t_ms"]),
                "pub_equity": float(last["dollar_equity"]),
                "pub_n": len(g),
                "pub_source": "alphaarena.ai/api/account-totals",
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    eq = pd.read_parquet(os.path.join(DER, "equity.parquet"))
    rt = pd.read_parquet(os.path.join(DER, "roundtrips.parquet"))
    fills = pd.read_parquet(os.path.join(DER, "fills.parquet"))
    ledger = pd.read_parquet(os.path.join(DER, "ledger.parquet"))
    tgt = organiser_targets()

    out = []
    for r in tgt.itertuples():
        sel = eq[
            (eq["season"] == r.season)
            & (eq["competition_id"] == r.competition_id)
            & (eq["model"] == r.model)
        ]
        if sel.empty:
            out.append({**r._asdict(), "recon_equity": None, "status": "no wallet data"})
            continue
        tag = sel["tag"].iloc[0]
        at = sel[sel["t"] <= r.pub_t_ms].sort_values("t")
        recon = float(at["equity"].iloc[-1]) if len(at) else float("nan")
        # public tips received before the comparison point inflate the real account
        tips = ledger[
            (ledger["tag"] == tag)
            & (ledger["type"] == "internalTransfer")
            & (ledger["time"] <= r.pub_t_ms)
        ]["signed"].sum()
        nf = len(fills[(fills["tag"] == tag) & (fills["time"] <= r.pub_t_ms)])
        nrt = len(rt[(rt["tag"] == tag) & (rt["exit_time"] <= r.pub_t_ms)])
        diff = recon + tips - r.pub_equity
        pct = 100 * diff / r.pub_equity if r.pub_equity else float("nan")
        out.append(
            {
                "season": r.season,
                "competition_id": r.competition_id,
                "model": r.model,
                "tag": tag,
                "pub_equity": r.pub_equity,
                "recon_equity": recon,
                "tips": tips,
                "recon_plus_tips": recon + tips,
                "diff": diff,
                "diff_pct": pct,
                "n_fills": nf,
                "n_roundtrips": nrt,
                "status": "RECONCILED" if abs(pct) <= TOL_PCT else "UNVERIFIED",
                "pub_source": r.pub_source,
            }
        )

    rec = pd.DataFrame(out)
    rec.to_parquet(os.path.join(DER, "recon.parquet"), index=False)
    pd.set_option("display.width", 220, "display.max_columns", 50)
    cols = [
        "season",
        "competition_id",
        "model",
        "pub_equity",
        "recon_equity",
        "tips",
        "diff",
        "diff_pct",
        "n_fills",
        "n_roundtrips",
        "status",
    ]
    print(rec[cols].to_string(index=False, float_format=lambda x: f"{x:,.2f}"))
    print()
    print(rec["status"].value_counts().to_string())


if __name__ == "__main__":
    main()
