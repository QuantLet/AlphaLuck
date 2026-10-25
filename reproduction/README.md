# AlphaLuck

**Trading versus Holding in a Live Language-Model Competition.**
Daniel Traian Pele, Diana Ioana Micu and Victor Rareș Curescu.

Reproduction package for the Finance Research Letters submission and its
Online Appendix. Every number, table and figure is written by the code here
into `paper/numbers.tex`, `paper/tables/`, `paper/figures/` and the
`paper/frl/*_numbers.tex` and `*_table.tex` files.

Nof1's Alpha Arena gave language models real capital to trade crypto
perpetuals (Season 1) and equity-linked perpetuals (Season 1.5) on Hyperliquid,
and published a leaderboard. This package rebuilds every account from the
chain and asks what that leaderboard measures.

---

## What the letter reports

This is a descriptive audit of a short live competition, not an estimate of
persistent model skill. The October 15 revision addresses denominator meaning,
shared-market dependence, conditional portfolio comparisons, extrapolation and
positioning in the literature.

- **Reconstruction:** 38 accounts in two seasons. Reconciliation checks selected
  organiser snapshots, not every intraday valuation. The main panel has 32
  accounts, eight model labels and four observed arms, with one run per cell.
  In-season operating rules and model configurations are incompletely documented.
- **Two capital bases:** current equity measures risk to remaining wealth;
  initial capital measures dollar variation against the starting budget. The
  main table reports both. F, rank concordance and return correlations describe
  this panel. The main text makes no population-model significance claim.
- **Shared-date sensitivity:** common date blocks reweight all 32 accounts and
  both volatility definitions together. Final observed returns stay fixed.
  The ranges are not confidence intervals, tests or counterfactual wealth paths.
- **Accounting attribution:** the main table and figure combine timing and the
  residual execution adjustment. This sum is invariant to intermediate marks
  only conditional on fixed endpoint valuations. It is not measured trading cost.
  Attribution retains the recorded daily-booked funding convention.
- **Primary portfolio comparison:** both actual and first-day frozen books use
  reconstructed hourly funding with pooled fills as oracle-price proxies. The
  frozen book returns 2.82% versus -26.30% actual and exceeds 26/32 accounts.
  These are mark-to-market results conditional on prices, with no liquidation
  replay. The daily-booked version is an appendix comparison only.
- **Exposure-specific sensitivity:** charging 100 bp on frozen terminal gross
  alone leaves a 25.68 pp advantage. A common adverse per-asset endpoint-price
  bound of 4.25% eliminates the aggregate gap when both books are revalued.
  Neither is an estimated cost or error bound. Historical isolated collateral
  and complete exchange margin rules remain unverified.
- **Short horizon:** numerical Sharpe-horizon extrapolations appear only in the
  appendix as conditional illustrations. Fourteen daily changes cannot validate
  years-long stationarity or a minimum evaluation duration.

The public archive and persistent identifier remain pending. The package is
prepared for author review, not a published or submission-certified release.

---

## Reproducing it

```sh
make setup       # uv venv (Python 3.13.9) + exact pins from requirements.lock
make download    # organiser payloads (not shipped) + public on-chain data
make verify-raw  # SHA-256 of every raw file against PROVENANCE.csv
make all         # raw data -> derived -> tables -> figures -> macros -> audit -> tests
make frl         # letter, highlights and Online Appendix (needs latexmk + pdflatex)
make frl-words   # main-text word count (FRL limit: 2,500)
```

`make all` needs the two `data/raw/nof1_hourly/` archives, which no script
can download (see DATA.md); without them it stops at `frl-organiser`.
`src/pnl_external_marks.py` needs `EODHD_API_KEY`; without it the step
fails, make ignores the failure and the committed `a3_external_marks.*` are
kept. `make test` checks the committed derived data against the macros; it
does not need any organiser file. A full run takes about 12 minutes
(`make all`) plus 4 minutes (`make frl`) on an Apple-silicon laptop.
Regenerated CSV/JSON values agree with the committed ones to within 1e-12
relative (floating-point summation order); every `.tex` output is
byte-identical.

`make all` runs `download → build → recon → analyse → followup → checks →
tables → audit → figures → numbers → frl-review → test`; `make quantlets` runs separately.

- `frl-review` runs the legacy audit plus
  `paper/frl/paired_denominator_sensitivity.py`,
  `src/frozen_book_robustness.py` and
  `paper/frl/render_reviewer_revision.py`. New descriptive tables and macros
  are separate from the 486 core macros. Shared-date results are in
  `paper/frl/review_results/inference/`; exposure-based results are in
  `data/derived/frozen_book_robustness*`.
- `frl-audit` runs `paper/frl/referee_audit.py` (leave-one-arm and
  leave-one-day stability, HAC(1) horizons, price ages, mark intervals; writes
  `referee_audit.json` and `audit_reconciliation.tex`) and
  `paper/frl/benchmark_cost_sensitivity.py` (writes
  `benchmark_cost_sensitivity.json`).
- `test` runs `tests/test_numbers.py`, which regenerates every macro and fails
  if any differs from the committed `paper/numbers.tex`, and
  `tests/test_frl_audit.py`, which checks the audit outputs against the macros
  the appendix quotes. `tests/test_frozen_book_robustness.py` checks the
  paired accounting results, all common terminal-price vertices, closing
  frictions and monotone margin-buffer screens.

All random procedures use fixed seeds. Pooled same-millisecond prices are
selected deterministically by time, trade ID and price; the ordering is a
marking convention, not a recovered execution sequence.

The 12 October audit also corrects zero-position/missing-price propagation,
exact Spearman tail comparisons, Kendall ties and the time-in-market
permutation p-value. The new regression tests cover these errors. The
downstream analytics were regenerated and then independently checked against
a fresh offline build and reconciliation from the archived raw payloads.
All existing columns matched exactly in fills, funding, ledger, round trips,
the exposure panel, equity and the 38-account reconciliation. All 408 raw
payloads with recorded provenance matched their SHA-256 hashes; the derived
40-address wallet array was also reproduced from the verified bundle.
The funding loader additionally retains four provenance fields, without
changing the baseline cash amounts or timing. See
`data/derived/raw_reproduction_validation.json` for counts and source hashes.
This check covers the core archived-data reconstruction; it does not test
current network re-acquisition or the optional pilot and external providers.

---

## What is not reproducible from public sources

| | status |
|---|---|
| **Hyperliquid fills, funding, ledger, candles** | Public on-chain records, **shipped** in `data/raw/hl/`. |
| **Organiser API payloads** | **Not shipped.** Nof1 publishes no licence for alphaarena.ai. `src/download_organiser.py` re-fetches them from public endpoints; `PROVENANCE.csv` records the SHA-256 of each file used. |
| **Season 1 organiser figures** | **Fragile.** nof1.ai no longer serves Season 1; they come from the 2025-11-12 Wayback Machine capture. |
| **Season 1.5 address array** | **Fragile.** The bundle URL embeds a deployment hash. `src/wallets.py` falls back to the committed `wallets.csv`, which records every address with its source URL. |
| **EODHD external marks** | **Not shipped** (licensed). `src/pnl_external_marks.py` needs `EODHD_API_KEY`; the step is optional in `make checks`. |
| **Historical Hyperliquid mark/oracle data** | **Not retrieved for Season 1.5.** Pooled fills remain proxies. The official requester-pays S3 archive is a candidate source; XYZ coverage for the window is not verified. |
| **Model versions, inference settings, in-season prompts** | **Not determinable.** Model effects are differences between the observed implementations under these conditions. |

---

## Layout

| path | what |
|---|---|
| `paper/frl/` | the letter, highlights, Online Appendix, `referee_audit.py`, `benchmark_cost_sensitivity.py` and their outputs |
| `paper/numbers.tex`, `paper/numbers.json` | generated macros, one per quoted number |
| `paper/tables/`, `paper/figures/`, `paper/code/` | generated tables and figures, and their generators |
| `paper/alphaluck_draft.tex` | earlier long working draft; superseded by the letter, kept because the macro tests cover it |
| `quantlets/` | six standalone FRL Quantlets with inputs, scripts, outputs and `Metainfo.txt` |
| `src/` | data retrieval, reconstruction and analysis modules |
| `tests/` | `test_numbers.py`, `test_frl_audit.py` |
| `AUDIT.md`, `DATA.md`, `PROVENANCE.csv`, `wallets.csv` | audit narrative, data dictionary, download provenance, wallet mapping |

## Method constraints

Read-only throughout: public endpoints and public pages only, no accounts, no
wallets, no orders. No wallet address was guessed; each carries the organiser
source URL it came from.

## Licence

Code is MIT (see [`LICENSE`](LICENSE)). The shipped on-chain data are public
blockchain records. Organiser payloads and EODHD data are not redistributed.
Cite via [`CITATION.cff`](CITATION.cff).

## Additional public-data checks

The funding sensitivity uses historical Hyperliquid hourly rates with source
requests and hashes recorded beside the inputs in `data/external/`. Funding
is priced against the oracle under exchange rules; pooled fills are only a
proxy. The very close fit to recorded daily payments does not establish exact
counterfactual funding or exact liquidation feasibility.

Hourly organiser snapshots (`make frl-organiser`, needs
`data/raw/nof1_hourly/`) check the reconstruction at every account-hour,
the freeze and close, the isolated-margin regime and on-chain liquidations,
and repeat the frozen-book comparison for every formation hour. Organiser
liquidation prices belong to the actual positions; they bound the frozen
book only under a stated margin policy. See Online Appendix Section 2 and
`paper/frl/organiser_hourly_revision.md`.

Binance spot bars provide a separate Season 1 price-source sensitivity. They
are not Hyperliquid perpetual marks and do not add independent model runs.
The downloaded dataset is retained for internal analysis under its source
terms; do not include the raw Binance archives in the public Quantlet package.

## Public Quantlets

The six compact Quantlets are public at https://github.com/QuantLet/AlphaLuck
(commit `beea27e3a55cfa82e07af22b653c9f24ee9b9367`, which adds fixed
horizons to `AlphaLuckFormationHour`; that Quantlet was first published at
`556b19382b45e38ac7e8435ce1b76f0dee903088` and the first five were
published at `a0504403f6b2573a9875d91087b0e06359b95db8`). The public repository
contains only the six standalone folders, their minimal derived inputs,
outputs and reproduction documentation. It does not publish this complete
transaction-reconstruction project. Catalogue indexing at quantlet.com is a
separate step. The local `quantlets/` folders match the published versions.
