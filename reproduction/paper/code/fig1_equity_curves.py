"""fig1: equity curves of all 38 reconciled arena wallets.

2x2 panels for the four Season-1.5 arms plus a fifth panel for the six
Season-1 wallets. The organiser's official window is shaded; curves continue
past it because on-chain trading did.
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
import wallets as W

def main():
    style.apply()
    eq = pd.read_parquet(os.path.join(style.DER, "equity.parquet"))
    eq["ts"] = pd.to_datetime(eq["t"], unit="ms", utc=True)

    fig = plt.figure(figsize=(7.0, 6.4))
    gs = fig.add_gridspec(3, 2, height_ratios=[1, 1, 0.85], hspace=0.55,
                          wspace=0.24, top=0.94, bottom=0.06)
    axes = [fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1]),
            fig.add_subplot(gs[1, 0]), fig.add_subplot(gs[1, 1])]
    ax5 = fig.add_subplot(gs[2, :])

    s15 = eq[eq["season"] == "S15"]
    models15 = sorted(s15["model"].unique())
    lab = "abcd"
    for j, arm in enumerate([1, 2, 3, 4]):
        ax = axes[j]
        g = s15[s15["competition_id"] == arm]
        for m, gg in g.groupby("model"):
            gg = gg.sort_values("ts")
            ax.plot(gg["ts"], gg["equity"] / 1000.0, color=style.colour(m),
                    linestyle=style.linestyle(m), linewidth=1.0,
                    marker=style.marker(m), markersize=3.0,
                    markevery=max(len(gg) // 7, 1), markeredgewidth=0,
                    solid_capstyle="round")
        ax.axvspan(pd.Timestamp(W.S15_START_MS, unit="ms", tz="UTC"),
                   pd.Timestamp(W.S15_OFFICIAL_END_MS, unit="ms", tz="UTC"),
                   color=style.INK, alpha=0.08, lw=0)
        ax.axhline(10.0, color=style.INK, lw=0.5, alpha=0.5, zorder=0)
        ax.set_ylabel("equity (USD thousands)")
        ax.set_ylim(0, 22)
        style.panel_label(ax, f"({lab[j]}) arm {style.ARM_NAME[arm]}")
        for t in ax.get_xticklabels():
            t.set_rotation(0)
        ax.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter("%d %b"))
        ax.xaxis.set_major_locator(plt.matplotlib.dates.DayLocator(interval=7))

    s1 = eq[eq["season"] == "S1"]
    for m, gg in s1.groupby("model"):
        gg = gg.sort_values("ts")
        ax5.plot(gg["ts"], gg["equity"] / 1000.0, color=style.colour(m),
                 linestyle=style.linestyle(m), linewidth=1.0,
                 marker=style.marker(m), markersize=3.0,
                 markevery=max(len(gg) // 12, 1), markeredgewidth=0)
    ax5.axvspan(pd.Timestamp(W.S1_START_MS, unit="ms", tz="UTC"),
                pd.Timestamp(W.S1_OFFICIAL_END_MS, unit="ms", tz="UTC"),
                color=style.INK, alpha=0.08, lw=0)
    ax5.axhline(10.0, color=style.INK, lw=0.5, alpha=0.5, zorder=0)
    ax5.set_ylabel("equity (USD thousands)")
    ax5.set_xlabel("")
    ax5.set_ylim(0, 22)
    ax5.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter("%d %b"))
    ax5.xaxis.set_major_locator(plt.matplotlib.dates.DayLocator(interval=7))
    style.panel_label(ax5, "(e) Season 1, crypto perpetuals")

    allmodels = models15 + [m for m in sorted(s1["model"].unique())
                            if m not in models15]
    leg = style.model_legend(fig, allmodels, ncol=5, y=0.015)
    style.save(fig, "fig1_equity_curves", extra_artists=[leg])

if __name__ == "__main__":
    main()
