"""Robustness of the exposure/timing/slippage split under external marks.

The five-minute marks used in src/pnl_decomposition.py are the pooled last
traded prints of the arena wallets themselves, because Hyperliquid serves no
intraday candles this far back. The sum of the components and the fee line are
therefore safe, but the split between timing and slippage is not: both are
measured against those same marks.

This module re-measures the split against an independent price source, EODHD
5-minute bars for the underlying instrument, once with the internal marks and
once with the external ones, over exactly the same grid points so that the two
are directly comparable. For each wallet and instrument:

    gross    = sum_t  N(t-1) * r(t)
    exposure = mean_t N(t-1) * sum_t r(t)
    timing   = gross - exposure
    slippage = gross - true_gross,   true_gross = d(realised) + d(mtm)

Both seasons are covered, and only one of the two tests is decisive.

Season 1 trades crypto perpetuals, whose underlying spot pairs trade around the
clock. The external series covers every grid point of the window at every hour
of the day, no instrument needs a proxy, and nothing is selected on time of day.
This is the test that answers the question, and it answers it cleanly: the two
marks agree across wallets to 0.99 in both components, both put timing firmly
negative, and the internal marks reproduce the gross P&L implied by the fills to
within one per cent while the external spot series is off by twelve, which is
the perpetual-to-spot basis. The split is not an artefact of marking positions
at the wallets' own prints.

Season 1.5 trades tokenised US equities, which trade 24/7 on Hyperliquid while
the underlying does not, so that comparison is restricted to regular trading
hours (14:30-21:00 UTC) and roughly three quarters of each wallet's exposure
falls outside it. That restriction is a confound, not merely a loss of sample:
true_gross is the change in realised and mark-to-market P&L recorded by the
fills, which accrues around the clock, so no sum of returns measured only inside
the session can reproduce it, under either mark. The level comparison there is
therefore uninformative by construction and is reported only for completeness;
what remains usable is the agreement between the two marks across wallets, which
is weaker than in Season 1 and consistent with observing a quarter of the
exposure. Two further caveats: xyz:XYZ100 is a Nasdaq-100 product with no single
underlying, so QQQ is used as a proxy and flagged, and the surviving sample is
selected on time of day. The Season 1 figures carry neither, which is why they
are the ones quoted.

Instruments with no external equivalent are skipped and reported: @156 is a
Hyperliquid spot index token that no vendor prices.

EODHD needs a subscription. The key is read from EODHD_API_KEY and is redacted
from PROVENANCE.csv; the downloaded bars are not redistributed (see DATA.md).
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
RAW = os.path.join(prov.RAW, "eodhd")
GRID_MS = 5 * 60 * 1000

# Season 1: crypto perpetuals against the vendor's 24/7 spot pairs.
# Season 1.5: tokenised equities against the underlying listing.
SYMBOL = {
    "S1": {"BTC": "BTC-USD.CC", "ETH": "ETH-USD.CC", "SOL": "SOL-USD.CC",
           "BNB": "BNB-USD.CC", "DOGE": "DOGE-USD.CC", "XRP": "XRP-USD.CC"},
    "S15": {"xyz:NVDA": "NVDA.US", "xyz:MSFT": "MSFT.US", "xyz:TSLA": "TSLA.US",
            "xyz:GOOGL": "GOOGL.US", "xyz:AMZN": "AMZN.US",
            "xyz:PLTR": "PLTR.US",
            "xyz:XYZ100": "QQQ.US"},   # proxy for the Nasdaq-100 basket
}
PROXY = {"S1": set(), "S15": {"xyz:XYZ100"}}
# Only the equity season needs a session filter; crypto trades continuously.
RTH_ONLY = {"S1": False, "S15": True}
RTH_OPEN_MIN = 14 * 60 + 30          # 14:30 UTC
RTH_CLOSE_MIN = 21 * 60              # 21:00 UTC


def fetch_bars(sym: str, lo: int, hi: int) -> pd.Series:
    """5-minute bars, cached; the API key never reaches PROVENANCE.csv."""
    key = os.environ.get("EODHD_API_KEY")
    if not key:
        raise SystemExit("EODHD_API_KEY is not set")
    base = (f"https://eodhd.com/api/intraday/{sym}?interval=5m"
            f"&from={lo // 1000}&to={hi // 1000}&fmt=json")
    path = prov.fetch(f"eodhd/{sym}_5m.json", f"{base}&api_token={key}",
                      log_url=f"{base}&api_token=REDACTED")
    if os.path.getsize(path) == 0:
        raise SystemExit(f"empty bars for {sym}")
    with open(path) as fh:
        rows = json.load(fh)
    d = pd.DataFrame(rows)
    d["t"] = (d["timestamp"].astype("int64") * 1000 // GRID_MS) * GRID_MS
    return d[["t", "close"]].dropna().groupby("t")["close"].last()


def rth_mask(t_ms: np.ndarray) -> np.ndarray:
    mins = (t_ms % 86_400_000) // 60_000
    return (mins >= RTH_OPEN_MIN) & (mins < RTH_CLOSE_MIN)


def split(N_lag: np.ndarray, r: np.ndarray) -> tuple[float, float]:
    ok = np.isfinite(N_lag) & np.isfinite(r)
    if ok.sum() < 2:
        return np.nan, np.nan
    gross = float((N_lag[ok] * r[ok]).sum())
    exposure = float(N_lag[ok].mean() * r[ok].sum())
    return exposure, gross - exposure


def run(season: str) -> dict:
    fills = pd.read_parquet(os.path.join(DER, "fills.parquet"))
    pan = pd.read_parquet(os.path.join(DER, "panel.parquet"))
    eq = pd.read_parquet(os.path.join(DER, "equity.parquet"))
    lo, hi = analyse.common_window(fills, season)
    p = pan[(pan["season"] == season) & (pan["t"] >= lo) & (pan["t"] <= hi)]

    traded = set(fills[fills["season"] == season]["coin"].unique())
    skipped = sorted(traded - set(SYMBOL[season]))

    print(f"\n{'=' * 78}\n{season}: downloading EODHD 5-minute bars "
          f"(subscription source)\n{'=' * 78}")
    ext = {}
    for coin, sym in SYMBOL[season].items():
        s = fetch_bars(sym, lo, hi)
        ext[coin] = s
        print(f"  {coin:<12} {sym:<12} {len(s):>5} bars")
    if skipped:
        print(f"  no external equivalent, excluded: {', '.join(skipped)}")

    grid = np.sort(p["t"].unique())
    # the session filter, then whatever the vendor actually served
    in_sess = rth_mask(grid) if RTH_ONLY[season] else np.ones(len(grid), bool)
    if RTH_ONLY[season]:
        # Drop each session's opening point. A five-minute return there spans
        # the close-to-open gap in the external series, while the tokenised
        # instrument traded straight through it, so that one interval would
        # compare two different things. Dropped from both marks equally.
        in_sess = in_sess & np.r_[False, in_sess[:-1]]
    served = np.zeros(len(grid), bool)
    for s in ext.values():
        served |= np.isfinite(s.reindex(grid).ffill().to_numpy())
    keep = in_sess & served
    print(f"\ngrid points {len(grid)}; in session {in_sess.sum()} "
          f"({100 * in_sess.mean():.1f}%); with external marks {keep.sum()} "
          f"({100 * keep.mean():.1f}% of the window)")

    rows = []
    for tag, w in p.groupby("tag"):
        meta = w.iloc[0]
        tot = {"int_exp": 0.0, "int_tim": 0.0, "ext_exp": 0.0, "ext_tim": 0.0}
        for coin, cg in w.groupby("coin"):
            if coin not in ext:
                continue
            cg = cg.sort_values("t").set_index("t")
            size = cg["signed_size"].reindex(grid).ffill().fillna(0.0).to_numpy()
            px_i = cg["px"].reindex(grid).ffill().to_numpy()
            px_e = ext[coin].reindex(grid).ffill().to_numpy()
            # the same points for both marks, so the two splits are comparable
            m = in_sess & np.isfinite(px_e) & np.isfinite(px_i)

            for name, px in (("int", px_i), ("ext", px_e)):
                N = size * px
                N_lag = np.r_[np.nan, N[:-1]]
                r = np.r_[np.nan, px[1:] / px[:-1] - 1.0]
                e_, t_ = split(np.where(m, N_lag, np.nan),
                               np.where(m, r, np.nan))
                tot[f"{name}_exp"] += 0.0 if np.isnan(e_) else e_
                tot[f"{name}_tim"] += 0.0 if np.isnan(t_) else t_

        # true gross over the same intervals, from the fills
        e_w = eq[eq["tag"] == tag].sort_values("t").set_index("t")
        rea = e_w["realised"].reindex(grid).ffill()
        mtm = e_w["mtm"].reindex(grid).ffill()
        d_true = (rea.diff() + mtm.diff()).to_numpy()
        true_gross = float(np.nansum(np.where(in_sess, d_true, 0.0)))

        rows.append({
            "season": season, "model": meta["model"],
            "arm": int(meta["competition_id"]), "tag": tag,
            "int_exposure": tot["int_exp"], "int_timing": tot["int_tim"],
            "ext_exposure": tot["ext_exp"], "ext_timing": tot["ext_tim"],
            "true_gross": true_gross,
            "int_slippage": tot["int_exp"] + tot["int_tim"] - true_gross,
            "ext_slippage": tot["ext_exp"] + tot["ext_tim"] - true_gross,
        })

    d = pd.DataFrame(rows)
    agg = d[["int_exposure", "int_timing", "int_slippage",
             "ext_exposure", "ext_timing", "ext_slippage"]].sum()
    scope = "regular hours" if RTH_ONLY[season] else "all hours"
    print(f"\n--- {season} P&L split over {scope}, internal vs external marks "
          f"(USD, {len(d)} wallets) ---\n")
    print(f"{'component':<12}{'internal marks':>18}{'external marks':>18}"
          f"{'difference':>14}")
    for a, b, lab in [("int_exposure", "ext_exposure", "exposure"),
                      ("int_timing", "ext_timing", "timing"),
                      ("int_slippage", "ext_slippage", "slippage")]:
        print(f"  {lab:<10}{agg[a]:>18,.0f}{agg[b]:>18,.0f}"
              f"{agg[b] - agg[a]:>14,.0f}")
    g_i = agg["int_exposure"] + agg["int_timing"]
    g_e = agg["ext_exposure"] + agg["ext_timing"]
    tg = d["true_gross"].sum()
    print(f"  {'gross':<10}{g_i:>18,.0f}{g_e:>18,.0f}{g_e - g_i:>14,.0f}")
    print(f"  {'true gross':<10}{tg:>18,.0f}")
    print(f"\ngross error against the fills: internal "
          f"{100 * (g_i - tg) / abs(tg):+.1f}%, external "
          f"{100 * (g_e - tg) / abs(tg):+.1f}%")

    corr_e = d["int_exposure"].corr(d["ext_exposure"])
    corr_t = d["int_timing"].corr(d["ext_timing"])

    # A correlation of 1.00 says the two marks order the accounts the same
    # way; it says nothing about whether they agree in level. The referee is
    # right to ask for both, so report the absolute gaps and the agreement of
    # signs and ranks alongside.
    agree = {}
    for lab, a, b in [("exposure", "int_exposure", "ext_exposure"),
                      ("timing", "int_timing", "ext_timing")]:
        gap = (d[b] - d[a]).abs()
        agree[lab] = {
            "mad_usd": float(gap.mean()), "max_usd": float(gap.max()),
            # scale-free: the gap against the typical size of the component
            "mad_rel": float(gap.mean() / d[a].abs().mean()),
            "sign_agree": int((np.sign(d[a]) == np.sign(d[b])).sum()),
            "spearman": float(d[a].corr(d[b], method="spearman")),
            "n": int(len(d)),
        }
    print(f"across the {len(d)} wallets: corr(exposure) = {corr_e:.3f}, "
          f"corr(timing) = {corr_t:.3f}")
    print(f"\n{'component':<11}{'mean |gap|':>12}{'max |gap|':>12}"
          f"{'mean |gap| / mean |level|':>27}{'same sign':>11}{'Spearman':>10}")
    for lab, q in agree.items():
        print(f"  {lab:<9}{q['mad_usd']:>12,.0f}{q['max_usd']:>12,.0f}"
              f"{q['mad_rel']:>26.1%}{q['sign_agree']:>7}/{q['n']:<3}"
              f"{q['spearman']:>10.3f}")
    if PROXY[season]:
        print(f"proxy instrument flagged: {', '.join(sorted(PROXY[season]))}")

    return {
        "rows": d,
        "summary": {
            "season": season,
            "totals": {k: float(v) for k, v in agg.items()},
            "true_gross": float(tg),
            "gross_internal": float(g_i), "gross_external": float(g_e),
            "gross_err_internal": float((g_i - tg) / abs(tg)),
            "gross_err_external": float((g_e - tg) / abs(tg)),
            "n_wallets": int(len(d)),
            "n_grid": int(len(grid)), "n_session": int(in_sess.sum()),
            "n_marked": int(keep.sum()), "coverage": float(keep.mean()),
            "rth_only": bool(RTH_ONLY[season]),
            "corr_exposure": float(corr_e), "corr_timing": float(corr_t),
            "agreement": agree,
            "proxy": sorted(PROXY[season]), "no_external": skipped,
        },
    }


def main() -> None:
    pd.set_option("display.width", 250, "display.max_columns", 40)
    os.makedirs(RAW, exist_ok=True)

    out = {s: run(s) for s in ("S1", "S15")}
    d = pd.concat([out[s]["rows"] for s in out], ignore_index=True)
    d.to_csv(os.path.join(DER, "a3_external_marks.csv"), index=False)
    with open(os.path.join(DER, "a3_external_marks.json"), "w") as fh:
        json.dump({s: out[s]["summary"] for s in out}, fh, indent=1)

    print(f"\n{'=' * 78}\nboth seasons: coverage of the external comparison")
    for s in out:
        q = out[s]["summary"]
        print(f"  {s:<4} {q['coverage'] * 100:>5.1f}% of grid points, "
              f"{q['n_wallets']} wallets, gross error internal "
              f"{q['gross_err_internal'] * 100:+6.1f}% vs external "
              f"{q['gross_err_external'] * 100:+6.1f}%")


if __name__ == "__main__":
    main()
