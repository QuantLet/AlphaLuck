# Research data and scope

## November 2026 release

`replication_20261102/` contains the data and code used for Prediction Arena
and the Alpha Arena threshold checks. It is also distributed as
`AlphaLuck_replication_supplement_v2.1.2.zip` in release v2.1.2.

Prediction Arena includes derived decision/order linkage records, independently
indexed Polygon transactions and settlements, explorer extracts, and Binance
POL/USDC minute prices used for wallet-paid gas. The primary outcome is the
terminal wealth difference with identical external cash flows. Stablecoins
are valued at parity; native POL investment returns are excluded. Time-weighted
returns are secondary estimates using transaction marks at intermediate dates.

The Envio / moose-code source is Polymarket On-Chain Complete v1, CC BY 4.0:
https://huggingface.co/datasets/moose-code/polymarket-onchain-v1 .
Its pinned revision is `7eeb860dea5b79d5c74f3182b70bd08c85c8f833`.
Records are extracted and transformed; source URLs and identifiers are retained.
See the README files within the replication directory for explorer and price
sources. Full operator decision logs are not redistributed or asserted to be
independently verified. Derived order records support the reported linkage.

Alpha Arena includes derived formation thresholds, public exchange-derived
panels and funding observations. Funding is aligned between the threshold
observation and portfolio formation. Raw organiser snapshots are excluded.
Recomputing from derived inputs does not independently verify those source
observations or establish the absence of margin transfers. Both joint-stress
directions and the prior-only missing-threshold scenarios are sensitivity
calculations, not formal bounds.

Machine-specific paths in a small set of funding metadata files have been
replaced with relative paths. Original response hashes, source URLs and the
numerical inputs are unchanged. Public collectors verify TLS certificates.
No private feedback, credentials or user-account exports are included.

## Earlier standalone Quantlets

The six compact Quantlets retain October input snapshots. Their descriptions
below concern those inputs; the November release supplies the margin
calculations. The reconstruction archive remains in `reproduction/`.



Only derived analytical extracts needed to run the six Quantlets are included. The original source project reconstructs public Alpha Arena competition accounts from Hyperliquid exchange records. This compact publication begins at the derived-data boundary.

| Directory | Included input rows |
|---|---|
| AlphaLuckRiskProfiles | 32 account labels/arms; 32 paired volatility and gross-exposure summaries |
| AlphaLuckRiskReturn | 32 account labels/arms/final returns; 32 initial-capital volatility summaries |
| AlphaLuckPnlAttribution | 32 Season 1.5 account accounting decompositions |
| AlphaLuckDenominatorSensitivity | 32 account-measure rows; 448 account-date rows (32 × 14) |
| AlphaLuckFrozenBenchmark | 32 hourly-funded account endpoints; 224 terminal-position rows (32 × 7) |
| AlphaLuckFormationHour | 10,752 account-hour rows (32 × 336) of frozen, realised and passive-isolated results; 336 hourly endpoint summaries; aggregate reconciliation and liquidation-validation statistics |

The figure Quantlets retain only the columns they use. Shared extracts are duplicated where necessary so each folder can run independently. Provenance JSON in the sensitivity folders records input hashes and the upstream analysis boundary. References to source-project scripts in those records identify provenance; those scripts are not required by, or included in, this compact repository.

The standalone folders contain no raw exchange archive (that is in `reproduction/`), organiser API response (including the hourly organiser snapshots used upstream for liquidation prices), licensed external-price dataset, manuscript or backup. Account tags identify competition model/arm combinations rather than personal account holders. No new live runs are represented by the sensitivity outputs.

The code licence does not purport to license third-party source records. The included files are authored derived numerical research extracts. Their interpretation is subject to the limitations in each Quantlet's README.

Primary source context: [Alpha Arena](https://alphaarena.ai/), [Hyperliquid API documentation](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint/perpetuals).

The v2.1.2 release includes `replication_20261102/robustness_checks/`: arm
deletions, model-block sign-flip reference calculations, cash closing costs,
and cash comparisons across 169 overlapping seven-day windows and 336
formations to the close. These are descriptive sensitivities on one market
path. Run `python replay_checks.py` and `python cash_formation_sensitivity.py`
from that directory; both use only the Python standard library.
