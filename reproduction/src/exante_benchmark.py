"""Ex-ante frozen-book benchmark for the letter (Section 3.2, Online Appendix).

The exposure component of the decomposition is what a constant position equal
to the account's time-averaged position would have earned. That average is
known only after the whole path has been observed, so it is an ex-post
attribution and not a strategy anyone could have followed.

This module computes a retrospective diagnostic using positions observed at
FORM_HOURS after the published start. Inherited reconstructed equity follows
the recorded daily-funding convention: historical daily aggregates are booked
at their labeled timestamps rather than their constituent hourly settlements.
It is therefore not exact cash equity known at formation. The open book is
held unchanged and marked to the published close; no subsequent trades or
trading fees are added. src/funding_hourly_sensitivity.py evaluates the
separate hourly-funding sensitivity using pooled prices as an oracle proxy.

Two exclusions define the benchmark and must be reported with it:

  * no funding is credited or debited after the freeze in this restricted
    baseline. The account's own later payments price a different position
    path and are retained only as a diagnostic. The separate hourly audit
    validates the daily aggregates against hourly quantities and rates,
    replaces daily-booked funding on both paths, and applies funding to the
    frozen quantities after formation. Historical oracle prices remain
    unverified, so that calculation is an explicitly labeled sensitivity;
  * the terminal book is marked, not liquidated, so no closing cost is taken.
    This favours the benchmark.

run(mmr=...) checks the frozen equity path against a maintenance-margin proxy
of mmr times gross notional at every grid point and flags breaches; the rate is
a parameter because Hyperliquid's per-asset schedule is not in the data. The
formation point is a choice, varied in the sensitivity table. The terminal
cost sensitivity is in paper/frl/benchmark_cost_sensitivity.py; it is a
terminal adjustment only and does not show that the path was feasible.

Writes data/derived/a4_exante_benchmark.{csv,json}.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import analyse
import prov

DER = os.path.join(prov.ROOT, "data", "derived")
BOOK = {"S1": 60_000.0, "S15": 320_000.0}
INITIAL_CAPITAL = 10_000.0
FORM_HOURS = 24
MMR = (0.01, 0.025, 0.05)        # maintenance margin rates swept
CUTOFFS = (12, 24, 48)           # freeze points swept, hours


def run(season: str, form_hours: int = FORM_HOURS,
        mmr: float = 0.0) -> pd.DataFrame:
    """Freeze each account's book at form_hours and carry it to the close.

    The cash-flow definition, stated because the comparison turns on it:

      * the benchmark inherits reconstructed equity under the recorded
        daily-funding convention: realised profit and loss, fees paid, and
        funding booked in the reconstructed series. Daily aggregates may
        contain settlements later on the same day, so this is not exact
        cash equity available at formation. Positions are the quantities
        the account actually held, without a hypothetical new entry trade;
      * first-day round trips are therefore already in the inherited equity,
        and only the open book is carried forward;
      * **no funding is credited after the freeze.** The account's own
        post-freeze payments cannot be used: they were charged on the
        positions it actually went on to hold, which are not the frozen ones.
        Historical userFunding rows with nSamples are daily aggregates,
        not single hourly payments. The separate funding_hourly_sensitivity.py
        validates their constituents and recomputes both paths using actual
        hourly rates and pooled trade prices in place of historical oracle
        prices. This resolves the earlier aggregation mismatch, but does not
        establish exact counterfactual funding. Adding the account's own
        later payments remains only a diagnostic for a different path;
      * no further fees are charged, because no further trade is made;
      * the terminal book is marked, not liquidated, so no closing cost is
        taken. That favours the benchmark, and is stated.

    With mmr > 0 the equity path is checked against a maintenance requirement
    of mmr times gross notional at every grid point, and an account whose
    frozen book would have breached it is flagged. Hyperliquid does not
    publish a per-asset maintenance schedule in a form this data captures, so
    the rate is a parameter and the result is reported across a range rather
    than at one value.
    """
    fills = pd.read_parquet(os.path.join(DER, "fills.parquet"))
    pan = pd.read_parquet(os.path.join(DER, "panel.parquet"))
    eq = pd.read_parquet(os.path.join(DER, "equity.parquet"))
    fu = pd.read_parquet(os.path.join(DER, "funding.parquet"))
    lo, hi = analyse.common_window(fills, season)
    t0 = lo + form_hours * 3_600_000
    p = pan[(pan["season"] == season) & (pan["t"] >= lo) & (pan["t"] <= hi)]
    grid = np.sort(p["t"].unique())
    fwd = grid[grid >= t0]

    rows = []
    for tag, w in p.groupby("tag"):
        meta = w.iloc[0]
        held, n_pos = {}, 0
        for coin, cg in w.groupby("coin"):
            cg = cg.sort_values("t").set_index("t")
            upto = cg[cg.index <= t0]
            if upto.empty:
                continue
            q = float(upto["signed_size"].iloc[-1])
            if q == 0.0:
                # An unheld instrument needs no mark: 0 * NaN is still NaN.
                continue
            px = cg["px"].reindex(fwd).ffill()
            if not np.isfinite(q) or not np.isfinite(px.to_numpy(float)).all():
                raise ValueError(
                    f"Non-finite frozen position or mark: {season}/{tag}/{coin}"
                )
            n_pos += 1
            held[coin] = (q, px)

        # reconstructed equity at formation under the recorded funding convention
        e_w = eq[eq["tag"] == tag].sort_values("t").set_index("t")
        eq0 = float(e_w["equity"].reindex(grid).ffill().loc[fwd[0]])
        mtm_path = np.zeros(len(fwd))
        gross_path = np.zeros(len(fwd))
        for q, px in held.values():
            v = px.to_numpy(float)
            mtm_path += q * (v - v[0])
            gross_path += np.abs(q * v)

        # Actual-path funding, retained only as a diagnostic; not frozen-book funding.
        fw = fu[(fu["tag"] == tag) & (fu["time"] >= t0) & (fu["time"] <= hi)]
        fund = float(fw["usdc"].sum()) if len(fw) else 0.0

        # no funding on the frozen book; `fund` is carried only so that the
        # alternative can be reported alongside
        equity_path = eq0 + mtm_path
        if not np.isfinite(equity_path).all() or not np.isfinite(gross_path).all():
            raise ValueError(f"Non-finite frozen valuation path: {season}/{tag}")
        breach_at = np.nan
        if mmr > 0:
            bad = np.where(equity_path < mmr * gross_path)[0]
            if len(bad):
                breach_at = float((fwd[bad[0]] - t0) / 86_400_000)

        rows.append({"season": season, "tag": tag, "model": meta["model"],
                     "arm": int(meta["competition_id"]),
                     "instruments_held": n_pos,
                     "equity_at_freeze": eq0,
                     "hold_mtm": float(mtm_path[-1]),
                     "hold_funding": fund,
                     "hold_terminal": float(equity_path[-1]),
                     "hold_net": float(equity_path[-1] - INITIAL_CAPITAL),
                     "hold_net_with_actual_funding":
                         float(equity_path[-1] + fund - INITIAL_CAPITAL),
                     "min_margin_ratio": float(np.min(
                         equity_path / np.where(gross_path > 0, gross_path,
                                                np.nan)))
                     if np.nanmax(gross_path) > 0 else np.nan,
                     "breach_day": breach_at})
    return pd.DataFrame(rows)


def main() -> None:
    pd.set_option("display.width", 250, "display.max_columns", 40)
    acc = pd.read_parquet(os.path.join(DER, "accounts.parquet"))
    out, summary = [], {}

    for season in ("S1", "S15"):
        a = acc[acc["season"] == season][["tag", "model", "equity_change"]]
        book = BOOK[season]
        d = run(season).merge(a, on=["tag", "model"])
        d["diff"] = d["equity_change"] - d["hold_net"]
        realised = float(d["equity_change"].sum())
        net = float(d["hold_net"].sum())
        better = int((d["hold_net"] > d["equity_change"]).sum())

        print(f"\n{'=' * 74}\n{season}: freeze the book at {FORM_HOURS} hours "
              f"and carry it to the close\n{'=' * 74}")
        print(f"  benchmark {net:>12,.0f}  {100 * net / book:>7.2f}% of capital")
        print(f"  realised  {realised:>12,.0f}  "
              f"{100 * realised / book:>7.2f}%")
        wf = float(d["hold_net_with_actual_funding"].sum())
        print(f"  (crediting the account's own post-freeze funding instead "
              f"would give {100 * wf / book:>6.2f}%)")
        print(f"  benchmark beats {better} of {len(d)} accounts; median paired "
              f"difference (realised - held) "
              f"{d['diff'].median() / INITIAL_CAPITAL * 100:+.1f} pp")

        print(f"\n  paired difference by arm, per cent of each account's "
              f"capital:")
        by_arm = d.groupby("arm")["diff"].agg(
            n="size", median=lambda v: 100 * v.median() / INITIAL_CAPITAL,
            worse=lambda v: int((v < 0).sum()))
        print(by_arm.to_string(float_format=lambda v: f"{v:+.1f}"))

        # margin feasibility
        print(f"\n  maintenance-margin feasibility of the frozen book:")
        feas = {}
        for m in MMR:
            dm = run(season, mmr=m)
            dm = dm.merge(a, on=["tag", "model"])
            ok = dm[dm["breach_day"].isna()]
            feas[m] = {
                "n_breach": int(dm["breach_day"].notna().sum()),
                "n_feasible": int(len(ok)),
                "feasible_hold_pct": 100 * float(ok["hold_net"].sum())
                / (INITIAL_CAPITAL * len(ok)) if len(ok) else np.nan,
                "feasible_realised_pct": 100 * float(ok["equity_change"].sum())
                / (INITIAL_CAPITAL * len(ok)) if len(ok) else np.nan,
                "feasible_better": int((ok["hold_net"]
                                        > ok["equity_change"]).sum()),
            }
            q = feas[m]
            print(f"    mmr {m:>5.1%}: {q['n_breach']:>2} of {len(dm)} breach; "
                  f"on the {q['n_feasible']} feasible accounts the held book "
                  f"returns {q['feasible_hold_pct']:>6.1f}% against "
                  f"{q['feasible_realised_pct']:>6.1f}% realised, beating "
                  f"{q['feasible_better']}")

        # Sensitivity to the freeze point. The default is one of the points
        # swept, so the headline figure is inside the reported range by
        # construction rather than by luck; tests/test_numbers.py checks it.
        print(f"\n  sensitivity to the freeze point:")
        cuts = {}
        for h in CUTOFFS:
            dh = run(season, form_hours=h).merge(a, on=["tag", "model"])
            row = {"hold_pct": 100 * float(dh["hold_net"].sum()) / book,
                   "realised_pct": 100 * float(dh["equity_change"].sum())
                   / book,
                   "better": int((dh["hold_net"] > dh["equity_change"]).sum()),
                   "n": int(len(dh))}
            for m in (0.025, 0.05):
                row[f"breach_{m}"] = int(
                    run(season, form_hours=h, mmr=m)["breach_day"]
                    .notna().sum())
            cuts[h] = row
            print(f"    {h:>3} h: {row['hold_pct']:>6.1f}% against "
                  f"{row['realised_pct']:>6.1f}% realised, beats "
                  f"{row['better']} of {row['n']}, breaches "
                  f"{row['breach_0.025']} at 2.5% and {row['breach_0.05']} "
                  f"at 5%")
        lo_, hi_ = (min(v["hold_pct"] for v in cuts.values()),
                    max(v["hold_pct"] for v in cuts.values()))
        print(f"    sweep range {lo_:.1f} to {hi_:.1f} per cent; the "
              f"{FORM_HOURS}-hour figure is one of these points")

        summary[season] = {
            "formation_hours": FORM_HOURS, "n_accounts": int(len(d)),
            "hold_net": net, "hold_net_pct": 100 * net / book,
            "realised": realised, "realised_pct": 100 * realised / book,
            "gap_pct": 100 * (net - realised) / book,
            "n_better_than_realised": better,
            "hold_net_pct_with_actual_funding": 100 * wf / book,
            "median_paired_diff_pp": float(
                100 * d["diff"].median() / INITIAL_CAPITAL),
            "mean_instruments_held": float(d["instruments_held"].mean()),
            "by_arm": {int(k): float(v) for k, v in
                       (100 * d.groupby("arm")["diff"].median()
                        / INITIAL_CAPITAL).items()},
            "margin": {str(k): v for k, v in feas.items()},
            "cutoffs": {str(k): v for k, v in cuts.items()},
            "sweep_lo_pct": lo_, "sweep_hi_pct": hi_,
        }
        out.append(d)

    pd.concat(out, ignore_index=True).to_csv(
        os.path.join(DER, "a4_exante_benchmark.csv"), index=False)
    with open(os.path.join(DER, "a4_exante_benchmark.json"), "w") as fh:
        json.dump(summary, fh, indent=1)
    print("\nThe terminal book is marked, not liquidated: no closing cost is "
          "charged,\nwhich favours the benchmark.")


if __name__ == "__main__":
    main()
