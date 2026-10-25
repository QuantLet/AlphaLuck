"""fig3: the risk-return relation, at model level and at account level.

Volatility is measured against initial capital, the standard deviation of
daily profit and loss in units of the 10,000 each account was funded with.
Against current equity the same figure rises when an account loses, so plotting
the return on it would put part of the vertical axis into the horizontal one.
"""
from __future__ import annotations
import os, sys
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), "src"))
import style

from scipy import stats as st

# label placement for panel (a): the lower cluster is tight, so the four
# crowded models get explicit offsets and the rest fall back to the default.
OFFSET = {
    # tuned for the fixed-denominator axis: the cluster near 6% is tight
    "qwen3-max":            (-4, -11, "right"),
    "claude-sonnet-4-5":    (0, -12, "center"),
    "gemini-3-pro-preview": (0, 8, "center"),
    "typhoon":              (6, -2, "left"),
    "kimi-k2-thinking":     (0, -12, "center"),
    "grok-4":               (6, 2, "left"),
    "deepseek-chat-v3.1":   (0, 8, "center"),
}


def main():
    style.apply()
    w = pd.read_csv(os.path.join(style.DER, "c4_wallet_risk.csv"))
    fx = pd.read_csv(os.path.join(style.DER, "i6_vol_denominator.csv"))
    w = w.merge(fx[["tag", "vol_fixed"]], on="tag", how="left")
    import json
    vd = json.load(open(os.path.join(style.DER, "i6_vol_denominator.json")))

    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.3))

    # (a) model means, n = 8
    g = w.groupby("model").agg(vol=("vol_fixed", "mean"),
                               ret=("final_return_pct", "mean"))
    ax = axes[0]
    for m, r in g.iterrows():
        ax.scatter(100 * r.vol, r.ret, color=style.colour(m),
                   marker=style.marker(m), s=55, zorder=3,
                   edgecolors="none")
        dx, dy, ha = OFFSET.get(m, (7, 3, "left"))
        ax.annotate(m, (100 * r.vol, r.ret), textcoords="offset points",
                    xytext=(dx, dy), ha=ha, fontsize=6.5, color=style.INK)
    ax.axhline(0, color=style.INK, lw=0.5, alpha=0.5, zorder=0)
    ax.set_xlabel("sd of daily P&L, % of initial capital")
    ax.set_ylabel("mean final return (%)")
    ax.set_xlim(2.2, 14.6)
    mg = st.spearmanr(g.vol, g.ret)
    style.panel_label(
        ax, f"(a) models, n = 8   " + r"$\rho$" + f" = {mg.statistic:.2f}")

    # (b) wallets, n = 32, within-arm ranks
    ax = axes[1]
    for a, gg in w.groupby("arm"):
        rx = st.rankdata(gg["vol_fixed"])
        ry = st.rankdata(gg["final_return_pct"])
        ax.scatter(rx, ry, marker=style.ARM_MARKER[a], s=42,
                   facecolors="none", linewidths=1.0,
                   edgecolors=style.INK, alpha=0.85, zorder=3,
                   label=f"arm {style.ARM_NAME[a]}")
    ax.set_xlabel("within-arm rank of volatility (1 = lowest)")
    ax.set_ylabel("within-arm rank of final return")
    ax.set_xticks(range(1, 9)); ax.set_yticks(range(1, 9))
    t = vd["vol_fixed"]
    style.panel_label(
        ax, f"(b) accounts, n = 32   mean within-arm " + r"$\rho$" +
            f" = {t['assoc_rho']:.2f}, perm p = {t['assoc_p_two_sided']:.3f}")

    handles, labels = ax.get_legend_handles_labels()
    fig.subplots_adjust(wspace=0.42, bottom=0.2)
    leg = fig.legend(handles=handles, labels=labels, loc="upper center",
                     bbox_to_anchor=(0.5, 0.04), ncol=4, frameon=False,
                     handletextpad=0.4, columnspacing=1.2)
    for tx in leg.get_texts():
        tx.set_color(style.INK)
    style.save(fig, "fig3_risk_return", extra_artists=[leg])

if __name__ == "__main__":
    main()
