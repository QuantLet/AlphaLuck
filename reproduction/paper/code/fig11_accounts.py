"""fig11: account-level advantage and its instrument composition, Season 1.5.

(a) Frozen minus realised for each of the 32 accounts, formation at 24 hours,
    under shared collateral and both isolated-margin conventions, in per cent
    of the account's initial capital; accounts sorted by the shared value.
(b) The before-cost gap by instrument (shared collateral), and the gap left
    when that instrument is dropped.
"""
from __future__ import annotations
import json, os, sys
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import style

CONV = [("shared", "shared collateral", "#0072B2", "o"),
        ("iso_A", "isolated, margin returned", "#00815A", "^"),
        ("iso_B", "isolated, margin forfeited", "#D55E00", "s")]


def main():
    style.apply()
    a = pd.read_csv(os.path.join(style.DER, "holding_vs_trading_accounts.csv")).set_index("tag")
    sw = pd.read_csv(os.path.join(style.DER, "organiser_hourly_sweep_accounts.csv"))
    sw = sw[sw["formation_hour"] == 24].set_index("tag").reindex(a.index)
    cap = 100 / 10_000
    d = pd.DataFrame({"shared": a["advantage"] * cap,
                      "iso_A": (sw["isolated_net_A"] - sw["actual_net"]) * cap,
                      "iso_B": (sw["isolated_net_B"] - sw["actual_net"]) * cap,
                      "model": a["model"], "arm": a["arm"]}).sort_values("shared")
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 5.2), gridspec_kw={"width_ratios": [1.5, 1]})
    ax = axes[0]
    y = np.arange(len(d))
    ax.hlines(y, d[["shared", "iso_A", "iso_B"]].min(axis=1), d[["shared", "iso_A", "iso_B"]].max(axis=1),
              color=style.INK, lw=0.4, alpha=0.5)
    for key, label, colour, m in CONV:
        ax.scatter(d[key], y, s=16, color=colour, marker=m, label=label, zorder=3,
                   edgecolor="white", linewidth=0.5)
    ax.axvline(0, color=style.INK, lw=0.7)
    ax.set_yticks(y, [f"{mdl} · {arm}" for mdl, arm in zip(d["model"], d["arm"])], fontsize=6.3)
    ax.set_ylim(-0.8, len(d) - 0.2)
    ax.set_xlabel("frozen minus realised (% of account capital)")
    ax.grid(axis="x")
    style.panel_label(ax, "(a) accounts, formation at 24 hours")
    ax.legend(loc="lower right", fontsize=7, handletextpad=0.3, framealpha=1, frameon=True,
              edgecolor="white")

    ax = axes[1]
    h = json.load(open(os.path.join(style.DER, "holding_vs_trading.json")))
    by = pd.Series(h["deviations"]["by_coin_pp"]).sort_values()
    loo = pd.Series(h["robustness"]["leave_one_instrument_before_costs"]).reindex(by.index)
    names = [c.split(":")[-1] for c in by.index]
    yy = np.arange(len(by))
    ax.barh(yy + 0.19, by, 0.36, color=["#D55E00" if v < 0 else "#0072B2" for v in by],
            label="instrument's contribution")
    ax.barh(yy - 0.19, loo, 0.36, color="#BDD7E7", edgecolor="#2171B5", linewidth=0.6,
            label="gap without it")
    for yi, v in zip(yy, by):
        ax.annotate(f"{v:.1f}".replace("-", "\u2212"), (max(v, 0), yi + 0.19), xytext=(3, 0),
                    textcoords="offset points", ha="left", va="center", fontsize=6.8)
    ax.axvline(0, color=style.INK, lw=0.7)
    ax.axvline(h["deviations"]["total_pp"], color=style.INK, lw=0.5, linestyle=(0, (1, 2)))
    ax.set_yticks(yy, names, fontsize=7.5)
    ax.set_xlabel("pp of initial capital, before costs")
    style.panel_label(ax, "(b) instruments")
    from matplotlib.patches import Patch
    handles = [Patch(color="#0072B2", label="contribution, favours holding"),
               Patch(color="#D55E00", label="contribution, favours trading"),
               Patch(facecolor="#BDD7E7", edgecolor="#2171B5", label="gap without the instrument")]
    leg = ax.legend(handles=handles, loc="upper center", fontsize=7, bbox_to_anchor=(0.5, -0.1))
    fig.subplots_adjust(wspace=0.45)
    style.save(fig, "fig11_accounts", extra_artists=[leg])


if __name__ == "__main__":
    main()
