"""fig5: where the money went -- P&L decomposition."""
from __future__ import annotations
import os, sys
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import style


COMPS = [("exposure_pnl", "exposure", "deepseek"),
         ("timing_execution", "timing + execution", "claude"),
         ("fees", "fees", "kimi"),
         ("funding", "funding", "gemini")]

def stack(ax, labels, mat, net, xlab):
    x = np.arange(len(labels))
    pos = np.zeros(len(labels)); neg = np.zeros(len(labels))
    for (key, lab, fam), vals in zip(COMPS, mat):
        b = np.where(vals >= 0, pos, neg)
        ax.bar(x, vals, 0.62, bottom=b, label=lab,
               color=style.FAMILY_COLOUR[fam], edgecolor="white", linewidth=0.35, alpha=1.0)
        pos = pos + np.where(vals >= 0, vals, 0)
        neg = neg + np.where(vals < 0, vals, 0)
    ax.scatter(x, net, marker="_", s=260, color=style.INK, zorder=5,
               linewidths=2.0, label="net (sum of components)")
    ax.axhline(0, color=style.INK, lw=0.7)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=30, ha="right",
                       rotation_mode="anchor")
    ax.set_ylabel("contribution (% of starting capital)")
    ax.set_xlabel(xlab, labelpad=2)

def main():
    style.apply()
    d = pd.read_csv(os.path.join(style.DER, "a1_pnl_decomposition.csv"))
    s15 = d[d["season"] == "S15"].copy()
    s15["timing_execution"] = s15["timing_pnl"] - s15["slippage"]
    np.testing.assert_allclose(s15["exposure_pnl"] + s15["timing_execution"]
                               - s15["fees"] + s15["funding"], s15["net_pnl"], atol=1e-8)

    fig, axes = plt.subplots(1, 2, figsize=(7.0, 3.4),
                             gridspec_kw={"width_ratios": [1.5, 1]})

    bym = s15.groupby("model")[[c[0] for c in COMPS] + ["net_pnl"]].mean() / 100.0
    bym = bym.sort_values("net_pnl", ascending=False)
    mat = []
    for key, lab, fam in COMPS:
        v = bym[key].to_numpy()
        mat.append(-v if key in ("fees", "slippage") else v)
    stack(axes[0], list(bym.index), mat, bym["net_pnl"].to_numpy(),
          "model (mean over the four arms)")
    style.panel_label(axes[0], "(a)")

    bya = s15.groupby("competition_id")[[c[0] for c in COMPS] + ["net_pnl"]].mean() / 100.0
    mat = []
    for key, lab, fam in COMPS:
        v = bya[key].to_numpy()
        mat.append(-v if key in ("fees", "slippage") else v)
    stack(axes[1], [f"arm {i}" for i in bya.index], mat,
          bya["net_pnl"].to_numpy(), "arm (mean over the eight models)")
    axes[1].set_ylabel("")
    style.panel_label(axes[1], "(b)")

    handles, labels = axes[0].get_legend_handles_labels()
    # bars first, the net marker last
    order = list(range(1, len(handles))) + [0]
    handles = [handles[i] for i in order]
    labels = [labels[i] for i in order]
    fig.subplots_adjust(wspace=0.22, bottom=0.30)
    leg = fig.legend(handles=handles, labels=labels, loc="upper center",
                     bbox_to_anchor=(0.5, 0.03), ncol=3, frameon=False)
    for tx in leg.get_texts():
        tx.set_color(style.INK)
    style.save(fig, "AlphaLuckPnlAttribution", extra_artists=[leg])

if __name__ == "__main__":
    main()
