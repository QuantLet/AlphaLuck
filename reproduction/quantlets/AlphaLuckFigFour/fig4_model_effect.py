"""fig4: how much of the outcome is the model? ICC and variance shares."""
from __future__ import annotations
import os, sys
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), "src"))
import style


SHORT = {
    "final return % (compounded, as published)": "final return",
    "cumulative return % (arithmetic sum of daily)": "cumulative return",
    "leverage-scaled cumulative % (per 1x of gross)": "leverage-scaled",
    "vol-standardised cumulative (= T x daily Sharpe)": "vol-standardised",
}
SHORT3 = {"final return %": "final return",
          "leverage-scaled cumulative %": "leverage-scaled",
          "daily Sharpe": "Sharpe"}

def main():
    style.apply()
    a = pd.read_csv(os.path.join(style.DER, "c2_anova.csv"))
    a = a[a["arms"] == "1-4"].copy()
    a["short"] = a["outcome"].map(SHORT)
    c3 = pd.read_csv(os.path.join(style.DER, "c3_variance_shares.csv"))

    fig, axes = plt.subplots(1, 2, figsize=(7.0, 3.1))

    ax = axes[0]
    yv = np.arange(len(a))[::-1]
    ax.errorbar(a["icc_armFE"], yv,
                xerr=[a["icc_armFE"] - a["icc_armFE_lo"],
                      a["icc_armFE_hi"] - a["icc_armFE"]],
                fmt="o", color=style.FAMILY_COLOUR["gpt"], ecolor=style.INK,
                elinewidth=1.0, capsize=2.5, markersize=5, zorder=3)
    ax.axvline(0, color=style.INK, lw=0.6, alpha=0.6)
    ax.set_yticks(yv); ax.set_yticklabels(a["short"])
    ax.set_xlabel("arm-adjusted ICC of the model effect (exact 95% interval)")
    ax.set_xlim(-0.25, 1.0)
    style.panel_label(ax, "(a)")

    ax = axes[1]
    outs = ["final return %", "leverage-scaled cumulative %", "daily Sharpe"]
    comp = [("share_model", "model", style.FAMILY_COLOUR["gpt"]),
            ("share_arm", "arm (rules)", style.FAMILY_COLOUR["kimi"]),
            ("share_resid", "residual: interaction + luck", style.FAMILY_COLOUR["grok"])]
    x = np.arange(len(outs))
    bottom = np.zeros(len(outs))
    for key, lab, col in comp:
        vals = np.array([
            c3[(c3["outcome"] == o) & (c3["quantity"] == key)]["estimate"].iloc[0]
            for o in outs])
        ax.bar(x, vals, 0.6, bottom=bottom, label=lab, color=col,
               edgecolor="none", alpha=0.9)
        bottom += vals
    ax.set_xticks(x)
    ax.set_xticklabels([SHORT3[o] for o in outs])
    ax.set_ylabel("share of variance")
    ax.set_ylim(0, 1)
    style.panel_label(ax, "(b)")

    handles, labels = ax.get_legend_handles_labels()
    fig.subplots_adjust(wspace=0.45, bottom=0.2)
    leg = fig.legend(handles=handles, labels=labels, loc="upper center",
                     bbox_to_anchor=(0.5, 0.045), ncol=3, frameon=False)
    for tx in leg.get_texts():
        tx.set_color(style.INK)
    style.save(fig, "fig4_model_effect", extra_artists=[leg])

if __name__ == "__main__":
    main()
