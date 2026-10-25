"""Item 4: intervals and breakdowns for the headline similarity comparison.

The audit reported, on the official S1.5 window and a 5-minute grid:
    0.669  mean aggregate signed-exposure correlation over the 112 pairs of
           *different* models inside the same competition
    0.676  mean over the 48 pairs of the *same* model in two different
           competitions
Item 4 attaches 95% intervals to both and to their difference by bootstrapping
over days, breaks each down by model, and breaks the second down by which pair
of competitions is involved -- so the arm differences found in item 1 (arm 2
Monk Mode, arm 3 Situational Awareness, arm 4 Max Leverage) are visible rather
than averaged away.

Resampling: moving-block bootstrap over the 13 UTC days, block 3, 2,000 draws;
grid points are carried with their day. A day-level bootstrap is the right unit
because exposure is strongly autocorrelated within a day.

Direction share is computed with the same machinery, vectorised per coin as
    agree = (S Sᵀ + |S| |S|ᵀ) / 2,   both = |S| |S|ᵀ
over the sign matrix S of signed position size.
"""
from __future__ import annotations

import itertools
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import analyse
import prov

DER = os.path.join(prov.ROOT, "data", "derived")
RNG = np.random.default_rng(20261010)
NBOOT = 2000
BLOCK = 3


def build():
    """G (N,T) aggregate signed notional; S list of per-coin sign matrices."""
    fills = pd.read_parquet(os.path.join(DER, "fills.parquet"))
    pan = pd.read_parquet(os.path.join(DER, "panel.parquet"))
    lo, hi = analyse.common_window(fills, "S15")
    p = pan[(pan["season"] == "S15") & (pan["t"] >= lo) & (pan["t"] <= hi)]

    tags = sorted(p["tag"].unique())
    meta = p.groupby("tag")[["model", "competition_id"]].first().loc[tags]
    grid = np.sort(p["t"].unique())
    gi = {t: i for i, t in enumerate(grid)}
    ti = {t: i for i, t in enumerate(tags)}
    coins = sorted(p["coin"].unique())

    G = np.zeros((len(tags), len(grid)))
    Sz = {c: np.zeros((len(tags), len(grid))) for c in coins}
    for (tag, coin), g in p.groupby(["tag", "coin"], sort=False):
        r = ti[tag]
        cols = g["t"].map(gi).to_numpy()
        G[r, cols] += np.nan_to_num(g["signed_notional"].to_numpy())
        Sz[coin][r, cols] = g["signed_size"].to_numpy()

    S = {c: np.sign(np.where(np.abs(v) < 1e-12, 0.0, v)) for c, v in Sz.items()}
    day = (grid // 86_400_000).astype(np.int64)
    days = np.unique(day)
    day_cols = [np.where(day == d)[0] for d in days]
    return G, S, tags, meta, day_cols, coins


def corr_matrix(M: np.ndarray) -> np.ndarray:
    Mc = M - M.mean(axis=1, keepdims=True)
    sd = np.sqrt((Mc**2).sum(axis=1))
    sd[sd == 0] = np.nan
    return (Mc @ Mc.T) / np.outer(sd, sd)


def direction_share(S: dict, cols: np.ndarray, ever: dict) -> np.ndarray:
    """Mean over coins (where both wallets ever traded) of the same-sign share."""
    N = next(iter(S.values())).shape[0]
    tot = np.zeros((N, N))
    cnt = np.zeros((N, N))
    for c, Sm in S.items():
        s = Sm[:, cols]
        a = np.abs(s)
        M = s @ s.T
        Nn = a @ a.T
        with np.errstate(divide="ignore", invalid="ignore"):
            share = np.where(Nn > 0, (M + Nn) / (2 * Nn), np.nan)
        ok = ever[c] & ~np.isnan(share)
        tot[ok] += share[ok]
        cnt[ok] += 1
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(cnt > 0, tot / cnt, np.nan)


def pair_sets(tags, meta):
    within, across = [], []
    for i, j in itertools.combinations(range(len(tags)), 2):
        a, b = tags[i], tags[j]
        ca, cb = meta.loc[a, "competition_id"], meta.loc[b, "competition_id"]
        ma, mb = meta.loc[a, "model"], meta.loc[b, "model"]
        if ca == cb and ma != mb:
            within.append((i, j, ma, mb, ca, cb))
        elif ca != cb and ma == mb:
            across.append((i, j, ma, mb, ca, cb))
    return within, across


def summarise(M: np.ndarray, within, across) -> dict:
    wi = np.array([M[i, j] for i, j, *_ in within])
    ac = np.array([M[i, j] for i, j, *_ in across])
    out = {
        "within_mean": np.nanmean(wi),
        "across_mean": np.nanmean(ac),
        "diff": np.nanmean(wi) - np.nanmean(ac),
    }
    # by model
    for lbl, pairs in [("within", within), ("across", across)]:
        for mdl in sorted({p[2] for p in within} | {p[2] for p in across}):
            v = [M[i, j] for i, j, ma, mb, *_ in pairs if ma == mdl or mb == mdl]
            out[f"{lbl}__{mdl}"] = np.nanmean(v) if v else np.nan
    # within by competition
    for c in sorted({p[4] for p in within}):
        v = [M[i, j] for i, j, _, _, ca, _ in within if ca == c]
        out[f"within_comp{c}"] = np.nanmean(v)
    # across by competition pair
    for ca, cb in itertools.combinations(sorted({p[4] for p in within}), 2):
        v = [
            M[i, j]
            for i, j, _, _, x, y in across
            if {x, y} == {ca, cb}
        ]
        out[f"across_c{ca}c{cb}"] = np.nanmean(v) if v else np.nan
    return out


def block_days(nd: int, block: int, n: int) -> np.ndarray:
    nb = int(np.ceil(nd / block))
    starts = RNG.integers(0, nd, size=(n, nb))
    off = np.arange(block)
    return ((starts[:, :, None] + off[None, None, :]) % nd).reshape(n, -1)[:, :nb * block][:, :nd]


def main() -> None:
    pd.set_option("display.width", 250, "display.max_columns", 80)
    G, S, tags, meta, day_cols, coins = build()
    nd = len(day_cols)
    within, across = pair_sets(tags, meta)
    print(f"grid {G.shape[1]} points over {nd} days; "
          f"{len(within)} different-model pairs, {len(across)} same-model pairs")

    allcols = np.concatenate(day_cols)
    ever = {
        c: (np.abs(S[c]).sum(axis=1) > 0)[:, None] & (np.abs(S[c]).sum(axis=1) > 0)[None, :]
        for c in coins
    }

    point = {
        "exposure_corr": summarise(corr_matrix(G[:, allcols]), within, across),
        "direction_share": summarise(direction_share(S, allcols, ever), within, across),
    }
    print("\n=== point estimates (full sample) ===")
    for met, d in point.items():
        print(f"  {met}: within {d['within_mean']:.4f}  across {d['across_mean']:.4f}  "
              f"diff {d['diff']:+.4f}")

    draws = block_days(nd, BLOCK, NBOOT)
    boot = {"exposure_corr": [], "direction_share": []}
    for b in range(NBOOT):
        cols = np.concatenate([day_cols[d] for d in draws[b]])
        boot["exposure_corr"].append(summarise(corr_matrix(G[:, cols]), within, across))
        boot["direction_share"].append(
            summarise(direction_share(S, cols, ever), within, across)
        )

    rows = []
    for met in boot:
        bd = pd.DataFrame(boot[met])
        for k in bd.columns:
            v = bd[k].to_numpy(dtype=float)
            rows.append(
                {
                    "metric": met,
                    "quantity": k,
                    "estimate": point[met][k],
                    "ci_lo": np.nanpercentile(v, 2.5),
                    "ci_hi": np.nanpercentile(v, 97.5),
                    "boot_sd": np.nanstd(v, ddof=1),
                }
            )
    res = pd.DataFrame(rows)
    res.to_csv(os.path.join(DER, "i4_similarity_ci.csv"), index=False)

    def show(met, keys, title):
        d = res[(res["metric"] == met) & (res["quantity"].isin(keys))]
        d = d.set_index("quantity").loc[[k for k in keys if k in set(d["quantity"])]]
        print(f"\n--- {title} ---")
        print(
            d[["estimate", "ci_lo", "ci_hi", "boot_sd"]]
            .to_string(float_format=lambda x: f"{x:,.4f}")
        )

    models = sorted(meta["model"].unique())
    comps = sorted(meta["competition_id"].unique())
    for met in ["exposure_corr", "direction_share"]:
        print(f"\n{'='*78}\n{met}\n{'='*78}")
        show(met, ["within_mean", "across_mean", "diff"], "headline, 95% bootstrap CI")
        show(met, [f"within__{m}" for m in models] + [f"across__{m}" for m in models],
             "by model")
        show(met, [f"within_comp{c}" for c in comps], "different-model pairs, by competition")
        show(met, [f"across_c{a}c{b}" for a, b in itertools.combinations(comps, 2)],
             "same-model pairs, by competition pair")

    with open(os.path.join(DER, "i4_summary.json"), "w") as fh:
        json.dump({m: point[m] for m in point}, fh, indent=1, default=float)


if __name__ == "__main__":
    main()
