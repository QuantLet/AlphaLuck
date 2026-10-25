"""Risk measured against a denominator that cannot move.

The continuation-sample check showed that gross leverage over *current* equity
is partly an arithmetic consequence of losses: an account that has lost money
shows higher leverage without having chosen a larger position, and the
in-season model effect fell from F = 8.18 to 2.11 once the denominator was
fixed at initial capital.

Realised daily volatility has the same problem in a subtler form. It is the
standard deviation of daily *returns*, and a return is a dollar change divided
by the previous day's equity. An account that has halved its equity turns the
same dollar swing into twice the return, so a model that lost early will look
more volatile afterwards whether or not it changed its behaviour.

This module recomputes volatility as

    sd_d( (E_d - E_{d-1}) / 10,000 ),

the standard deviation of daily profit and loss expressed in units of initial
capital. The denominator is the same number for every account on every day, so
the measure moves only when the dollar swings do. Both versions are run
through the same three analyses:

    (a) the in-season trait test -- two-way ANOVA on the 8 x 4 layout, the
        arm-adjusted ICC with its exact interval, Kendall's W across arms, and
        a permutation of model labels within arm;
    (b) persistence into the adjacent continuation sample;
    (c) the within-arm rank correlation with the final return.

Nothing downstream is changed here. The point of the module is to say whether
the volatility result survives the fixed denominator, so that the manuscript
can state whichever answer is true.

Writes data/derived/i6_vol_denominator.{csv,json}.
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
DAY_MS = 86_400_000
INITIAL_CAPITAL = 10_000.0
RNG = np.random.default_rng(20261009)
NPERM = 20000


def daily_frame(lo: int, hi: int) -> pd.DataFrame:
    """Per account: both denominators for volatility and turnover, plus return."""
    eq = pd.read_parquet(os.path.join(DER, "equity.parquet"))
    fills = pd.read_parquet(os.path.join(DER, "fills.parquet"))
    e = eq[(eq["season"] == "S15") & (eq["t"] >= lo) & (eq["t"] <= hi)].copy()
    e["day"] = e["t"] // DAY_MS
    dayend = (e.sort_values("t").groupby(["tag", "day"])["equity"].last()
              .unstack())
    meta = e.groupby("tag")[["model", "competition_id"]].first()

    ret = dayend.pct_change(axis=1).iloc[:, 1:]            # current-equity base
    pnl = dayend.diff(axis=1).iloc[:, 1:] / INITIAL_CAPITAL  # fixed base

    # Turnover has the same problem: traded notional divided by an equity that
    # falls as the account loses. The fixed version divides by the 10,000 the
    # account was funded with.
    f = fills[(fills["season"] == "S15") & (fills["time"] >= lo)
              & (fills["time"] <= hi)].copy()
    f["notional"] = f["sz"].abs() * f["px"]
    notional = f.groupby("tag")["notional"].sum()
    ndays = ret.notna().sum(axis=1)
    mean_eq = dayend.mean(axis=1)

    # Gross leverage, the measure the referee started from, on both
    # denominators: mean over grid points of gross notional over current
    # equity, and over the 10,000 the account was funded with.
    pan = pd.read_parquet(os.path.join(DER, "panel.parquet"))
    pp = pan[(pan["season"] == "S15") & (pan["t"] >= lo) & (pan["t"] <= hi)]
    gross = (pp.assign(absn=pp["signed_notional"].abs())
             .groupby(["tag", "t"])["absn"].sum())
    eqs = (e.sort_values("t").set_index(["tag", "t"])["equity"]
           .groupby(level=0).ffill())
    gi = gross.index
    eq_on_grid = eqs.reindex(gi).groupby(level=0).ffill()
    lev_eq = (gross / eq_on_grid.replace(0, np.nan)).groupby(level=0).mean()
    lev_fx = (gross / INITIAL_CAPITAL).groupby(level=0).mean()

    out = pd.DataFrame({
        "vol_equity": ret.std(axis=1, ddof=1),
        "vol_fixed": pnl.std(axis=1, ddof=1),
        "turnover_equity": notional / (mean_eq * ndays) * 100.0,
        "turnover_fixed": notional / (INITIAL_CAPITAL * ndays) * 100.0,
        "leverage_equity": lev_eq,
        "leverage_fixed": lev_fx,
        "n_days": ndays,
        "final_return": dayend.iloc[:, -1] / INITIAL_CAPITAL - 1.0,
    }).join(meta)
    return out.rename(columns={"competition_id": "arm"}).reset_index()


def anova_icc(y: np.ndarray) -> dict:
    """Two-way layout, one observation per cell: model F and arm-adjusted ICC."""
    k, a = y.shape
    grand = y.mean()
    ss_m = a * ((y.mean(axis=1) - grand) ** 2).sum()
    ss_a = k * ((y.mean(axis=0) - grand) ** 2).sum()
    ss_e = ((y - grand) ** 2).sum() - ss_m - ss_a
    df_m, df_a, df_e = k - 1, a - 1, (k - 1) * (a - 1)
    ms_m, ms_a, ms_e = ss_m / df_m, ss_a / df_a, ss_e / df_e
    F = ms_m / ms_e
    icc = (ms_m - ms_e) / (ms_m + (a - 1) * ms_e)
    fl = F / stats.f.ppf(1 - 0.05 / 2, df_m, df_e)
    fu = F * stats.f.ppf(1 - 0.05 / 2, df_e, df_m)
    return {"F_model": float(F), "p_model": float(stats.f.sf(F, df_m, df_e)),
            "icc": float(icc),
            "icc_lo": float((fl - 1) / (fl + a - 1)),
            "icc_hi": float((fu - 1) / (fu + a - 1)),
            "F_arm": float(ms_a / ms_e),
            "p_arm": float(stats.f.sf(ms_a / ms_e, df_a, df_e))}


def kendall_w(y: np.ndarray) -> dict:
    """Do the arms agree on the ordering of models?"""
    k, a = y.shape
    ranks = np.apply_along_axis(stats.rankdata, 0, y)
    S = ((ranks.sum(axis=1) - a * (k + 1) / 2) ** 2).sum()
    tie_sum = 0
    for j in range(a):
        counts = np.unique(ranks[:, j], return_counts=True)[1]
        tie_sum += np.sum(counts**3 - counts)
    denominator = a ** 2 * (k ** 3 - k) - a * tie_sum
    Wst = 12 * S / denominator if denominator > 0 else np.nan
    cnt = 0
    for _ in range(NPERM):
        rp = np.column_stack([RNG.permutation(ranks[:, j]) for j in range(a)])
        Sp = ((rp.sum(axis=1) - a * (k + 1) / 2) ** 2).sum()
        if Sp >= S:
            cnt += 1
    return {"W": float(Wst), "p_W_perm": (cnt + 1) / (NPERM + 1)}


def perm_F(y: np.ndarray, obs_F: float, rng=None) -> float:
    """Permute model labels within arm; optionally use an isolated RNG."""
    rng = RNG if rng is None else rng
    cnt = 0
    for _ in range(NPERM):
        yp = np.column_stack([rng.permutation(y[:, j]) for j in range(y.shape[1])])
        if anova_icc(yp)["F_model"] >= obs_F:
            cnt += 1
    return (cnt + 1) / (NPERM + 1)


def within_arm_rho(d: pd.DataFrame, col: str) -> dict:
    """Mean within-arm rank correlation with the final return, permuted."""
    arms = sorted(d["arm"].unique())

    def stat(frame):
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
        p["arm"] = np.concatenate([
            d[d["arm"] == a]["arm"].to_numpy() for a in arms])
        p["final_return"] = np.concatenate([
            d[d["arm"] == a]["final_return"].to_numpy() for a in arms])
        if abs(stat(p)) >= abs(obs):
            cnt += 1
    return {"rho": obs, "p_two_sided": (cnt + 1) / (NPERM + 1)}


def analyse_one(d: pd.DataFrame, col: str) -> dict:
    models = sorted(d["model"].unique())
    arms = sorted(d["arm"].unique())
    y = d.pivot(index="model", columns="arm", values=col).loc[models, arms]
    y = y.to_numpy(float)
    res = anova_icc(y)
    res.update(kendall_w(y))
    res["p_perm"] = perm_F(y, res["F_model"])
    res.update({f"assoc_{k}": v for k, v in within_arm_rho(d, col).items()})
    return res


def main() -> None:
    pd.set_option("display.width", 260, "display.max_columns", 40)
    fills = pd.read_parquet(os.path.join(DER, "fills.parquet"))
    lo, hi = analyse.common_window(fills, "S15")
    _, on_hi = analyse.common_window(fills, "S15", official=False)

    ins = daily_frame(lo, hi)
    cont = daily_frame(W.S15_OFFICIAL_END_MS, on_hi)
    ins.to_csv(os.path.join(DER, "i6_vol_denominator.csv"), index=False)

    print(f"in-season daily observations per account: "
          f"{sorted(ins['n_days'].unique())}")
    print(f"continuation daily observations: {sorted(cont['n_days'].unique())}\n")

    out = {}
    for col, lab in [
            ("vol_equity", "volatility, returns on current equity (published)"),
            ("vol_fixed", "volatility, daily P&L on initial capital (fixed)"),
            ("turnover_equity", "turnover on current equity (published)"),
            ("turnover_fixed", "turnover on initial capital (fixed)"),
            ("leverage_equity", "gross leverage on current equity (published)"),
            ("leverage_fixed", "gross exposure on initial capital (fixed)")]:
        r = analyse_one(ins, col)
        j = ins[["tag", col]].merge(cont[["tag", col]], on="tag",
                                    suffixes=("_in", "_post"))
        rho = stats.spearmanr(j[f"{col}_in"], j[f"{col}_post"]).statistic
        r["persist_rho"] = float(rho)
        out[col] = r
        print(f"=== {lab} ===")
        print(f"  model effect      F = {r['F_model']:.2f}  "
              f"p = {r['p_model']:.4f}   permutation p = {r['p_perm']:.4f}")
        print(f"  arm-adjusted ICC  {r['icc']:.3f}  "
              f"[{r['icc_lo']:.3f}, {r['icc_hi']:.3f}]")
        print(f"  Kendall's W       {r['W']:.3f}  p = {r['p_W_perm']:.4f}")
        print(f"  arm effect        F = {r['F_arm']:.2f}  p = {r['p_arm']:.4f}")
        print(f"  persistence rho   {r['persist_rho']:.3f}")
        print(f"  return assoc rho  {r['assoc_rho']:.3f}  "
              f"p = {r['assoc_p_two_sided']:.4f}\n")

    a, b = out["vol_equity"], out["vol_fixed"]
    print("--- does the volatility result survive the fixed denominator? ---")
    survives = (b["p_perm"] < 0.05 and b["icc_lo"] > 0)
    print(f"  F {a['F_model']:.2f} -> {b['F_model']:.2f}, "
          f"ICC {a['icc']:.2f} -> {b['icc']:.2f}, "
          f"permutation p {a['p_perm']:.4f} -> {b['p_perm']:.4f}")
    print(f"  interval clear of zero on the fixed denominator: "
          f"{b['icc_lo'] > 0}")
    print(f"  VERDICT: {'SURVIVES' if survives else 'DOES NOT SURVIVE'}")

    out["survives"] = bool(survives)
    out["n_days_in"] = int(ins["n_days"].iloc[0])
    out["n_days_cont"] = int(cont["n_days"].iloc[0])
    with open(os.path.join(DER, "i6_vol_denominator.json"), "w") as fh:
        json.dump(out, fh, indent=1, default=float)


if __name__ == "__main__":
    main()
