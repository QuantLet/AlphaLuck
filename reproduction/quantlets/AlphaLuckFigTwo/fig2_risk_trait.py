"""fig2: is risk-taking a stable model trait? Leverage and volatility by arm."""
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
    # Both measures are taken against initial capital: against current equity
    # they rise as an account loses, so the panels would show the losses as
    # well as the behaviour. See src/vol_fixed_denominator.py.
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
                    linewidth=1.2, markeredgewidth=0, alpha=0.95)
        ax.set_xticks(range(len(arms)))
        ax.set_xticklabels([f"arm {a}" for a in arms])
        ax.set_ylabel(ylab)
        ax.set_xlim(-0.3, len(arms) - 0.7)
        style.panel_label(ax, lab)
    axes[0].set_ylim(0, None)
    axes[1].set_ylim(0, None)
    fig.subplots_adjust(wspace=0.3, bottom=0.18)
    leg = style.model_legend(fig, order, ncol=4, y=0.02)
    style.save(fig, "fig2_risk_trait", extra_artists=[leg])

if __name__ == "__main__":
    main()
