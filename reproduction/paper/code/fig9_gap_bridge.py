"""fig9: where the frozen-book advantage comes from, Season 1.5, formation at 24 hours.

(a) The advantage under each margin convention as stacked accounting terms:
    fees avoided, funding difference and the before-cost difference are common
    to all three; isolated margin subtracts the cost of liquidations.
(b) The before-cost difference split into deviations from the frozen book,
    on the five-minute grid and on coarser grids.
"""
from __future__ import annotations
import json, os, sys
import matplotlib.pyplot as plt
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import style

TERMS = [("fees", "fees avoided", "#0072B2"),
         ("funding", "funding difference", "#7A3DB8"),
         ("before", "before costs", "#00815A"),
         ("liq", "liquidations", "#D55E00")]
PARTS = [("new", "new\ninstr."), ("add", "add-\nitions"), ("reverse", "rever-\nsals"),
         ("reduce", "reduc-\ntions"), ("execution", "within-\ngrid")]
GRIDS = [("5min", "5 minutes", "#062A5E"), ("15min", "15 minutes", "#1E63A8"),
         ("1h", "1 hour", "#4F99D3"), ("4h", "4 hours", "#9CC8E8")]


def main():
    style.apply()
    h = json.load(open(os.path.join(style.DER, "holding_vs_trading.json")))
    o = json.load(open(os.path.join(style.DER, "organiser_hourly.json")))
    b = h["benchmark"]
    p24 = next(x for x in o["sweep_primary"] if x["formation_hour"] == 24)
    shared = b["advantage_pp"]
    rows = [("shared\ncollateral", shared),
            ("isolated,\nreturned", p24["isolated_A_advantage_pp"]),
            ("isolated,\nforfeited", p24["isolated_B_advantage_pp"])]
    common = {"fees": b["fees_after_pp"], "funding": b["funding_diff_pp"],
              "before": b["advantage_before_costs_pp"]}

    fig, axes = plt.subplots(1, 2, figsize=(7.0, 3.0), gridspec_kw={"width_ratios": [1, 1.25]})
    ax = axes[0]
    x = np.arange(len(rows))
    for i, (_, net) in enumerate(rows):
        bottom = 0.0
        for key, label, colour in TERMS[:3]:
            ax.bar(i, common[key], 0.6, bottom=bottom, color=colour,
                   edgecolor="white", linewidth=1.0, label=label if i == 0 else None)
            bottom += common[key]
        liq = net - shared
        if liq < 0:
            ax.bar(i, liq, 0.6, bottom=0, color=TERMS[3][2], edgecolor="white",
                   linewidth=1.0, hatch="////", label=TERMS[3][1] if i == 1 else None)
        ax.plot([i - 0.38, i + 0.38], [net, net], color=style.INK, lw=1.6)
        ax.annotate(f"{net:.1f}", (i, net), xytext=(0, 3), textcoords="offset points",
                    va="bottom", ha="center", fontsize=7.5, fontweight="bold",
                    bbox=dict(boxstyle="square,pad=0.1", fc="white", ec="none"))
    ax.axhline(0, color=style.INK, lw=0.7)
    ax.set_xticks(x, [r[0] for r in rows], fontsize=7.5)
    ax.set_xlim(-0.5, len(rows) - 0.5)
    ax.set_ylim(-21, 34)
    ax.set_ylabel("pp of initial capital")
    style.panel_label(ax, "(a) advantage by margin convention")
    leg_a = ax.legend(loc="upper center", fontsize=7, handlelength=1.2, ncol=2,
                      bbox_to_anchor=(0.5, -0.2), columnspacing=0.8)

    ax = axes[1]
    grids = {"5min": h["deviations"], **h["robustness"]["deviation_grids_pp"]}
    width = 0.2
    for j, (g, label, colour) in enumerate(GRIDS):
        vals = [grids[g][f"{k}_pp"] if g == "5min" else grids[g][k] for k, _ in PARTS]
        ax.bar(np.arange(len(PARTS)) + (j - 1.5) * width, vals, width * 0.92,
               color=colour, edgecolor="#062A5E", linewidth=0.5, label=label)
    ax.axhline(0, color=style.INK, lw=0.7)
    ax.set_xticks(np.arange(len(PARTS)), [p[1] for p in PARTS], fontsize=7.5)
    ax.set_ylabel("pp of initial capital")
    style.panel_label(ax, f"(b) before-cost gap ({b['advantage_before_costs_pp']:.1f} pp) by grid")
    leg_b = ax.legend(loc="upper center", fontsize=7, ncol=4, handlelength=1.2,
                      bbox_to_anchor=(0.5, -0.2), columnspacing=0.8)
    fig.subplots_adjust(wspace=0.32)
    style.save(fig, "fig9_gap_bridge", extra_artists=[leg_a, leg_b])


if __name__ == "__main__":
    main()
