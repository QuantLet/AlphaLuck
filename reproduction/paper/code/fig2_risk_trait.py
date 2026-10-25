"""fig2: descriptive gross-exposure and volatility profiles across arms."""
from __future__ import annotations
import os, sys
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), "src"))
import style


def main():
    style.apply()
    w = pd.read_csv(os.path.join(style.DER, "c4_wallet_risk.csv"))
    # Both measures use initial capital to compare dollar risk on a common
    # starting budget. Current equity measures risk to remaining wealth;
    # the manuscript reports both legitimate definitions.
    fx = pd.read_csv(os.path.join(style.DER, "i6_vol_denominator.csv"))
    w = w.merge(fx[["tag", "vol_fixed", "leverage_fixed"]], on="tag")
    arms = sorted(w["arm"].unique())
    specs = [("leverage_fixed", "gross exposure (x initial capital)", "(a)"),
             ("vol_fixed", "sd of daily P&L (% of initial capital)", "(b)")]

    fig, axes = plt.subplots(1, 2, figsize=(7.0, 3.0))
    order = (w.groupby("model")["leverage_fixed"].mean()
             .sort_values(ascending=False).index.tolist())
    for ax, (met, ylab, lab) in zip(axes, specs):
        piv = w.pivot(index="model", columns="arm", values=met).loc[order]
        if met == "vol_fixed":
            piv = piv * 100
        # Arms are categories, not an ordered scale: dots side by side
        # within each arm, no connecting lines.
        offsets = np.linspace(-0.3, 0.3, len(order))
        for dx, m in zip(offsets, order):
            ax.scatter(np.arange(len(arms)) + dx, piv.loc[m].to_numpy(),
                       color=style.colour(m), marker=style.marker(m), s=22,
                       linewidths=0.3, edgecolors="white", zorder=3)
        for x in np.arange(len(arms) - 1) + 0.5:
            ax.axvline(x, color=style.INK, lw=0.4, alpha=0.25, zorder=0)
        ax.set_xticks(range(len(arms)))
        ax.set_xticklabels([f"arm {a}" for a in arms])
        ax.set_ylabel(ylab)
        ax.set_xlim(-0.5, len(arms) - 0.5)
        style.panel_label(ax, lab)
    axes[0].set_ylim(0, None)
    axes[1].set_ylim(0, None)
    fig.subplots_adjust(wspace=0.3, bottom=0.18)
    leg = style.model_legend(fig, order, ncol=4, y=0.02, lines=False)
    style.save(fig, "fig2_risk_trait", extra_artists=[leg])

if __name__ == "__main__":
    main()
