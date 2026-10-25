# Quantlets

One folder per figure, each self-contained: the plotting script, the shared `style.py`, the rendered figure in PDF and PNG, and a `Metainfo.txt` in QuantNet format.

Regenerate with `python paper/code/make_quantlets.py`. The data dependencies in each `Metainfo.txt` are discovered by scanning the script, not maintained by hand.

| Quantlet | Figure |
|---|---|
| `AlphaLuckFigOne` | `fig1_equity_curves` |
| `AlphaLuckFigTwo` | `fig2_risk_trait` |
| `AlphaLuckFigThree` | `fig3_risk_return` |
| `AlphaLuckFigFour` | `fig4_model_effect` |
| `AlphaLuckFigFive` | `fig5_pnl_decomposition` |
| `AlphaLuckFigSix` | `fig6_design_horizon` |
| `AlphaLuckFigSeven` | `fig7_pilot` |

Published standalone Quantlets (https://github.com/QuantLet/AlphaLuck, commit `beea27e`): `AlphaLuckRiskProfiles`, `AlphaLuckRiskReturn`, `AlphaLuckPnlAttribution`, `AlphaLuckDenominatorSensitivity`, `AlphaLuckFrozenBenchmark` and `AlphaLuckFormationHour` (frozen-book comparison for every formation hour, to the close and over fixed horizons, under two margin policies; Online Appendix Section 2).
