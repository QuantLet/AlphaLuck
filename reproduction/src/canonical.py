"""One account-level table, from which every return in the paper is taken.

The referee found Grok-4's mean Season 1.5 return reported as -42.6 per cent in
the profit-and-loss decomposition and -49.1 per cent in the risk table, with
DeepSeek and Kimi differing by five and eight points. The cause was the window.

`analyse.common_window` used to begin at max(first fill) across accounts, which
is not the start of the season but the moment the last of the 32 accounts first
traded -- 20.8 hours into Season 1.5. Every account was already trading before
that. Measured at the old start, account equity ranged from 5,765 to 15,278
rather than the 10,000 each had been funded with, and one account was already
up 53 per cent. The risk table divided the window's equity change by equity at
that mid-season moment; the decomposition divided its dollar total by initial
capital. Two different denominators, two different numerators, and the gap
between them is largest for the accounts that moved most in the first day.

On the organiser's published window every account starts at exactly 10,000, so
the two definitions coincide. This module fixes the definition in one place:

    simple return = equity(official end) / 10,000 - 1

with the decomposition taken over the same window, so that for every account

    exposure + timing - slippage - fees + funding = 10,000 x simple return

up to the reconciliation residual. `tests/test_numbers.py` checks that each
model's mean decomposition total equals its mean final return to within
0.05 percentage points.

Writes data/derived/accounts.parquet, one row per account per season.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import analyse
import pnl_decomposition
import prov

DER = os.path.join(prov.ROOT, "data", "derived")
INITIAL_CAPITAL = 10_000.0


def build() -> pd.DataFrame:
    fills = pd.read_parquet(os.path.join(DER, "fills.parquet"))
    eq = pd.read_parquet(os.path.join(DER, "equity.parquet"))
    pan = pd.read_parquet(os.path.join(DER, "panel.parquet"))

    rows = []
    for season in ("S1", "S15"):
        lo, hi = analyse.common_window(fills, season)
        dec = pnl_decomposition.decompose(season).set_index("tag")
        e = eq[(eq["season"] == season) & (eq["t"] >= lo) & (eq["t"] <= hi)]
        p = pan[(pan["season"] == season) & (pan["t"] >= lo) & (pan["t"] <= hi)]

        for tag, g in e.groupby("tag"):
            g = g.sort_values("t")
            start, end = float(g["equity"].iloc[0]), float(g["equity"].iloc[-1])
            meta = fills[fills["tag"] == tag].iloc[0]

            # risk measures on the same window and the same grid, time-weighted
            w = p[p["tag"] == tag]
            lev = w["lev"] if "lev" in w else pd.Series(dtype=float)
            daily = (g.set_index(pd.to_datetime(g["t"], unit="ms", utc=True))
                      ["equity"].resample("1D").last().pct_change().dropna())

            d = dec.loc[tag] if tag in dec.index else None
            rows.append({
                "season": season, "tag": tag, "model": meta["model"],
                "competition_id": int(meta["competition_id"]),
                "initial_capital": INITIAL_CAPITAL,
                "equity_start": start, "equity_end": end,
                # the one definition: simple return on initial capital
                "final_return": end / INITIAL_CAPITAL - 1.0,
                "daily_vol": float(daily.std(ddof=1)) if len(daily) > 1 else np.nan,
                "n_days": int(len(daily)),
                **({f"pnl_{k}": float(d[k]) for k in
                    ["exposure_pnl", "timing_pnl", "slippage", "fees",
                     "funding", "net_pnl"]} if d is not None else {}),
            })

    out = pd.DataFrame(rows)
    # the identity, per account, in dollars
    out["pnl_total"] = (out["pnl_exposure_pnl"] + out["pnl_timing_pnl"]
                        - out["pnl_slippage"] - out["pnl_fees"]
                        + out["pnl_funding"])
    out["equity_change"] = out["equity_end"] - out["initial_capital"]
    out["residual"] = out["pnl_total"] - out["equity_change"]
    out["return_from_pnl"] = out["pnl_total"] / INITIAL_CAPITAL
    return out


def main() -> None:
    pd.set_option("display.width", 250, "display.max_columns", 40)
    d = build()
    d.to_parquet(os.path.join(DER, "accounts.parquet"), index=False)

    print("=== canonical account table: data/derived/accounts.parquet ===\n")
    for season, g in d.groupby("season"):
        worst = g["residual"].abs().max()
        print(f"{season}: {len(g)} accounts, "
              f"max |decomposition - equity change| = ${worst:,.0f} "
              f"({100 * worst / INITIAL_CAPITAL:.2f}% of initial capital)")

    print("\n--- Season 1.5 model means, the two definitions that disagreed ---\n")
    g = d[d["season"] == "S15"].groupby("model").agg(
        final_return=("final_return", "mean"),
        from_pnl=("return_from_pnl", "mean"))
    g["gap_pp"] = 100 * (g["from_pnl"] - g["final_return"])
    g = (100 * g[["final_return", "from_pnl"]]).join(g["gap_pp"])
    g.columns = ["final return %", "decomposition total %", "gap (pp)"]
    print(g.sort_values("final return %").round(2).to_string())
    print(f"\nlargest gap across models: "
          f"{g['gap (pp)'].abs().max():.3f} percentage points")


if __name__ == "__main__":
    main()
