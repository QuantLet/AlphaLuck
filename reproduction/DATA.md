# Data

Everything here is derived from two kinds of source: **public on-chain records
from Hyperliquid**, which are redistributed in full, and **the organiser's own
API payloads**, which are not. See [What is not shipped](#what-is-not-shipped).

Regenerate everything with `make all`. Every downloaded file is listed in
`PROVENANCE.csv` with its URL, request payload, UTC fetch time, row count and
SHA-256.

---

## Wallet-to-model mapping

`wallets.csv` — the 38 arena wallets. **No address was guessed**; each carries
the organiser source it was taken from.

| column | meaning |
|---|---|
| `season` | `S1` (crypto perpetuals, Oct–Nov 2025) or `S15` (tokenised US equities, Nov–Dec 2025) |
| `season_label` | human-readable season name |
| `competition_id` | 1 for S1; 1–4 for the four S1.5 rule sets (arms) |
| `run_id` | the organiser's internal run identifier (S1.5 only) |
| `model` | model identifier as the organiser publishes it |
| `address` | the wallet's Hyperliquid address |
| `reconciliation` | `RECONCILED` for all 38 — see `data/derived/recon.parquet` |
| `source_kind` | how the address was obtained |
| `source_url` | the exact URL it came from |

**Season 1 (6 wallets).** The archived Season-1 front-end bundle contains an
explicit, *labelled* map from model id to wallet address. Source:
`https://web.archive.org/web/20251101120000id_/https://nof1.ai/_next/static/chunks/pages/_app-a5ae0a367d6e6067.js`

| model | address |
|---|---|
| gpt-5 | `0x67293d914eafb26878534571add81f6bd2d9fe06` |
| claude-sonnet-4-5 | `0x59fa085d106541a834017b97060bcbbb0aa82869` |
| gemini-2.5-pro | `0x1b7a7d099a670256207a30dd0ae13d35f278010f` |
| grok-4 | `0x56d652e62998251b56c8398fb11fcfe464c08f84` |
| deepseek-chat-v3.1 | `0xc20ac4dc4188660cbf555448af52694ca62b0734` |
| qwen3-max | `0x7a8fd8bba33e37361ca6b0cb4518a44681bad2f3` |

**Season 1.5 (32 wallets).** The live bundle holds a flat array of 40 addresses
and the front end resolves a run's wallet as `addressArray[run_id]`; the run ids
come from the organiser's own run metadata. Two sources, joined:
`https://www.alphaarena.ai/_next/static/chunks/pages/_app-16433bc4d70bcfd6.js`
and `https://www.alphaarena.ai/api/since-inception-values`.
The full 32-row mapping is in `wallets.csv`; `src/extract_wallets.py`
re-derives the array from the bundle.

**Verification.** The mapping is not taken on trust. All 38 wallets were
rebuilt from the chain and compared with the organiser's published hourly
equity: median absolute gap 0.43%, maximum 2.38%, all 38 reconciled
(`data/derived/recon.parquet`). Independently, the organiser states Season 1.5
was won by its "Mystery Model" with +12.11% and $4,844; the chain gives the same
winner at +11.80% and $4,719.

---

## What is not shipped

Nof1 publishes **no licence and no terms of use** for `alphaarena.ai`, `nof1.ai`
or their API. Their payloads are therefore fetched, not redistributed:

```
data/raw/nof1/            live Season-1.5 API responses
data/raw/nof1_s1/         Season-1 API responses (Wayback capture 2025-11-12)
data/raw/nof1_app_bundle.js    live front-end bundle
data/raw/nof1_s1_bundle.js     archived Season-1 bundle
data/raw/alphaarena_home.html  live home page
data/raw/traderank/            TradeRank.ai open dataset (comparison arena)
data/raw/nof1_hourly/          paged hourly account-totals export and 6 December conversations (zip)
```

`data/raw/nof1_hourly/account_totals_hourly.zip` is a CSV export of
`https://www.alphaarena.ai/api/account-totals?lastHourlyMarker=N`, paged over
the whole history (about 40 requests of at most 500 rows). Its 16,552 account
rows equal those of `data/raw/nof1/account-totals.json`; the 51,132 position
rows with quantity, current price, isolated margin and liquidation price are
new, because the unpaged response carries positions for the last 32 snapshots
only. `conversations_6dec.zip` holds the 100 records the conversations
endpoint still returns, all from 6 December 2025. Both archives were supplied
by a collaborator rather than fetched by `download_organiser.py`; their
SHA-256 values are in `PROVENANCE.csv`. `src/organiser_hourly.py` and
`src/organiser_conversations.py` read them; per-snapshot derived detail in
`data/derived/organiser_hourly/` reproduces organiser values and stays local.

**The two `nof1_hourly` archives cannot be re-fetched by any script here.**
No downloader exists for the paged export, and a new paging of the live
endpoint will not reproduce the same bytes. To rerun `make frl-organiser`
(part of `make all`), obtain the two files from the author, place them
unchanged at `data/raw/nof1_hourly/account_totals_hourly.zip` and
`data/raw/nof1_hourly/conversations_6dec.zip`, and run `make verify-raw`.
Without them, every other target runs, `make test` passes, and the
committed `data/derived/organiser_hourly*` and `paper/frl/organiser_*.tex`
outputs are used as shipped.

`python src/download_organiser.py` (run automatically by `make download`)
fetches every other file listed above from public, unauthenticated
endpoints. It does not check the hashes and does not fail when an endpoint
fails. Run `make verify-raw` afterwards: it compares every file in
`data/raw/` with the SHA-256 recorded in `PROVENANCE.csv`. A live endpoint
that has changed since 8 October 2026 will produce a mismatch. Such a copy
is not the one the published results were computed from.

**Two risks worth stating plainly.**

1. *The Season-1 payloads survive only in the Internet Archive.* nof1.ai no
   longer serves Season 1; `data/raw/nof1_s1/` was recovered from the
   2025-11-12 Wayback capture, the last one taken. If that capture becomes
   unavailable the Season-1 organiser figures cannot be re-fetched from
   anywhere. The Season-1 *on-chain* data is unaffected and is shipped here.
2. *The live bundle URL embeds a deployment hash.* When Nof1 redeploys,
   `_app-16433bc4d70bcfd6.js` will 404 and the address array will have to be
   recovered from the new bundle. The analysis does not depend on this:
   `src/wallets.py` falls back to the committed `wallets.csv`, which carries
   the resolved mapping and its source for every address.

Hyperliquid fills are public blockchain records and are shipped in full.

---

## External replication data — `data/raw/aitrader/`

Position logs and price files of the AI-Trader benchmark (Fan et al., HKU;
`https://github.com/HKUDS/AI-Trader`), **MIT licence** (`LICENSE.txt`, shipped
with the files). The repository head no longer carries `data/`; every file is
taken from commit `c8b24a00b106279ec17f434421b8978e0b5e341d` (11 March 2026)
by `src/download_aitrader.py`, so the URLs are immutable, and logged in
`PROVENANCE.csv`.

| path | contents |
|---|---|
| `data/agent_data*/<model>/position/position.jsonl` | 26 accounts: after every step, the action, every holding and `CASH` |
| `data/merged.jsonl` | Nasdaq-100 hourly prices (`1. buy price` = the step's open, the fill price) |
| `data/A_stock/merged.jsonl`, `merged_hourly.jsonl` | SSE-50 daily and hourly prices |
| `data/crypto/crypto_merged.jsonl` | ten cryptocurrencies, daily |
| `*.py.txt`, `configs/*.json` | AI-Trader's trade, price and metric code and run configurations, kept as reference text (renamed so nothing is importable; never executed) |
| `tree.json` | the pinned commit's file tree, from the GitHub API |

The runs are historical replays, long-only, unlevered and without fees.
`src/aitrader_replication.py` applies the letter's frozen-book comparison to
them.

---

## Shipped raw data — `data/raw/hl/` (378 files)

Responses from `POST https://api.hyperliquid.xyz/info`, one JSON file per
request, exactly as returned.

| directory | request type | files | contents |
|---|---|---|---|
| `userFillsByTime/` | `userFillsByTime` | 144 | every fill, paginated 2000 per page |
| `userFunding/` | `userFunding` | 63 | funding payments, paginated 500 per page |
| `userNonFundingLedgerUpdates/` | `userNonFundingLedgerUpdates` | 38 | transfers in the season window |
| `ledger_all/` | same, `startTime=0` | 38 | full ledger from genesis, to capture the initial $10,000 deposit |
| `clearinghouseState/` | `clearinghouseState` | 38 | account snapshot at audit time |
| `candles4h/`, `candles1d/` | `candleSnapshot` | 28 | 4-hour and daily candles per traded instrument |
| `candles5m/` | `candleSnapshot` | 14 | returns **zero rows** for these windows; kept as evidence |
| `candle_probe/` | `candleSnapshot` | 15 | retention probe: 5m/15m/1h return nothing beyond ~2 weeks / ~6 months |

Fill fields are Hyperliquid's own: `coin`, `px`, `sz`, `side` (`B`/`A`),
`time` (ms), `startPosition`, `dir`, `closedPnl`, `fee`, `oid`, `tid`, `hash`.

---

## Derived data — `data/derived/`

### Panels (parquet)

**`fills.parquet`** — 245,474 rows, every fill of every arena wallet.

| column | meaning |
|---|---|
| `season`, `competition_id`, `model`, `tag`, `address` | wallet identity; `tag` is the stable key, e.g. `S15__c3__grok-4` |
| `time` | fill time, epoch ms UTC |
| `coin` | instrument (`BTC`, `xyz:NVDA`, …) |
| `px`, `sz` | fill price and absolute size |
| `signed_sz` | `+sz` for a buy, `-sz` for a sell |
| `start_position` | position before the fill, as the venue reports it |
| `dir` | venue's label, e.g. `Open Short`, `Close Long` |
| `closed_pnl` | realised P&L booked by this fill |
| `fee` | fee paid, USDC |
| `oid`, `tid` | venue order and trade ids |

**`panel.parquet`** — 1,796,012 rows, position panel on a 5-minute grid.
`t` (grid point, ms), `coin`, `signed_size` (position in units),
`px` (mark), `signed_notional` = `signed_size × px`.
Marks are the last traded print pooled across all 38 wallets and forward-filled,
because Hyperliquid serves no 5m or 1h candles this far back.

**`equity.parquet`** — 260,786 rows, reconstructed equity on the same grid:
`realised` (cumulative `closed_pnl`), `fees`, `funding`, `mtm`
(mark-to-market of open positions), and `equity` =
`10000 + realised − fees + funding + mtm`.

**`funding.parquet`** — 20,366 rows: `time`, `coin`, `usdc` (signed payment),
`funding_rate`.

**`ledger.parquet`** — 455 rows: `type` (`subAccountTransfer`, `send`,
`internalTransfer`, …), `amount`, `signed` (positive into the wallet),
`counterparty`.

**`roundtrips.parquet`** — 19,486 rows, flat→non-flat→flat cycles per
(wallet, coin): `entry_time`, `entry_px`, `exit_time`, `exit_px`, `side`,
`fills` (count), `pnl`, `fee`, `max_abs_sz`, `notional`, `hold_ms`, `closed`.

**`recon.parquet`** — 38 rows, one per wallet: `pub_equity` (organiser's),
`recon_equity` (ours), `tips` (unsolicited public transfers, added before
comparison), `diff`, `diff_pct`, `status`, `pub_source`.

**`a1_pnl_decomposition.parquet`** — 38 rows: `exposure_pnl`, `timing_pnl`,
`slippage`, `fees`, `funding`, `net_pnl`, `equity_change`, `check_gap`.
Identity: `equity_change = exposure + timing − slippage − fees + funding`,
closing to ≤0.23% of a $10,000 book.

### Result tables (44 CSVs)

Named by the section of `AUDIT.md` that uses them:
`t1`–`t6` the original audit, `i1`–`i5` the follow-up items,
`c1`–`c4` the robustness checks, `r1`–`r4` the referee items,
`a1`–`a2` the P&L and cross-season work, `p1` the persistence check.
Each is also rendered as a markdown table in `data/derived/tables*.md` and,
where the paper uses it, as LaTeX in `paper/tables/`.

---

## Season windows

| | start (UTC) | official end (UTC) | on-chain end |
|---|---|---|---|
| Season 1 | 2025-10-17 22:00 | 2025-11-03 23:59 | 2025-11-19 |
| Season 1.5 | 2025-11-19 21:00 | 2025-12-03 22:00 | 2025-12-14 |

The official S1.5 end is quoted verbatim from the organiser's home page
("ended as of December 3rd, 2025 at 5:00 PM EST"). Trading continued past both
ends; analyses use the official windows by default, and
`analyse.common_window(..., official=False)` reproduces them on the full
on-chain windows. The post-season period is analysed in `AUDIT.md` §24.

## External price marks (not redistributed)

`src/pnl_external_marks.py` downloads EODHD five-minute bars to test the
timing/slippage split of §18 against a price source independent of the arena
accounts: the six underlying crypto spot pairs for Season 1 (`BTC-USD.CC` and
the rest) and the underlying US listings for Season 1.5 (`NVDA.US` and the rest,
with `QQQ.US` as a flagged proxy for `xyz:XYZ100`).

EODHD is a paid subscription and its data are licensed, so the bars are fetched
at run time from `EODHD_API_KEY` and are **not** included in the release;
`data/raw/eodhd/` is gitignored. The requests are logged in `PROVENANCE.csv`
with the key replaced by `REDACTED`, so the endpoint and parameters are on the
record even though the credential is not. `make checks` tolerates a missing key
and skips this one step; every other result in `AUDIT.md` reproduces without a
subscription.

## External corroboration (committed, CC BY 4.0)

`data/raw/dxap/league.csv` is the replay-league table published by Barton et
al. (2026) alongside their paper, at
`github.com/ProjectDXAI/continuous-record-llm-trading-agents`. It is released
under CC BY 4.0 and is therefore included here with attribution.
`src/dxap_league.py` reads it to quote one number of theirs correctly — the
smallest Holm-adjusted p-value any frontier model obtained against the leader
in a design with true replicates — and nothing in our own estimates depends on
it. Their fleet-level record of roughly 300,000 on-chain actions is not
released; only the aggregates behind their figures are.

## The replicated pilot (archives kept out of git)

The design section's replication argument is tested in a separate pilot run:
three open-weight models (`gemma-3-27b`, `mistral-24b`, `qwen3-32b`) × two
asset arms × 250 days, with R = 20 replicates per cell at each model's serving
default temperature and R = 10 at temperatures 0.2 and 1.0, giving 60,000
decisions from 61,311 cached model calls, plus three reference agents whose
ι is known in closed form or by Monte Carlo.

That run lives in its own repository at commit
`3301b12c598594b99ecc934b3ec242663654ed31` and reaches this one as two
archives, both **deliberately not committed** (`archives/` is gitignored):

| archive | bytes | SHA-256 | contents |
|---|---:|---|---|
| `alphaluck_pilot_results_20261009.tar.gz` | 8,005,832 | `163992407608e0fbbbdd99f01ac59d4a22d4987924296932cf8261e120fa6e05` | the tracked commit: code, tests, raw market data, derived parquet, results, figures, env locks |
| `alphaluck_pilot_full_20261009.tar.zst` | 21,048,668 | `dc3507a3668f719feee46e0c74cd2c43504c80e08bba2ac76a57adea85d27f68` | the above plus 61,311 cached model calls and logs |

Both were verified with `sha256sum -c` against the sidecars shipped beside
them. `data/derived/pilot/` holds the 22 files this paper needs, extracted from
the results archive: `data/derived/*.parquet`, `results/`, `PILOT.md`,
`PLAN.md`, the pilot's own `PROVENANCE.csv`, `MODEL_HASHES.sha256`,
`GITLOG.txt` and the archive manifest. Every extracted file was re-hashed
against `MANIFEST.sha256` — 22 of 22 match. The raw market JSON, the model
cache, the source tree and the environment locks are **not** extracted; they
are in the archives, which `archives/README_ARCHIVE.md` documents, including
how to replay the whole estimation from cache without calling a model.

Model weights are not included anywhere. They are identified by
`MODEL_HASHES.sha256` and by the revisions recorded in the pilot's `PLAN.md`.

The pilot is replay on historical data, not live trading, and uses mid-size
quantised open-weight checkpoints. Its threats to validity are listed in
`PILOT.md` §6 and the manuscripts state the replay limitation wherever the
pilot is quoted.
