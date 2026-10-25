"""fig6: required season length against the number of replicates."""
from __future__ import annotations
import os, sys
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), "src"))
import style


Z2 = 7.8489
DELTA = 1.0
CASES = [(0.5, 0.50, "gpt"), (0.5, 0.95, "claude"),
         (0.1, 0.50, "deepseek"), (0.9, 0.50, "kimi")]

def t_years(iota, rho, R, delta=DELTA):
    return 2 * Z2 / delta**2 * (iota * (1 - rho) + (1 - iota) / R)

def main():
    style.apply()
    R = np.logspace(0, np.log10(200), 300)
    fig, ax = plt.subplots(figsize=(4.6, 3.2))
    for iota, rho, fam in CASES:
        ax.plot(R, t_years(iota, rho, R), color=style.FAMILY_COLOUR[fam],
                linewidth=1.5,
                label=r"$\iota$=" + f"{iota}, " + r"$\rho^m$=" + f"{rho}")
        ax.axhline(t_years(iota, rho, np.inf), color=style.FAMILY_COLOUR[fam],
                   linewidth=0.7, linestyle=(0, (2, 2)), alpha=0.6)
    ax.axhline(1.0, color=style.INK, linewidth=0.9, linestyle="-", alpha=0.8)
    ax.annotate("one year", xy=(1.15, 1.0), xytext=(1.15, 1.18),
                fontsize=7, color=style.INK)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("replicates per model, R")
    ax.set_ylabel("season length needed (years)")
    ax.set_xlim(1, 200)
    ax.set_xticks([1, 2, 5, 10, 20, 50, 100, 200])
    ax.get_xaxis().set_major_formatter(plt.matplotlib.ticker.ScalarFormatter())
    fig.subplots_adjust(bottom=0.20)
    leg = fig.legend(loc="upper center", bbox_to_anchor=(0.5, 0.10), ncol=2,
                     frameon=False)
    for tx in leg.get_texts():
        tx.set_color(style.INK)
    style.save(fig, "fig6_design_horizon", extra_artists=[leg])

if __name__ == "__main__":
    main()
