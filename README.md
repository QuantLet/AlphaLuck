# AlphaLuck

Six standalone Quantlets accompanying the working paper **Risk Measurement and Performance Benchmarks in a Live LLM Trading Competition**, by Daniel Traian Pele. The association with a working paper does not imply journal acceptance.

This repository contains the six Quantlets, their minimal derived numerical inputs, generated results and reproduction instructions. It does not contain the manuscript or the full transaction reconstruction project.

| Quantlet | Reproduces |
|---|---|
| [AlphaLuckRiskProfiles](AlphaLuckRiskProfiles) | Initial-capital volatility and gross-exposure profiles across the observed arms |
| [AlphaLuckRiskReturn](AlphaLuckRiskReturn) | Model-level and within-arm risk-return associations, recomputed from account data |
| [AlphaLuckPnlAttribution](AlphaLuckPnlAttribution) | Signed accounting contributions, with timing and execution combined |
| [AlphaLuckDenominatorSensitivity](AlphaLuckDenominatorSensitivity) | Paired capital-base comparisons, shared-date reweighting and deletion sensitivities |
| [AlphaLuckFrozenBenchmark](AlphaLuckFrozenBenchmark) | Aggregation of hourly-funded endpoints and conditional closing-cost and common-price stresses |
| [AlphaLuckFormationHour](AlphaLuckFormationHour) | The frozen-book comparison for every formation hour, under account-wide and passive-isolated margin policies |

## Reproduce

Tested with Python 3.13 and the pinned packages in `requirements.txt`.

```sh
python -m pip install -r requirements.txt
python reproduce_quantlets.py
```

Each directory is also self-contained: install its requirements and run the Python script with the same name as that directory. All six run offline after dependency installation; no credentials, parent checkout or LaTeX installation are required. The denominator calculation uses 20,000 draws for each of three block lengths with recorded fixed seeds.

PNG previews, PDF figures and numerical outputs are included. The two sensitivity Quantlets validate input hashes, numerical identities and reference results on execution. The frozen-book script additionally enumerates all 128 common-price sign vertices for the seven instruments. The P&L plot checks the supplied accounting identity. The formation-hour script recomputes every hourly aggregate from account rows and checks it against the upstream reference.

## What the data support

The main panel has 32 accounts, eight model labels and four observed arms, with 14 daily changes per account. They share a market path. Both current-equity and initial-capital denominators are economically meaningful. Reported associations and rank concordance describe this panel; they do not establish persistent model skill or population-model effects.

The frozen-position comparison aggregates derived endpoints: 2.82% versus -26.30% realised, with a higher frozen value for 26/32 accounts. A common adverse per-asset terminal-price bound of approximately 4.25% erases the aggregate advantage. These are conditional accounting and stress calculations. Revaluing both terminal books at organiser prices within 15 minutes of the close gives 28.98 points instead of 29.12. Across all 336 formation hours the advantage ranges from -17.4 to 33.8 points and is positive in 269. Organiser liquidation prices follow the isolated-margin formula; if each frozen position kept its formation margin without transfers, 26 of 32 first-day frozen books would incur at least one liquidation and the advantage would fall to 20.44 or 10.10 points. Historical oracle validation and an exchange replay of liquidations are not established. Central date-reweighting ranges are sensitivity ranges, not confidence intervals.

These compact Quantlets reproduce calculations **from the included derived inputs**. They do not independently reconstruct the original exchange ledger, the funding stream or the market-price history. See each Quantlet's README and [DATA.md](DATA.md) for the precise boundary.

## Citation, licensing and catalogue

Use [CITATION.cff](CITATION.cff) to cite this software. Code and authored documentation use the [MIT licence](LICENSE); this does not grant rights over third-party raw records. Raw exchange and organiser data are not redistributed here.

Metadata follow the [QuantLet style guide](https://github.com/QuantLet/Styleguide-and-FAQ). GitHub publication and indexing by [quantlet.com](https://quantlet.com/) are separate steps; this README does not assert that catalogue indexing has completed.
