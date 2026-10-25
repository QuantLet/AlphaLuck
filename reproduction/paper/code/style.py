"""Shared publication style for AlphaLuck figures.

Use saturated series colours, redundant model markers, black text and a
white background for legibility in the manuscript. No data series is grey.
The same model family keeps its colour and marker across figures; older
versions additionally use dashed lines. Save vector PDF and 300 dpi PNG.
"""
from __future__ import annotations

import os

import matplotlib as mpl
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIGDIR = os.path.join(ROOT, "paper", "figures")
DER = os.path.join(ROOT, "data", "derived")

INK = "#111111"        # high-contrast text, axes and reference marks
INK_STRONG = "#111111"  # panel labels

# Distinct saturated hues; markers provide an additional identifier.
FAMILY_COLOUR = {
    "gpt": "#0072B2",       # blue
    "claude": "#D55E00",    # vermillion
    "gemini": "#2196B3",    # sky blue
    "grok": "#7A3DB8",      # violet
    "qwen": "#B54482",      # reddish purple
    "deepseek": "#00815A",  # bluish green
    "kimi": "#CC8800",      # orange
    "typhoon": "#795324",   # brown
}
FAMILY_MARKER = {
    "gpt": "o", "claude": "s", "gemini": "^", "grok": "D",
    "qwen": "v", "deepseek": "P", "kimi": "X", "typhoon": "*",
}
# older model versions get a dashed line, newer a solid one
DASHED_VERSIONS = {"gemini-2.5-pro", "gpt-5"}

ARM_NAME = {1: "1 New Baseline", 2: "2 Monk Mode",
            3: "3 Situational Awareness", 4: "4 Max Leverage"}
ARM_MARKER = {1: "o", 2: "s", 3: "^", 4: "D"}
ARM_COLOUR = {1: "#0072B2", 2: "#D55E00", 3: "#00815A", 4: "#7A3DB8"}


def family(model: str) -> str:
    m = model.lower()
    for f in FAMILY_COLOUR:
        if m.startswith(f):
            return f
    return "grok"


def colour(model: str) -> str:
    return FAMILY_COLOUR[family(model)]


def marker(model: str) -> str:
    return FAMILY_MARKER[family(model)]


def linestyle(model: str) -> str:
    return (0, (4, 2)) if model in DASHED_VERSIONS else "-"


def apply() -> None:
    mpl.rcParams.update({
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.facecolor": "white",
        "savefig.edgecolor": "none",
        "savefig.transparent": False,
        "font.family": "sans-serif",
        "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
        "font.size": 9.0,
        "axes.labelsize": 9.0,
        "axes.titlesize": 8.5,
        "axes.titlepad": 6.0,
        "xtick.labelsize": 8.0,
        "ytick.labelsize": 8.0,
        "legend.fontsize": 8.0,
        "axes.edgecolor": INK,
        "axes.labelcolor": INK,
        "axes.titlecolor": INK,
        "text.color": INK,
        "xtick.color": INK,
        "ytick.color": INK,
        "xtick.labelcolor": INK,
        "ytick.labelcolor": INK,
        "axes.linewidth": 0.6,
        "xtick.major.width": 0.6,
        "ytick.major.width": 0.6,
        "xtick.major.size": 2.5,
        "ytick.major.size": 2.5,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": False,
        "grid.color": INK,
        "grid.alpha": 0.18,
        "grid.linewidth": 0.5,
        "legend.frameon": False,
        "lines.linewidth": 1.2,
        "lines.markersize": 3.5,
        "figure.dpi": 110,
        "savefig.dpi": 300,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    })


def panel_label(ax, text: str, dx: float = 0.0, dy: float = 0.0, pad: float = 6.0):
    """Left-aligned title above the axes.

    Uses set_title rather than a free-floating text artist: matplotlib reserves
    layout space for a title, so the label cannot be clipped at the top of the
    figure, which free text at axes-coordinate y > 1 can be.
    """
    ax.set_title(text, loc="left", pad=pad, fontsize=9,
                 fontweight="bold", color=INK_STRONG)


def model_legend(fig, models, ncol=None, y=-0.02, lines=True):
    """Single figure-level legend below the axes, horizontal, frameless."""
    handles = [
        mpl.lines.Line2D([], [], color=colour(m), marker=marker(m),
                         linestyle=linestyle(m) if lines else "none",
                         markersize=4, linewidth=1.3, label=m)
        for m in models
    ]
    if ncol is None:
        ncol = 4 if len(models) > 6 else 3
    leg = fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, y),
                     ncol=ncol, frameon=False, handlelength=2.2,
                     columnspacing=1.4, handletextpad=0.5)
    for t in leg.get_texts():
        t.set_color(INK)
    return leg


def save(fig, name: str, extra_artists=()) -> None:
    """Write the figure as vector PDF and 300 dpi PNG, byte-reproducibly.

    matplotlib stamps a CreationDate into PDF metadata, which would make every
    rebuild differ from the committed file even when the figure is identical.
    Setting it to None omits it, so `make all` leaves a clean git tree.
    """
    os.makedirs(FIGDIR, exist_ok=True)
    for ext in ("pdf", "png"):
        meta = {"CreationDate": None} if ext == "pdf" else None
        fig.savefig(
            os.path.join(FIGDIR, f"{name}.{ext}"),
            bbox_inches="tight",
            transparent=False,
            bbox_extra_artists=tuple(extra_artists) or None,
            pad_inches=0.03,
            metadata=meta,
        )
    plt.close(fig)
    print(f"  wrote paper/figures/{name}.pdf and .png")
