"""fig7: the replicated pilot.

Panel (a): the share of an instance's variance due to the market path, iota,
for each model and asset arm, with moving-block bootstrap intervals, and the
three reference agents whose iota is known. The point is the spread: iota runs
from about zero to about one across models, so it is a property of the model
and not of "language-model traders".

Panel (b): the proposition tested on subsets of replicates. For random subsets
of size R, the variance of the mean daily difference is compared with
A/T + B/(RT). The ratio is flat in R for every pair, which is the 1/R structure
the design argument rests on; its level is off, which is serial dependence in
daily P&L, and both facts are reported.

Reads data/derived/pilot/, which is extracted from an archive that is not
committed (see DATA.md). Skips cleanly when the pilot is absent.
"""
from __future__ import annotations

import os
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import style

PILOT = os.path.join(style.DER, "pilot", "results")

# One colour per model, reusing the house palette by family so that the pilot
# figure is visually of a piece with the rest. The reference agents are grey.
MODEL_COLOUR = {
    "gemma-3-27b": style.FAMILY_COLOUR["gemini"],
    "mistral-24b": style.FAMILY_COLOUR["deepseek"],
    "qwen3-32b": style.FAMILY_COLOUR["qwen"],
}
MODEL_MARKER = {"gemma-3-27b": "^", "mistral-24b": "P", "qwen3-32b": "v"}
LABEL = {"gemma-3-27b": "Gemma 3", "mistral-24b": "Mistral Small 3",
         "qwen3-32b": "Qwen3", "RANDOM": "random", "MOMENTUM": "momentum",
         "NOISY-MOMENTUM": "noisy momentum"}
REF_COLOUR = style.FAMILY_COLOUR["grok"]
ARM_OFFSET = {"crypto": -0.13, "equity": 0.13}
ARM_FILL = {"crypto": True, "equity": False}


def ci_pair(v) -> tuple[float, float]:
    """iota_ci_b10 is stored as a two-element sequence."""
    lo, hi = list(v)
    return float(lo), float(hi)


def main() -> None:
    if not os.path.isdir(PILOT):
        print("  fig7_pilot: data/derived/pilot absent, skipped")
        return
    style.apply()

    ic = pd.read_parquet(os.path.join(PILOT, "iota_cells.parquet"))
    fc = pd.read_parquet(os.path.join(PILOT, "formula_check.parquet"))
    main_cells = ic[(ic.metric == "pnl") & (ic.cell == "main")]
    llm = main_cells[~main_cells.model.str.isupper()]
    ref = main_cells[main_cells.model.str.isupper()]

    fig, (axa, axb) = plt.subplots(1, 2, figsize=(7.0, 3.1))

    # ---- (a) iota by model and arm
    order = ["qwen3-32b", "mistral-24b", "gemma-3-27b"]
    refs = ["RANDOM", "NOISY-MOMENTUM", "MOMENTUM"]
    ypos = {m: i for i, m in enumerate(order)}
    ypos.update({m: len(order) + 0.6 + i for i, m in enumerate(refs)})

    for _, r in pd.concat([llm, ref]).iterrows():
        y = ypos[r.model] + ARM_OFFSET[r.arm]
        col = MODEL_COLOUR.get(r.model, REF_COLOUR)
        mk = MODEL_MARKER.get(r.model, "o")
        lo, hi = ci_pair(r.iota_ci_b10)
        axa.plot([lo, hi], [y, y], color=col, linewidth=1.1, alpha=0.9,
                 solid_capstyle="butt")
        axa.plot([r.iota], [y], marker=mk, color=col, markersize=4.6,
                 markerfacecolor=col if ARM_FILL[r.arm] else "none",
                 markeredgecolor=col, markeredgewidth=1.1, linestyle="none")

    # the known values of the reference agents, as open vertical ticks
    known = {"RANDOM": 0.0, "NOISY-MOMENTUM": 0.5, "MOMENTUM": 1.0}
    for m, k in known.items():
        axa.plot([k], [ypos[m]], marker="|", color=style.INK, markersize=11,
                 markeredgewidth=1.3, linestyle="none", zorder=5)

    axa.axvline(0.0, color=style.INK, linewidth=0.7, alpha=0.5)
    axa.axvline(1.0, color=style.INK, linewidth=0.7, alpha=0.5)
    axa.set_yticks([ypos[m] for m in order + refs])
    axa.set_yticklabels([LABEL[m] for m in order + refs])
    axa.set_xlabel(r"$\iota$ = market share of instance variance")
    axa.set_xlim(-0.2, 1.12)
    axa.set_ylim(-0.6, max(ypos.values()) + 0.6)
    axa.invert_yaxis()
    style.panel_label(axa, "(a) variance due to the market path")

    # ---- (b) the proposition on subsets of replicates
    # One neutral colour for all six pairs. Six pairs cannot be encoded by the
    # three model colours without implying a pair belongs to one model, and the
    # panel's message is the shape -- flat in R -- not which pair is which.
    # The one pair that sits above the line is named instead.
    fc = fc.assign(ratio=fc.emp_var / fc.pred)
    for (arm, pair), g in fc.groupby(["arm", "pair"]):
        g = g.sort_values("R")
        axb.plot(g["R"], g["ratio"], color=style.INK, linewidth=1.1,
                 linestyle="-" if arm == "crypto" else (0, (3, 2)),
                 marker="o" if arm == "crypto" else "s", markersize=3.0,
                 markerfacecolor=style.INK if arm == "crypto" else "none",
                 alpha=0.85)
    hi = fc[fc.ratio == fc.ratio.max()].iloc[0]
    axb.annotate("Gemma 3 vs Qwen3,\ncrypto", xy=(hi["R"], hi["ratio"]),
                 xytext=(2.6, 1.235), fontsize=7, color=style.INK,
                 ha="left", va="center")
    axb.axhline(1.0, color=style.INK, linewidth=0.9)
    axb.set_xscale("log")
    axb.set_xticks(sorted(fc["R"].unique()))
    axb.get_xaxis().set_major_formatter(plt.matplotlib.ticker.ScalarFormatter())
    axb.set_xlabel("replicates in the subset, R")
    axb.set_ylabel("empirical / predicted variance")
    axb.set_ylim(0.5, 1.3)
    style.panel_label(axb, "(b) the variance formula on subsets")

    # ---- one legend below both panels: models, then the arm encoding
    handles = [
        plt.matplotlib.lines.Line2D([], [], color=MODEL_COLOUR[m],
                                    marker=MODEL_MARKER[m], linestyle="none",
                                    markersize=4.6, label=LABEL[m])
        for m in order
    ] + [
        plt.matplotlib.lines.Line2D([], [], color=style.INK, marker="|",
                                    linestyle="none", markersize=11,
                                    markeredgewidth=1.3,
                                    label="known value"),
        plt.matplotlib.lines.Line2D([], [], color=style.INK, marker="o",
                                    linestyle="-", markersize=3.6,
                                    label="crypto arm"),
        plt.matplotlib.lines.Line2D([], [], color=style.INK, marker="s",
                                    linestyle=(0, (3, 2)), markersize=3.6,
                                    markerfacecolor="none",
                                    label="equity arm"),
    ]
    leg = fig.legend(handles=handles, loc="upper center",
                     bbox_to_anchor=(0.5, -0.01), ncol=3, frameon=False,
                     handlelength=2.2, columnspacing=1.4, handletextpad=0.5)
    for t in leg.get_texts():
        t.set_color(style.INK)

    fig.tight_layout()
    style.save(fig, "fig7_pilot", extra_artists=(leg,))
    plt.close(fig)


if __name__ == "__main__":
    main()
