# AlphaLuckDenominatorSensitivity

A standalone replication Quantlet for *Trading versus Holding in a Live Language-Model Competition* (working paper). It compares descriptive risk summaries on two legitimate capital bases and reweights the observed dates jointly across the entire account panel.

## Run

Use Python 3.11 or later. From this folder:

```sh
python -m pip install -r requirements.txt
python AlphaLuckDenominatorSensitivity.py
```

The script also works when invoked by its absolute path from another directory. It requires no network connection, API key, parent repository, LaTeX installation or raw organiser files. Once dependencies are installed, all calculations run locally. Default execution performs 20,000 draws for each of three block lengths. `--draws 5000` changes this number; `--out DIR` changes the numeric-output folder. Preview files are always written beside the script.

## Included inputs

- `data/paired_daily_inputs.csv`: 448 account-date observations, containing the account tag, UTC date, daily P&L divided by USD 10,000 and daily return on preceding equity. Each of 32 accounts has 14 observations.
- `data/account_measures.csv`: one row per account with model label, arm, final return, and gross-exposure and turnover summaries on both capital bases. All quantities are derived analytical data.
- `data/PROVENANCE.json`: input SHA-256 values, upstream source hashes, sample convention and scope.
- `expected_statistics.json`: numerical regression checks only; no result is computed from this file.

Volatility is recalculated from the daily observations. F, W and correlations for all three measures are recalculated from the paired measures and final outcomes. This compact Quantlet does not reconstruct the original exchange ledger or independently validate prices. No licensed external prices, organiser API responses or credentials are included.

## Economic definitions

Let C = USD 10,000 and E[d] denote date-end equity. Current-equity volatility is the sample standard deviation of `(E[d] - E[d-1]) / E[d-1]`; initial-capital volatility is the standard deviation of `(E[d] - E[d-1]) / C`. They measure variation relative to remaining wealth and to a common starting budget, respectively. Neither denominator is universally preferable.

Gross exposure averages `gross_notional / equity` on the intraday grid, or averages `gross_notional / C`. Turnover is total traded notional divided by 14 and mean date-end equity, or by 14 and C, multiplied by 100. Its equity base averages all 15 date-end marks and differs from the lagged-equity convention used for volatility. Turnover volume covers the full window.

The daily volatility series excludes the initial partial interval between opening and the first UTC date-end mark. The last of the 14 changes ends at 22:00 UTC and is shorter than 24 hours. These conventions match the manuscript; they do not constitute an ideal homogeneous daily sample.

## Statistics and sensitivity

F is the ratio of additive model and residual mean squares in the 8-by-4 layout, reported as a descriptive statistic without a reference distribution. W is Kendall's rank concordance across arms. The return association is the mean of four within-arm Spearman correlations with observed season-final returns. Differences always mean initial capital minus current equity.

The date sensitivity draws overlapping non-circular blocks of one, two or three consecutive dates, concatenates them and truncates at 14. The same date indices select all 32 accounts and both volatility inputs. Final returns and account labels remain fixed. This preserves the observed cross-section and within-block order; it does not preserve dependence beyond the block length. Seeds are fixed and recorded.

The central 95% ranges are **reweighting sensitivity ranges, not confidence intervals or significance tests**. Fourteen dates cannot establish stationarity or reliable coverage. Reweighted observations are not dynamically consistent wealth paths and do not estimate a future joint distribution of risk and returns. One run per model-arm cell does not allow model population claims or separate model-arm interaction from run variation. The sign of a descriptive difference does not identify a causal effect of losses or of risk on performance.

The script also deletes each date, model and arm in turn, pairing both denominators throughout. These are deterministic sensitivities, not new independent observations.

## Outputs and verification

The PNG/PDF preview compares F, W and return correlations and shows the paired volatility-correlation reweighting ranges. All figures use saturated colours with black labels and a white background.

`outputs/denominator_comparison.csv` contains the paired statistics; `outputs/joint_block_summary.csv` contains observed statistics and resampling quantiles; `outputs/paired_leave_one_out.csv` contains deletion sensitivities. `outputs/verification.json` records parameters, package versions, input hashes and checks.

On each execution the script verifies data hashes, balance/completeness, F against an independent residual formula, rank correlation and tie-corrected W against independent calculations, contiguous block indexing, zero paired contrasts for identical inputs, and reproduction of the historical numerical summaries. Expected core results include volatility correlations -0.511905 and -0.363095, and their difference +0.148810. No p-values are calculated.

The metadata and script naming follow the [official QuantLet style guide](https://github.com/QuantLet/Styleguide-and-FAQ). The paper's title in `Published in` identifies the associated working paper; it does not imply journal acceptance.

Code and authored documentation are covered by the included MIT licence. The licence does not purport to grant rights over third-party source records.
