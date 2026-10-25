"""Which parts of the decomposition survive a change of intraday marks.

The appendix used to argue that an error in an intermediate mark telescopes
out of A + B = sum_t q_{t-1} dP_t. That is wrong, and a referee supplied the
counterexample: the weights move, so perturbing one mark P_s by eta changes
the sum by (q_{s-1} - q_s) eta, which is zero only when the position is
unchanged across s. With positions 1 then 2 and prices 100, 110, 120 the sum
is 30; moving the middle price to 115 gives 25, on unchanged endpoints.

The reported quantity is nonetheless invariant, for a different reason. The
execution adjustment is defined as a residual,

    X = A + B - G,     G = d(realised) + d(mark-to-market), from the fills,

so that

    B - X = G - A.

G is computed from the fills and does not involve the intraday marks at all,
and A = sum_k qbar_k (P_kT - P_k0) involves only the average positions and the
two endpoint valuations. Hence timing less the execution adjustment -- the
figure the letter reports -- is invariant to every intermediate mark, while B
and X individually are not: whatever the marks add to one they take from the
other.

This module demonstrates it on the actual data rather than asserting it. It
perturbs the interior five-minute marks with Gaussian multiplicative noise at
standard deviations up to 2 per cent -- noise that is unbounded, not bounded
by 2 per cent -- holding the window's endpoints and the fills fixed, and
recomputes the decomposition. B and X move by up to twelve per cent of the
book. Since X = A + B - G with A and G unmoved, they move by the same amount
in the SAME direction; it is the signed contributions B and -X that move
oppositely, and their sum B - X does not move at all.

Getting that exact took two corrections to the implementation, both of which
were departures from the stated formula rather than choices. Each instrument's
first print arrives one to twenty-four grid points after the window opens, so
its price series is now extended to both ends of the window. And the mask that
drops t = 0, where the price change is undefined, was also being used to pick
the endpoint price, which took P_1 -- an interior mark -- in place of P_0.
With both fixed the exposure term is a function of the average position and
the two window endpoints alone, exactly as written, and does not move when an
interior mark does.

The noise experiment is a sensitivity analysis, not a bound: it reports the
variation observed under these perturbations, not a maximum over a defined set
of them. The invariance itself is algebraic and does not rest on it.

Writes data/derived/i8_mark_invariance.json.
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
RNG = np.random.default_rng(20261009)
SIZES = (0.001, 0.005, 0.02)          # sd of the multiplicative mark noise
BOOK = 320_000.0


def decompose_with(pan: pd.DataFrame, eq: pd.DataFrame, grid: np.ndarray,
                   noise_sd: float) -> dict:
    """A, B and G over the window, with the interior marks perturbed."""
    A = B = G = 0.0
    for tag, w in pan.groupby("tag"):
        for coin, cg in w.groupby("coin"):
            cg = cg.sort_values("t").set_index("t")
            q = cg["signed_size"].reindex(grid).ffill().fillna(0.0).to_numpy()
            # same extension as src/pnl_decomposition.py, so that the endpoint
            # prices are the window's and not the instrument's first print
            px = (cg["px"].reindex(grid).ffill().bfill().to_numpy())
            if np.isfinite(px).sum() < 3:
                continue
            if noise_sd > 0:
                # interior points only: the endpoints are the settlement marks
                e = RNG.normal(0.0, noise_sd, size=px.shape)
                e[0] = e[-1] = 0.0
                px = px * (1.0 + e)
            q_lag = np.r_[np.nan, q[:-1]]
            dP = np.r_[np.nan, np.diff(px)]
            m = np.isfinite(q_lag) & np.isfinite(dP) & np.isfinite(px)
            if m.sum() < 2:
                continue
            gross = float((q_lag[m] * dP[m]).sum())
            # window endpoints, as in src/pnl_decomposition.py
            exposure = float(q_lag[m].mean() * (px[-1] - px[0]))
            A += exposure
            B += gross - exposure

        e_w = eq[eq["tag"] == tag].sort_values("t").set_index("t")
        rea = e_w["realised"].reindex(grid).ffill()
        mtm = e_w["mtm"].reindex(grid).ffill()
        G += float(np.nansum((rea.diff() + mtm.diff()).to_numpy()))

    return {"A": A, "B": B, "G": G, "X": A + B - G, "B_minus_X": G - A}


def main() -> None:
    fills = pd.read_parquet(os.path.join(DER, "fills.parquet"))
    pan = pd.read_parquet(os.path.join(DER, "panel.parquet"))
    eq = pd.read_parquet(os.path.join(DER, "equity.parquet"))
    lo, hi = analyse.common_window(fills, "S15")
    p = pan[(pan["season"] == "S15") & (pan["t"] >= lo) & (pan["t"] <= hi)]
    e = eq[(eq["season"] == "S15") & (eq["t"] >= lo) & (eq["t"] <= hi)]
    grid = np.sort(p["t"].unique())

    base = decompose_with(p, e, grid, 0.0)
    print("=== Season 1.5, per cent of the $320,000 book ===\n")
    print(f"{'mark noise':<14}{'A exposure':>12}{'B timing':>12}"
          f"{'X execution':>13}{'B - X':>12}")
    print(f"  {'none':<12}" + "".join(
        f"{100 * base[k] / BOOK:>12.2f}" if k != "X" else
        f"{100 * base[k] / BOOK:>13.2f}" for k in ("A", "B", "X", "B_minus_X")))

    rows = []
    for sd in SIZES:
        r = decompose_with(p, e, grid, sd)
        rows.append({"noise_sd": sd, **r})
        print(f"  {sd:<12.3f}" + "".join(
            f"{100 * r[k] / BOOK:>12.2f}" if k != "X" else
            f"{100 * r[k] / BOOK:>13.2f}"
            for k in ("A", "B", "X", "B_minus_X")))

    dB = max(abs(r["B"] - base["B"]) for r in rows)
    dX = max(abs(r["X"] - base["X"]) for r in rows)
    dC = max(abs(r["B_minus_X"] - base["B_minus_X"]) for r in rows)
    print(f"\nlargest movement in dollars: B {dB:,.0f}, X {dX:,.0f} "
          f"(same sign), B - X {dC:,.2e}")
    print("B and X move by the same amount in the same direction, since "
          "X = A + B - G\nwith A and G unmoved; the signed contributions B "
          "and -X move oppositely and\ntheir sum B - X does not move, "
          "because it equals G - A.")

    out = {"base": base, "perturbed": rows,
           "max_abs_move": {"B": dB, "X": dX, "B_minus_X": dC},
           "B_minus_X_pct": 100 * base["B_minus_X"] / BOOK}
    with open(os.path.join(DER, "i8_mark_invariance.json"), "w") as fh:
        json.dump(out, fh, indent=1)


if __name__ == "__main__":
    main()
