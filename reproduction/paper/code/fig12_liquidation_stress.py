"""fig12: liquidation stress under passive isolated margin, Season 1.5.

Advantage to the close at the 24-hour formation under each scenario of
src/organiser_hourly.py, with the remaining margin returned (A) or
forfeited (B); the dotted lines mark the unstressed values.
"""
from __future__ import annotations
import os, sys
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import style

CASES = [("A", "margin returned", "#00815A", None), ("B", "margin forfeited", "#D55E00", "////")]


def main():
    style.apply()
    s = pd.read_csv(os.path.join(style.DER, "organiser_hourly_liquidation_stress.csv"))
    s = s.iloc[::-1].reset_index(drop=True)
    y = np.arange(len(s))
    fig, ax = plt.subplots(figsize=(7.0, 3.2))
    for j, (c, label, colour, hatch) in enumerate(CASES):
        v = s[f"advantage_pp_{c}"]
        ax.barh(y + (0.19 if c == "A" else -0.19), v, 0.36, color=colour, hatch=hatch,
                edgecolor="white", linewidth=0.6, label=f"{label}")
        base = float(s.loc[s["scenario"] == "none", f"advantage_pp_{c}"].iloc[0])
        ax.axvline(base, color=colour, lw=0.8, linestyle=(0, (1, 2)))
        for yi, val, ahead in zip(y, v, s[f"accounts_ahead_{c}"]):
            ax.annotate(f"{val:.1f} ({ahead}/32)", (val, yi + (0.19 if c == "A" else -0.19)),
                        xytext=(3, 0), textcoords="offset points", va="center", fontsize=6.5)
    ax.set_yticks(y, [x[0].upper() + x[1:] for x in s["scenario"]], fontsize=7.5)
    ax.axvline(0, color=style.INK, lw=0.7)
    ax.set_xlim(0, s[["advantage_pp_A", "advantage_pp_B"]].to_numpy().max() * 1.38)
    ax.set_xlabel("frozen minus realised to the close (pp of initial capital); accounts ahead")
    ax.legend(loc="upper right", fontsize=7.5, frameon=True, edgecolor="white", framealpha=1)
    style.save(fig, "fig12_liquidation_stress")


if __name__ == "__main__":
    main()
