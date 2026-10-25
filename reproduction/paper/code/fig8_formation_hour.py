"""fig8: the frozen-book comparison for every formation hour, Season 1.5."""
from __future__ import annotations
import os, sys
import matplotlib.pyplot as plt
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import style

SERIES = [("advantage_pp", "marked, hourly funding", "#0072B2", "-"),
          ("isolated_A_advantage_pp", "passive isolated, margin returned", "#00815A", (0, (4, 2))),
          ("isolated_B_advantage_pp", "passive isolated, margin forfeited", "#D55E00", (0, (1.2, 1.2))),
          ("advantage_pp_168h", "marked, seven days after formation", "#7A3DB8", "-")]


def main():
    style.apply()
    s = pd.read_csv(os.path.join(style.DER, "organiser_hourly_sweep.csv"))
    h = s["formation_hour"] / 24
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 3.0))
    ax = axes[0]
    for key, label, colour, ls in SERIES:
        ax.plot(h, s[key], color=colour, linestyle=ls,
                lw=1.0 if key == "advantage_pp_168h" else 1.3, label=label)
    ax.axhline(0, color=style.INK, lw=0.7)
    for mark in (12, 24, 48):
        ax.axvline(mark / 24, color=style.INK, lw=0.5, linestyle=(0, (1, 2)))
    ax.set_xlabel("formation time (days after start)")
    ax.set_ylabel("frozen minus realised (pp of capital)")
    style.panel_label(ax, "(a) aggregate advantage")
    ax = axes[1]
    ax.plot(h, s["accounts_ahead"], color="#0072B2", lw=1.3,
            label="frozen ahead")
    ax.plot(h, s["isolated_accounts_liquidated"], color="#D55E00", lw=1.3,
            linestyle=(0, (4, 2)), label="isolated liquidation")
    ax.legend(loc="upper center", ncol=2, fontsize=7.5, handlelength=2.4)
    ax.set_ylim(0, 39)
    ax.set_yticks(range(0, 33, 8))
    ax.set_xlabel("formation time (days after start)")
    ax.set_ylabel("accounts of 32")
    style.panel_label(ax, "(b) account counts")
    fig.subplots_adjust(wspace=0.3, bottom=0.24)
    handles, labels = axes[0].get_legend_handles_labels()
    leg = fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 0.06),
                     ncol=2, frameon=False)
    style.save(fig, "fig8_formation_hour", extra_artists=[leg])


if __name__ == "__main__":
    main()
