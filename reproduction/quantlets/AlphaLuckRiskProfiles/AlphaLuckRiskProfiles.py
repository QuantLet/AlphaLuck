"""Descriptive risk profiles across the observed competition arms."""
from __future__ import annotations
import os, sys
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import style


def main():
    style.apply()
    w = pd.read_csv(os.path.join(style.DER, "c4_wallet_risk.csv"))
    # Initial capital measures dollar exposure against the starting budget.
    # Current equity instead measures exposure relative to remaining wealth.
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
        for m in order:
            ax.plot(range(len(arms)), piv.loc[m].to_numpy(),
                    color=style.colour(m), marker=style.marker(m),
                    linestyle=style.linestyle(m), markersize=5,
                    linewidth=1.6, markeredgewidth=0.3, markeredgecolor="white", alpha=1.0)
        ax.set_xticks(range(len(arms)))
        ax.set_xticklabels([f"arm {a}" for a in arms])
        ax.set_ylabel(ylab)
        ax.set_xlim(-0.3, len(arms) - 0.7)
        style.panel_label(ax, lab)
    axes[0].set_ylim(0, None)
    axes[1].set_ylim(0, None)
    fig.subplots_adjust(wspace=0.3, bottom=0.18)
    leg = style.model_legend(fig, order, ncol=4, y=0.02)
    style.save(fig, "AlphaLuckRiskProfiles", extra_artists=[leg])

if __name__ == "__main__":
    main()
