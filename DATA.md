# Included numerical inputs

This file describes the inputs of the six standalone Quantlets. The full reconstruction package in [`reproduction/`](reproduction), including the raw Hyperliquid records, is documented in [`reproduction/DATA.md`](reproduction/DATA.md).

## Standalone Quantlets

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
