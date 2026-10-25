"""Attribute wallet equity changes using average positions in instrument units.

A = sum_k mean_t(q[k,t-1]) * (P[k,T]-P[k,0]);
B = sum_{k,t} q[k,t-1] * delta(P[k,t]) - A;
G is realised fill P&L plus the change in terminal marked open-position P&L.
X = A+B-G is an execution/valuation adjustment, not a bound on true slippage.
The signed contributions satisfy delta(E)=A+B-X-fees+funding.
B-X=G-A is invariant to interior marks when positions, endpoints and G are
fixed. Closure is an accounting identity, not independent validation.
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


def decompose(season: str) -> pd.DataFrame:
    fills = pd.read_parquet(os.path.join(DER, "fills.parquet"))
    pan = pd.read_parquet(os.path.join(DER, "panel.parquet"))
    eq = pd.read_parquet(os.path.join(DER, "equity.parquet"))
    fu = pd.read_parquet(os.path.join(DER, "funding.parquet"))
    lo, hi = analyse.common_window(fills, season)

    p = pan[(pan["season"] == season) & (pan["t"] >= lo) & (pan["t"] <= hi)]
    f = fills[(fills["season"] == season) & (fills["time"] >= lo)
              & (fills["time"] <= hi)]
    g = fu[(fu["season"] == season) & (fu["time"] >= lo) & (fu["time"] <= hi)]
    e = eq[(eq["season"] == season) & (eq["t"] >= lo) & (eq["t"] <= hi)]

    # One price series per coin, shared by every wallet in the season, and
    # extended to both ends of the window. Each instrument's first print
    # arrives a few grid points after the window opens (one to twenty-four
    # here, five minutes to two hours); without the extension the "endpoint"
    # prices in the exposure term would be interior marks, and the identity
    # B - X = G - A would not hold against a change of interior marks. The
    # extension carries the first and last observed price outward, which is
    # the convention the appendix states.
    px = (
        p.groupby(["coin", "t"])["px"].first().unstack(0).sort_index()
        .ffill().bfill()
    )
    ret = px.pct_change()

    rows = []
    for tag, w in p.groupby("tag"):
        exposure = timing = 0.0
        percoin = {}
        for coin, cg in w.groupby("coin"):
            # Exposure is the average position in UNITS carried through the
            # endpoint price change, which is the definition the appendix
            # states and the only one that makes timing less the execution
            # adjustment free of the intraday marks. An earlier version used
            # the average notional times the sum of simple returns; that
            # leaves the same gross -- sum_t q_{t-1} dP_t either way -- but
            # splits it with a denominator that the marks themselves move.
            q = cg.sort_values("t").set_index("t")["signed_size"]
            q = q.reindex(px.index).ffill().fillna(0.0)
            P = px[coin].reindex(px.index)
            lagq = q.shift(1)
            dP = P.diff()
            ok = lagq.notna() & dP.notna() & P.notna()
            gross_c = float((lagq[ok] * dP[ok]).sum())
            qbar = float(lagq[ok].mean())
            # The endpoints are the window's, P_0 and P_T, not the first and
            # last point of the masked subset: the mask drops t = 0, where
            # dP is undefined, so taking its first element would use P_1 --
            # an interior mark -- and the exposure term would move when the
            # interior marks moved. For a constant position sum_t q dP
            # telescopes to q(P_T - P_0), which is the quantity this matches.
            exp_c = qbar * float(P.iloc[-1] - P.iloc[0])
            exposure += exp_c
            timing += gross_c - exp_c
            percoin[coin] = {"gross": gross_c, "exposure": exp_c,
                             "timing": gross_c - exp_c, "qbar": qbar}
        fee = float(f[f["tag"] == tag]["fee"].sum())
        fund = float(g[g["tag"] == tag]["usdc"].sum())
        we = e[e["tag"] == tag].sort_values("t")
        ee = we["equity"]
        d_eq = float(ee.iloc[-1] - ee.iloc[0]) if len(we) else np.nan
        # actual gross P&L implied by the fills: d(realised) + d(mtm)
        true_gross = (
            float(we["realised"].iloc[-1] - we["realised"].iloc[0])
            + float(we["mtm"].iloc[-1] - we["mtm"].iloc[0])
        ) if len(we) else np.nan
        meta = w.iloc[0]
        rows.append(
            {
                "season": season,
                "competition_id": int(meta["competition_id"]),
                "model": meta["model"],
                "tag": tag,
                "exposure_pnl": exposure,
                "timing_pnl": timing,
                "gross_pnl": exposure + timing,
                "true_gross_pnl": true_gross,
                "slippage": exposure + timing - true_gross,
                "fees": fee,
                "funding": fund,
                "net_pnl": true_gross - fee + fund,
                "equity_change": d_eq,
                "percoin": json.dumps(percoin),
            }
        )
    df = pd.DataFrame(rows)
    df["check_gap"] = df["net_pnl"] - df["equity_change"]
    df["check_gap_pct_of_book"] = 100 * df["check_gap"] / 10000.0
    return df


def main() -> None:
    pd.set_option("display.width", 260, "display.max_columns", 50)
    out = []
    for season in ["S1", "S15"]:
        d = decompose(season)
        out.append(d)
        print(f"\n{'='*86}\n{season}: P&L decomposition, $ per $10,000 wallet\n{'='*86}")
        cols = ["competition_id", "model", "exposure_pnl", "timing_pnl",
                "slippage", "fees", "funding", "net_pnl", "equity_change",
                "check_gap"]
        print(d[cols].to_string(index=False, float_format=lambda x: f"{x:,.0f}"))
        print(f"\n  identity check |net - equity change|: mean "
              f"{d['check_gap'].abs().mean():,.0f}, max {d['check_gap'].abs().max():,.0f} "
              f"({d['check_gap_pct_of_book'].abs().max():.2f}% of a $10k book)")
        tot = d[["exposure_pnl", "timing_pnl", "slippage", "fees", "funding",
                 "net_pnl"]].sum()
        print(f"  season totals: exposure {tot.exposure_pnl:+,.0f}  "
              f"timing {tot.timing_pnl:+,.0f}  slippage {-tot.slippage:+,.0f}  "
              f"fees {-tot.fees:+,.0f}  funding {tot.funding:+,.0f}  "
              f"net {tot.net_pnl:+,.0f}")

    alld = pd.concat(out, ignore_index=True)
    alld.drop(columns=["percoin"]).to_csv(
        os.path.join(DER, "a1_pnl_decomposition.csv"), index=False
    )
    alld.to_parquet(os.path.join(DER, "a1_pnl_decomposition.parquet"), index=False)

    print(f"\n{'='*86}\nBy model, S1.5 (sum over the four arms, $ per $40,000)\n{'='*86}")
    s15 = alld[alld["season"] == "S15"]
    bym = (
        s15.groupby("model")[["exposure_pnl", "timing_pnl", "slippage", "fees", "funding", "net_pnl"]]
        .sum()
        .sort_values("net_pnl", ascending=False)
    )
    bym["net_%_of_40k"] = 100 * bym["net_pnl"] / 40000
    print(bym.to_string(float_format=lambda x: f"{x:,.0f}"))

    print(f"\nBy arm, S1.5 (sum over the eight models, $ per $80,000)")
    bya = s15.groupby("competition_id")[
        ["exposure_pnl", "timing_pnl", "slippage", "fees", "funding", "net_pnl"]
    ].sum()
    print(bya.to_string(float_format=lambda x: f"{x:,.0f}"))

    with open(os.path.join(DER, "a1_pnl_summary.json"), "w") as fh:
        json.dump(
            {
                "by_model_S15": bym.reset_index().to_dict("records"),
                "by_arm_S15": bya.reset_index().to_dict("records"),
                "totals": {
                    s: alld[alld["season"] == s][
                        ["exposure_pnl", "timing_pnl", "slippage", "fees",
                         "funding", "net_pnl"]
                    ].sum().to_dict()
                    for s in ["S1", "S15"]
                },
                "identity_max_gap_pct": float(
                    alld["check_gap_pct_of_book"].abs().max()
                ),
            },
            fh,
            indent=1,
            default=float,
        )


if __name__ == "__main__":
    main()
