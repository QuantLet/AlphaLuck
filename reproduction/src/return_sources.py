"""Does the leaderboard order the trading component or the exposure component?

The letter concludes that a ranking on final returns "orders mainly how much
each model lost by trading". That is a statement about ordering, and ordering
is not what the aggregate decomposition measures: the aggregate says the
trading terms are large and the exposure term small, which makes the claim
plausible but does not test it.

This tests it. For each account, split the change in equity into

    trading  = timing - execution adjustment - fees
    exposure = the average-position term

and rank each against the final return within its arm, since the arms differ
in both. The statistic is the mean within-arm Spearman correlation, and the
p-value comes from permuting accounts within arm, which preserves the arm
composition and is the same scheme used for the risk-return associations.

Funding is left out of both: it is a transfer the account neither chose nor
controls, and it is 0.4 per cent of capital in Season 1.5. Its omission is why
the two correlations are not mechanically tied to each other.

Writes data/derived/i7_return_sources.json.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import prov

DER = os.path.join(prov.ROOT, "data", "derived")
RNG = np.random.default_rng(20261009)
NPERM = 20000


def within_arm(d: pd.DataFrame, col: str) -> dict:
    arms = sorted(d["arm"].unique())

    def stat(frame: pd.DataFrame) -> float:
        return float(np.mean([
            stats.spearmanr(frame[frame["arm"] == a][col],
                            frame[frame["arm"] == a]["final_return"]).statistic
            for a in arms]))

    obs = stat(d)
    cnt = 0
    for _ in range(NPERM):
        p = d.copy()
        p[col] = np.concatenate([
            RNG.permutation(d[d["arm"] == a][col].to_numpy()) for a in arms])
        if abs(stat(p)) >= abs(obs):
            cnt += 1
    per_arm = {int(a): float(stats.spearmanr(
        d[d["arm"] == a][col], d[d["arm"] == a]["final_return"]).statistic)
        for a in arms}
    return {"rho": obs, "p_two_sided": (cnt + 1) / (NPERM + 1),
            "per_arm": per_arm}


def main() -> None:
    pd.set_option("display.width", 250, "display.max_columns", 40)
    acc = pd.read_parquet(os.path.join(DER, "accounts.parquet"))
    d = acc[acc["season"] == "S15"].copy()
    d = d.rename(columns={"competition_id": "arm"})

    # the signs follow the identity net = exposure + timing - slippage - fees
    d["trading"] = (d["pnl_timing_pnl"] - d["pnl_slippage"] - d["pnl_fees"])
    d["exposure"] = d["pnl_exposure_pnl"]

    out = {}
    print("=== what does the final ranking follow? "
          "(32 accounts, within arm) ===\n")
    for col, lab in [("trading", "trading component (timing - execution - fees)"),
                     ("exposure", "exposure component (average position)")]:
        r = within_arm(d, col)
        out[col] = r
        print(f"  {lab}")
        print(f"    mean within-arm Spearman {r['rho']:+.3f}   "
              f"permutation p = {r['p_two_sided']:.4f}")
        print(f"    by arm: " + ", ".join(f"{a}: {v:+.2f}"
                                          for a, v in r["per_arm"].items()))
        print()

    # how much of the cross-account spread each component carries
    for col in ("trading", "exposure"):
        out[f"{col}_sd_pct"] = float(d[col].std(ddof=1) / 10_000 * 100)
    print(f"  cross-account sd, per cent of initial capital: "
          f"trading {out['trading_sd_pct']:.1f}, "
          f"exposure {out['exposure_sd_pct']:.1f}")

    out["n"] = int(len(d))
    with open(os.path.join(DER, "i7_return_sources.json"), "w") as fh:
        json.dump(out, fh, indent=1)


if __name__ == "__main__":
    main()
