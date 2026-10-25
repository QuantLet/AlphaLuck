"""Build every paper figure, then write the white-background check sheets."""
from __future__ import annotations
import importlib, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

FIGURES = [
    "fig1_equity_curves",
    "fig2_risk_trait",
    "fig3_risk_return",
    "fig4_model_effect",
    "fig5_pnl_decomposition",
    "fig6_design_horizon",
    "fig7_pilot",
]


def main() -> None:
    for name in FIGURES:
        print(name)
        importlib.import_module(name).main()
    print("\nchecking transparency and compositing onto white and dark:")
    importlib.import_module("check_figures").main()


if __name__ == "__main__":
    main()
