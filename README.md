# AlphaLuck

Data and code for **Trading versus Holding in a Live Language-Model Competition**,
by Daniel Traian Pele, Diana Ioana Micu and Victor Rareș Curescu.
The current research release is [v2.1.1](https://github.com/QuantLet/AlphaLuck/releases/tag/v2.1.1),
dated 2 November 2026. This is a research deposit, not journal acceptance.

## Current replication

[`replication_20261102/`](replication_20261102) contains the saved inputs,
calculations and results for:

- Prediction Arena's trading-versus-holding comparison, with independently
  reconciled transactions, external deposits, network fees and settlement evidence;
- formation at 12, 24 and 48 hours, with the same closing date;
- corrected Alpha Arena funding alignment, all 336 formation hours, both
  joint-stress directions, and the checks using only preceding margin observations.

At first-day formation, holding preserves more terminal wealth for three of
the four attributable Prediction Arena accounts. One starts in cash. GLM's
sign changes at earlier formation, and settlement-only bounds leave Gemini's
sign uncertain. GPT is reported separately because of an unmatched order.
These are descriptive comparisons and do not establish a general advantage
of holding or persistent model skill.

Saved-data replay needs no credentials or new downloads. With Python 3.11+
and the packages in `replication_20261102/requirements.txt` installed:

```sh
cd replication_20261102/alpha_arena
python src/reproduce_threshold_results.py
python -m unittest discover -s tests
cd ../prediction_arena
python calculate_replication.py
python calculate_twr.py
python formation_sensitivity.py
python -m unittest test_replication.py test_formation_sensitivity.py
python independent_inputs/test_history.py
```

Read the [replication instructions](replication_20261102/README.txt) for
valuation assumptions, source attribution and the limits of the reconstruction.
The release includes a standalone ZIP of this folder. The archive supplements
the earlier reconstruction; it does not contain raw organiser snapshots.

## Reconstruction and earlier standalone analyses

[`reproduction/`](reproduction) retains the public Hyperliquid records,
AI-Trader inputs and the numerical tables, figures and Alpha Arena
code. Its README explains the offline checks and which parts of a complete
reconstruction still depend on unavailable organiser archives.

The following six compact Quantlets retain their October inputs and results.
For the margin calculations use `replication_20261102`, not the
older isolated-margin values in `AlphaLuckFormationHour`.

| Quantlet | Reproduces |
|---|---|
| [AlphaLuckRiskProfiles](AlphaLuckRiskProfiles) | Initial-capital volatility and gross-exposure profiles across the observed arms |
| [AlphaLuckRiskReturn](AlphaLuckRiskReturn) | Model-level and within-arm risk-return associations, recomputed from account data |
| [AlphaLuckPnlAttribution](AlphaLuckPnlAttribution) | Signed accounting contributions, with timing and execution combined |
| [AlphaLuckDenominatorSensitivity](AlphaLuckDenominatorSensitivity) | Paired capital-base comparisons, shared-date reweighting and deletion sensitivities |
| [AlphaLuckFrozenBenchmark](AlphaLuckFrozenBenchmark) | Aggregation of hourly-funded endpoints and conditional closing-cost and common-price stresses |
| [AlphaLuckFormationHour](AlphaLuckFormationHour) | The frozen-book comparison for every formation hour, to the close and over fixed 1-, 3- and 7-day horizons, under account-wide and passive-isolated margin policies |


Each compact folder remains independently executable. See [DATA.md](DATA.md)
for the boundaries between archived observations and derived numerical inputs.

## Citation and licences

Cite Pele, Micu and Curescu (2026), *AlphaLuck: Trading versus Holding in a
Live Language-Model Competition*, research data and code, version 2.1.0.
Release: https://github.com/QuantLet/AlphaLuck/releases/tag/v2.1.1.
Machine-readable metadata are in [CITATION.cff](CITATION.cff).

Code and authored documentation use the [MIT licence](LICENSE). The
Envio / moose-code Polymarket archive retains CC BY 4.0 attribution; other
third-party records retain their source notices. This does not relicense
third-party material. Raw organiser snapshots, private feedback and licensed
external-price datasets are not added. GitHub publication does not establish
indexing in the QuantLet catalogue.

The v2.1.1 release includes `replication_20261102/robustness_checks/`: arm
deletions, model-block sign-flip reference calculations, cash closing costs,
and cash comparisons across 169 overlapping seven-day windows and 336
formations to the close. These are descriptive sensitivities on one market
path. Run `python replay_checks.py` and `python cash_formation_sensitivity.py`
from that directory; both use only the Python standard library.
