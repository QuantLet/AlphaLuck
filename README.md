# AlphaLuck

Code and data for **Trading versus Holding in a Live Language-Model Competition**, by Daniel Traian Pele, Diana Ioana Micu and Victor Rareș Curescu. The association with a working paper does not imply journal acceptance.

The repository has two parts:

- [`reproduction/`](reproduction) — the full reconstruction package: the public Hyperliquid fills, funding, ledger and candle records for all 38 accounts, the AI-Trader inputs, the derived data, and the code that rebuilds every number, table and figure. Hyperliquid's API now returns only each wallet's most recent 10,000 fills and recent candles, so nine of the 38 wallets and the 5-minute price history for the season can no longer be re-downloaded in full; the copy here is the one the results were computed from, with SHA-256 hashes in `reproduction/PROVENANCE.csv`. See [`reproduction/README.md`](reproduction/README.md) and [`reproduction/DATA.md`](reproduction/DATA.md).
- Six standalone Quantlets (below) that reproduce selected results from minimal derived inputs.

| Quantlet | Reproduces |
|---|---|
| [AlphaLuckRiskProfiles](AlphaLuckRiskProfiles) | Initial-capital volatility and gross-exposure profiles across the observed arms |
| [AlphaLuckRiskReturn](AlphaLuckRiskReturn) | Model-level and within-arm risk-return associations, recomputed from account data |
| [AlphaLuckPnlAttribution](AlphaLuckPnlAttribution) | Signed accounting contributions, with timing and execution combined |
| [AlphaLuckDenominatorSensitivity](AlphaLuckDenominatorSensitivity) | Paired capital-base comparisons, shared-date reweighting and deletion sensitivities |
| [AlphaLuckFrozenBenchmark](AlphaLuckFrozenBenchmark) | Aggregation of hourly-funded endpoints and conditional closing-cost and common-price stresses |
| [AlphaLuckFormationHour](AlphaLuckFormationHour) | The frozen-book comparison for every formation hour, to the close and over fixed 1-, 3- and 7-day horizons, under account-wide and passive-isolated margin policies |

## Reproduce the standalone Quantlets

Tested with Python 3.13 and the pinned packages in `requirements.txt`.

```sh
python -m pip install -r requirements.txt
python reproduce_quantlets.py
```

Each directory is also self-contained: install its requirements and run the Python script with the same name as that directory. All six run offline after dependency installation; no credentials, parent checkout or LaTeX installation are required. The denominator calculation uses 20,000 draws for each of three block lengths with recorded fixed seeds.

PNG previews, PDF figures and numerical outputs are included. The two sensitivity Quantlets validate input hashes, numerical identities and reference results on execution. The frozen-book script additionally enumerates all 128 common-price sign vertices for the seven instruments. The P&L plot checks the supplied accounting identity. The formation-hour script recomputes every hourly aggregate from account rows and checks it against the upstream reference.

## What the data support

The main panel has 32 accounts, eight model labels and four observed arms, with 14 daily changes per account. They share a market path. Both current-equity and initial-capital denominators are economically meaningful. Reported associations and rank concordance describe this panel; they do not establish persistent model skill or population-model effects.

The frozen-position comparison aggregates derived endpoints: 2.82% versus -26.30% realised, with a higher frozen value for 26/32 accounts. A common adverse per-asset terminal-price bound of approximately 4.25% erases the aggregate advantage. These are conditional accounting and stress calculations. Revaluing both terminal books at organiser prices within 15 minutes of the close gives 28.98 points instead of 29.12. Across all 336 formation hours the advantage ranges from -17.4 to 33.8 points and is positive in 269. Over a fixed seven-day horizon the frozen book is ahead for 151 of 169 formation hours (median 7.4 points); the 24-hour formation, at 22.2 points, lies at the 89th percentile, and its advantage to the close at the 96th percentile of all formation hours. Organiser liquidation prices follow the isolated-margin formula; if each frozen position kept its formation margin without transfers, 26 of 32 first-day frozen books would incur at least one liquidation and the advantage would fall to 20.44 or 10.10 points. Historical oracle validation and an exchange replay of liquidations are not established. Central date-reweighting ranges are sensitivity ranges, not confidence intervals.

These compact Quantlets reproduce calculations **from the included derived inputs**. They do not independently reconstruct the original exchange ledger, the funding stream or the market-price history. See each Quantlet's README and [DATA.md](DATA.md) for the precise boundary.

## Reproduce the full package

Tested with Python 3.13 and the pinned packages in `reproduction/requirements.lock`.

```sh
cd reproduction
python -m venv .venv && .venv/bin/pip install -r requirements.lock
make verify-raw   # SHA-256 of every shipped raw file against PROVENANCE.csv
make test         # identities, reconciliation and every reported macro
make frl-figures  # the letter's figures
```

The organiser's own API payloads (alphaarena.ai, nof1.ai) carry no licence and are not redistributed; `make download` re-fetches those that are still served, and `make verify-raw` reports them as missing until then. Licensed EODHD prices, used in one optional robustness check, are also not included. Steps that need either use the committed derived outputs.

## Citation, licensing and catalogue

Use [CITATION.cff](CITATION.cff) to cite this software. Code and authored documentation use the [MIT licence](LICENSE); this does not grant rights over third-party raw records. Public Hyperliquid records are redistributed in `reproduction/data/raw/hl/`; AI-Trader inputs keep their MIT licence; organiser payloads and licensed external prices are not redistributed.

Metadata follow the [QuantLet style guide](https://github.com/QuantLet/Styleguide-and-FAQ). GitHub publication and indexing by [quantlet.com](https://quantlet.com/) are separate steps; this README does not assert that catalogue indexing has completed.
