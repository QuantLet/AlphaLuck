"""fig10: seven-day frozen-book advantage for every formation hour, Season 1.5.

Shared collateral and passive isolated margin (A returns, B forfeits the
remaining margin), and B under the joint liquidation stress with the later
trigger (the more adverse of the two over all formation hours).
"""
from __future__ import annotations
import os, sys
import matplotlib.pyplot as plt
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import style

SERIES = [("cash", "cash", "#111111", (0, (5, 2))),
          ("advantage_pp_168h", "shared collateral", "#0072B2", "-"),
          ("isolated_A_advantage_pp_168h", "isolated, margin returned", "#00815A", (0, (4, 2))),
          ("isolated_B_advantage_pp_168h", "isolated, margin forfeited", "#D55E00", "-"),
          ("stress", "margin forfeited, joint liquidation stress", "#7A3DB8", (0, (1.2, 1.2)))]


def main():
    style.apply()
    s = pd.read_csv(os.path.join(style.DER, "organiser_hourly_sweep.csv"))
    st = pd.read_csv(os.path.join(style.DER, "organiser_hourly_stress_sweep.csv"))
    st = st[st["trigger"] == "later"].set_index("formation_hour")
    s = s.set_index("formation_hour")
    s["stress"] = st["isolated_B_advantage_pp_168h"]
    cash = pd.read_csv(os.path.join(style.DER, "cash_formation_sweep.csv")).set_index("formation_hour")
    s["cash"] = cash["cash_gap_pp_168h_cost0"]
    s = s.dropna(subset=["advantage_pp_168h"])
    d = s.index / 24
    fig, ax = plt.subplots(figsize=(7.0, 3.5))
    for key, label, colour, ls in SERIES:
        ax.plot(d, s[key], color=colour, linestyle=ls, lw=1.3,
                label=label)
    ax.axhline(0, color=style.INK, lw=0.7)
    ax.axvline(1, color=style.INK, lw=0.5, linestyle=(0, (1, 2)))
    ax.annotate("24-hour\nformation", (1, ax.get_ylim()[0]), xytext=(-3, 4),
                textcoords="offset points", fontsize=7.5, va="bottom", ha="right")
    ax.set_xlabel("formation time (days after start)")
    ax.set_ylabel("benchmark minus trading\n(pp of initial capital)")
    ax.grid(axis="y")
    fig.subplots_adjust(bottom=0.32)
    handles, labels = ax.get_legend_handles_labels()
    leg = fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 0.13),
                     ncol=2, frameon=False, fontsize=7.5, handlelength=2.6)
    style.save(fig, "fig10_formation_week", extra_artists=[leg])


if __name__ == "__main__":
    main()
