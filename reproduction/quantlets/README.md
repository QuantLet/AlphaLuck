# Quantlets

Standalone Quantlets for *Trading versus Holding in a Live Language-Model Competition*, published at https://github.com/QuantLet/AlphaLuck. Each folder holds the script, its minimal derived inputs, the rendered output, a `Metainfo.txt` in QuantNet format and a README.

| Quantlet | What it reproduces |
|---|---|
| `AlphaLuckFrozenBenchmark` | 24-hour frozen-book comparison, closing-cost and endpoint-price stresses |
| `AlphaLuckFormationHour` | frozen-book comparison for every formation hour and fixed horizons, two margin policies (Online Appendix Section 2) |
| `AlphaLuckPnlAttribution` | accounting attribution of the gap |
| `AlphaLuckRiskReturn` | exposure and return on current equity and initial capital |
| `AlphaLuckRiskProfiles` | gross exposure and daily P&L volatility by model |
| `AlphaLuckDenominatorSensitivity` | risk summaries on the two capital bases with resampled dates |

Rerun all six with `make quantlets`.
