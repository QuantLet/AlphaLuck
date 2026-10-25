# alphaluck pilot: PLAN (Phase 0, frozen before any model output)

Status: frozen at commit time. After this commit, design choices do not change. Any deviation goes in
a **Deviations** section below, with the reason. Prompts and parameters are not tuned on results.

The only section filled in after the freeze is §9 (benchmark timing and projected runtime), in a
separate commit. The benchmark calls use a **pre-window date (2025-06-30)**. Their outputs are only
timed and counted as parseable or not. They are not analysed.

## 1. Inventory and model choice

Machine: 2x NVIDIA A30 (24 GB each), driver 535.230.02, CUDA 12.2, 96 CPU cores, 503 GB RAM.
No ollama install. vLLM exists only in conda env `syncrisk-vllm`.

Open-weight LLMs in the HF cache (`~/.cache/huggingface/hub`):

| model | family | notes |
|---|---|---|
| Qwen/Qwen3-32B-AWQ | Qwen (Alibaba) | text, AWQ 4-bit, 19 GB |
| abhishekchohan/gemma-3-27b-it-quantized-W4A16 | Gemma (Google) | VLM, 4-bit compressed-tensors, 16 GB |
| gaunernst/gemma-3-27b-it-int4-awq | Gemma | alternative Gemma 3 quant |
| stelterlab/Mistral-Small-24B-Instruct-2501-AWQ | Mistral | text, AWQ 4-bit, 14 GB |
| google/gemma-4-26b-a4b-it, google/gemma-4-e4b-it | Gemma 4 | bf16 (49 GB doesn't fit) / small |
| Qwen2/2.5/3-VL 2-8B, SmolVLM | VLMs | small, vision-oriented |

Chosen (three families; all already validated under this vLLM build in the SYNCRISK project, used here read-only):

| alias | repo | revision (snapshot) | quantisation | vLLM quantization arg |
|---|---|---|---|---|
| qwen3-32b | Qwen/Qwen3-32B-AWQ (official Qwen quant) | 0499c3ac83fdef8810b907a23894ba91e95eddd8 | AWQ 4-bit, group 128, GEMM | awq_marlin |
| gemma-3-27b | abhishekchohan/gemma-3-27b-it-quantized-W4A16 (community quant) | d15b68f50c67a54bed6624e1b2e8e006776d951f | W4A16 int4 sym, group 128 (compressed-tensors) | compressed-tensors |
| mistral-24b | stelterlab/Mistral-Small-24B-Instruct-2501-AWQ (community quant) | cbda099649a0188dd888d44f0e4964d8d982dc9a | AWQ 4-bit, group 128, GEMM | awq_marlin |

The SHA-256 of every weight file is in `MODEL_HASHES.sha256`.

Serving backend: vLLM 0.8.5.post1 (offline `LLM` engine, default V1 engine), torch 2.6.0+cu124,
transformers 4.51.3. The python is `/home/jovyan/.conda-envs/syncrisk-vllm` (reused read-only, no
packages installed into it). Engine settings: tensor_parallel_size=2, max_model_len=4096,
gpu_memory_utilization=0.90, prefix caching on, CUDA graphs on (changed to eager mode; see Deviation 1). One model is served at a time.
Analysis and data run in a new env, `/home/jovyan/.conda-envs/alphaluck` (python 3.11, pandas 2.2,
numpy, scipy, statsmodels, matplotlib, pyarrow, pytest).

Prompts are rendered with each model's own chat template (`apply_chat_template`,
`add_generation_prompt=True`, `enable_thinking=False`). The tokens go to vLLM with no extra special
tokens. For Qwen3 this produces the empty `<think></think>` (non-thinking) block. Gemma's template
folds the system message into the first user turn. Mistral's template would inject a default system
prompt containing *today's real date*. That is avoided because we always send our own system
message; a test confirms that no rendered prompt contains a 2026-10 date.

## 2. Knowledge cutoffs and evaluation window

| model | documented cutoff | source |
|---|---|---|
| Gemma 3 | August 2024 | Google Gemma 3 model card, ai.google.dev/gemma/docs/core/model_card_3: "The knowledge cutoff date for the training data was August 2024." |
| Mistral Small 3 (2501) | 2023-10-01 | The model's own chat template (tokenizer_config.json in the snapshot), default system prompt: "Your knowledge base was last updated on 2023-10-01." |
| Qwen3 | **not documented** | The Qwen3-32B-AWQ model card and Qwen3 technical report state no cutoff. Third-party trackers disagree (2023-12 to 2025-03) and cite no primary source. **Bound used: public release date 2025-04-29** (Qwen3 release); training data cannot postdate release. |

- Latest cutoff (bound): 2025-04-29, so the window starts at **2025-07-29** (bound plus three months).
- Window end: **2026-10-07**, the last complete trading day (equities) and last complete UTC day
  (crypto) when the data was pulled on 2026-10-08 10:28 UTC.
- Trading days in the window: equity 301, crypto 436 (crypto trades every calendar day). Both
  exceed 120.
- At most 250 days are used. Each arm takes the last 251 trading days of the window: decisions on
  the first 250, with the last decision earning the return of the 251st.
  - EQUITY decision days: 2025-10-08 … 2026-10-06 (250 NYSE days)
  - CRYPTO decision days: 2026-01-30 … 2026-10-06 (250 calendar days; day = UTC daily candle)
- The arms cover different calendar spans. They are never compared day by day; pairs are always
  within one arm.

## 3. Data (Phase 1)

- EQUITY: Yahoo Finance chart API v8, unauthenticated, daily, `events=div|split`,
  `includeAdjustedClose=true`, 2025-01-01 to 2026-10-08. Total-return index = `adjclose`.
  The price level shown to the model is the **as-traded close**: Yahoo's split-adjusted close,
  re-multiplied by every split after that date (NFLX 10:1 in Nov 2025). This keeps levels free of
  later corporate actions.
- Universe: the SYNCRISK 30 US single names (read-only from `syncrisk_pilot/config/tickers.yaml`):
  AAPL MSFT GOOGL AMZN NVDA META TSLA JPM BAC WFC GS MS V MA JNJ UNH PFE LLY XOM CVX KO PEP WMT HD PG
  BA CAT DIS NFLX T.
- CRYPTO: Binance public spot klines, `{BTC,ETH,SOL,BNB,XRP,DOGE}USDT`, 1d, UTC. The close is the
  candle close at 00:00 UTC of the next day.
- Provenance: one row per request in `PROVENANCE.csv` (source, request URL, UTC time, rows,
  SHA-256 of the raw response). Raw responses are kept in `data/raw/` and never overwritten.
- Features per asset for day t (`src/features.py`):
  - last close (as-traded)
  - total returns over 1, 5 and 20 days
  - 20-day realised volatility (std of daily log total returns over the last 20 sessions, daily
    units)
  - 20-day high and low of closes. These are computed on the total-return index and rescaled to
    today's price level, so they only depend on corporate actions inside the window.
- `tests/test_no_lookahead.py` checks two things on synthetic and real data:
  - truncation: features up to t are identical when all data after t is dropped
  - perturbation: features up to t are identical when every value after t is scrambled

  It also includes a check that a deliberately leaky feature is caught.
- Accounting return for a decision at t: close-to-close return from t to t+1 of the total-return
  index (equity) or close (crypto).

## 4. Arena (Phase 2)

- One decision per replicate per day. The input is the day-t feature table plus the replicate's own
  state: current (drifted) weights, equity in USD (starting at 1,000,000), and cumulative return.
  There is no conversation history.
- Output parse (strict, `arena.parse_weights`): exactly one JSON object `{"weights": {...}}`,
  optionally wrapped in a single markdown code fence. It is invalid if any of these hold:
  - it isn't valid JSON
  - it has keys other than `weights`
  - any of the arm's assets is missing, or an unknown asset is present
  - a value is non-numeric or boolean
  - a value is outside [-1, 1]
  - generation stopped for a reason other than `stop` (e.g. length)
- Gross exposure above 2: all weights are scaled proportionally to gross 2.
- Retries on invalid output: up to 2 more attempts, using the same prompt and seed = base_seed +
  retry index. If all 3 attempts fail, the previous (drifted) weights are held and the failure is
  logged.
- Accounting:
  - weights set at close t earn r_{t+1}: x = w·r_{t+1} − 0.0005·turnover_t, where
    turnover_t = Σ|w_t − w_{t−1}^drift|
  - drift: w^drift = w·(1+r)/(1+w·r)
  - no funding, borrow, margin or liquidation modelling (stated simplification)
  - x[k,r,t] is the replicate's net daily return
- Sampling:
  - temperature as per cell
  - top_p and top_k = each model's `generation_config.json` (Qwen3: top_p 0.95, top_k 20; Gemma 3
    and Mistral: none, so top_p 1, top_k −1)
  - max_tokens 768
- **Serving-default temperature** (from `generation_config.json`; vLLM uses these as defaults):
  - Qwen3 0.6
  - Gemma 3 1.0 (unset, so the vLLM default of 1.0 applies)
  - Mistral 0.15
- Seeds:
  - base seed = int(sha256("model|arm|temperature|replicate|YYYY-MM-DD")[:8], 16) mod (2^31−16);
    retry k uses base+k
  - the model name is part of the hash, so random streams are not shared across models
  - seeds are stored with every cached response and in the derived parquet
- Cache:
  - one JSON file per call at
    `cache/{model}/{arm}/T{temperature}/r{replicate}/{date}_{prompt_sha256[:16]}_try{k}.json`, so the
    key is (model, arm, temperature, replicate, date, prompt hash, retry)
  - files are created with mode `x`, so a cached response can never be overwritten
  - each file holds the full rendered prompt, response text, finish reason, token counts, seed,
    sampling params, revision, vLLM version and UTC time
  - a run rebuilds every replicate's state from the cache, so it resumes exactly where it stopped
- Parallelism: within a model, every replicate of every cell advances one day at a time, and all
  uncached calls for that day go out as one vLLM batch. Days are sequential because state carries
  over.

### 4.1 Frozen prompt (identical across models, replicates and temperatures; `src/arena.py`)

System message:

> You are an autonomous portfolio manager responsible for a real trading account. Once per trading day, after the close, you set the target portfolio weights that the account will hold until the next close. Reply with a single JSON object and nothing else.

User message (`{…}` filled per call; `ARM_DESC`/`WHEN` per arm):

```
Date: {YYYY-MM-DD} ({WHEN})
Account: {ARM_DESC}

Account state:
- Equity: {equity:,.2f} USD
- Cumulative return since inception: {cum:+.2f}%
- Current weights (fraction of equity, negative = short): {"BTC": 0.0, ...}

Market data as of today's close. Returns are total returns in percent; vol_20d is the standard deviation of daily log returns over the last 20 sessions in percent; high_20d and low_20d are the highest and lowest close of the last 20 sessions.
asset,close,ret_1d,ret_5d,ret_20d,vol_20d,high_20d,low_20d
{one CSV row per asset; close/high/low 6 significant digits, percentages 2 decimals}

Rules:
- Set a target weight for every one of the {N} assets, between -1 and 1 (negative = short, 0 = no position).
- Gross exposure (sum of absolute weights) must not exceed 2. If it does, all weights are scaled down proportionally.
- The account is rebalanced to your targets at today's close and holds them until the next close. Trading costs are 0.05% of traded notional.
- No other information is available.

Respond with only this JSON object, no explanation:
{"weights": {"BTC": <number>, ..., "DOGE": <number>}}
```

- CRYPTO: ARM_DESC = "Spot crypto account (USDT-quoted). The market trades every day; the daily
  close is 00:00 UTC.", WHEN = "after the daily close".
- EQUITY: ARM_DESC = "US equity account (large-cap stocks). The daily close is the 16:00 New York
  close.", WHEN = "after the close".

The prompt never mentions replay or backtest.

### 4.2 Design cells

| cell | models | arms | temperature | R | replicate ids | days | calls (no retries) |
|---|---|---|---|---|---|---|---|
| main | 3 | 2 | serving default (0.6 / 1.0 / 0.15) | 20 | 0–19 | 250 | 30,000 |
| temperature arm | 3 | 2 | 0.2 and 1.0 | 10 each | 100–109 | 250 | 30,000 |
| RANDOM | — | 2 | — | 20 | 0–19 | 250 | CPU |
| MOMENTUM | — | 2 | — | 20 | 0–19 | 250 | CPU |
| NOISY-MOMENTUM | — | 2 | — | 20 | 0–19 | 250 | CPU |

- Gemma 3's default temperature equals 1.0, so its temperature-arm cell at 1.0 is configured
  identically to its main cell, with different replicate ids and therefore different seeds. It is
  run anyway and reported as an internal replication check.
- Reference agents go through the same `arena.step` accounting (costs, gross cap, drift):
  - **RANDOM**: w_i iid U(−1,1), then the gross cap; numpy seed from sha256("RANDOM|arm|rep").
    Known iota is ≈0; the exact population value is computed by Monte Carlo with 4,000 independent
    replicates on the same path.
  - **MOMENTUM**: w_i = sign(ret_20d_i)/N, deterministic (gross ≤ 1). τ²=0, so iota = 1 exactly.
  - **NOISY-MOMENTUM**: w = sign(ret_20d)/N + s·z, with z iid N(0,1) per asset, day and replicate,
    clipped to [−1,1], then the gross cap.
    - s is calibrated per arm by bisection so that the Monte Carlo population iota (4,000
      replicates, same path, through the full accounting) equals 0.5.
    - The known value is that Monte Carlo iota, reported with its MC error.
    - The R=20 estimation replicates use seeds disjoint from the calibration ones.

## 5. Estimation (Phase 3), per arm × temperature × model (and per reference agent)

- x is the R×T matrix of net daily returns.
- τ² = mean over days of the between-replicate sample variance (ddof=1).
- ω² = sample variance over days of the replicate mean (ddof=1), minus τ²/R. Negative values are
  reported as negative, never truncated.
- ι = ω²/(ω²+τ²). With ω²<0, ι is reported as negative.
- Bootstrap: B = 2,000 draws, percentile 95% intervals.
  - Days: circular moving-block bootstrap of day indices, block length **10** (primary) and 5 and
    20 (sensitivity).
  - Replicates: resampled with replacement within each model, independently per model.
  - For pairs, the same day-index draw is applied to both models of the arm.
- Long-run versions use the Newey–West (Bartlett) long-run variance with lag
  **L = floor(4(T/100)^{2/9}) = 4** for T = 250:
  - ω²_LR = LRV(replicate mean series) − τ²_LR/R
  - τ²_LR = R/(R−1) · mean over replicates of LRV(e[k,r,·]), where e[k,r,t] = x[k,r,t] − mean_r x[k,r,t]
  - ι_LR = ω²_LR/(ω²_LR+τ²_LR)
- Per pair (k,l) within arm and temperature cell (the main cell, at each model's default
  temperature):
  - ρ_m = cov_t(x̄_k, x̄_l)/(ω_k ω_l), using bias-corrected ω (the cross-covariance needs no
    correction under the model)
  - A = ω_k²+ω_l²−2ρ_m ω_k ω_l, B = τ_k²+τ_l², and B/A
- Independence check: the correlation over (r,t) between e[k,r,t] and e[l,r,t], with replicates
  matched by index r (seeds are independent by construction). Matching is the only non-trivial
  pairing, because the deviations sum to zero over r. Reported with:
  - a 95% block-bootstrap interval
  - a permutation null (500 random re-pairings of replicate indices)
  - also the correlation of e[k,·,t] cross-products averaged over days (the empirical cross term
    that would enter B)

  "Clearly non-zero" means the 95% interval excludes 0 **and** |corr| > 0.05.
- Boundary check: triggered if any ρ̂_m > 1 (or < −1) or any ω̂² < 0. Run a parametric Gaussian
  bootstrap under the model at the estimated parameters (ω² floored at 0, ρ clipped to [−1,1]), with
  the same T and R and 2,000 simulations, and report how often the boundary event occurs by chance.
- Formula check, per pair:
  - for R ∈ {1,2,5,10,20}, draw 200 random replicate subsets (without replacement) per model
  - for each subset, compute the variance of the mean daily difference over 200 block-bootstrap
    (block 10) day resamples, then average over subsets
  - plot against A/T + B/(RT) (plug-in) and against the long-run analogue
- Implied design numbers, with intervals from the same bootstrap draws:
  - Horizon: T_years(R) = z²(A + B/R)/(δ² σ̄²), with σ̄² = ((ω_k²+τ_k²)+(ω_l²+τ_l²))/2 and
    z² = 7.85. This equals the equal-variance form 2z²/δ²[ι(1−ρ)+(1−ι)/R] when variances are
    equal.
  - Grid: δ ∈ {0.5,1,2} annualised Sharpe and R ∈ {1,5,20,100,∞}. Years don't depend on the
    periods per year, because Sharpe and T scale together.
  - R needed to be within 10% of the floor: R ≥ 10·B/A.
  - Cost-optimal R* = sqrt((B/A)(c_d/c_r)) for c_d/c_r ∈ {10,100,1000}.
- Descriptives per model, arm and temperature:
  - mean daily return, volatility, annualised Sharpe (√252 equity, √365 crypto)
  - mean turnover
  - share of flat days (gross exposure < 1e-6)
  - parse-failure rate, defined as the share of replicate-days still invalid after 2 retries (the
    first-try invalid rate is also reported)

  No ranking claims.
- Reference-agent validation: the known value must lie inside the 95% block-10 interval for
  RANDOM, MOMENTUM (degenerate interval at 1) and NOISY-MOMENTUM, in both arms. If not, the
  estimator is fixed before LLM results are looked at.

## 6. Decision-level score (Phase 4, exploratory)

- Score: s[k,r,t] = Σ_i w_{i,t}(r_{i,t+1} − mean_j r_{j,t+1}), using the post-cap target weights.
- The same decomposition gives A_score and B_score.
- Unit-effect scaling: each metric is divided by its own pair-average per-instance standard
  deviation σ̄. The effect size δ is then a standardized gap in that metric's own units. The floor
  ratio reported is (A_score/σ̄²_score)/(A_pnl/σ̄²_pnl) = [ι(1−ρ)]_score/[ι(1−ρ)]_pnl.
  - This assumes equal standardized effects in both metrics. That is a stated assumption, not a
    result.
  - A ratio below 1 means scoring decisions would shorten the required season.
  - It is reported separately for CRYPTO (6 assets) and EQUITY (30 assets), with bootstrap
    intervals.

## 7. Larger-study sizing

- To pin ι to ±0.05 (95% half-width):
  1. Run a parametric simulation at each model's pilot estimates over a grid of T ∈ {250, 500,
     1000, 2000, 4000} and R ∈ {5, 10, 20, 50, 100}.
  2. Inflate the half-widths by the ratio (pilot block-bootstrap SE)/(parametric SE at the pilot
     T,R) to account for serial dependence and tails.
  3. Report the smallest (T,R) that meets the target.
- Number of models needed to estimate the mean ι across LLM traders to ±0.05:
  n = (1.96·sd_between/0.05)², where sd_between is the between-model SD of pilot ι (with its
  uncertainty).

## 8. Stop conditions (checked in this order)

1. Fewer than 120 post-cutoff days. Not triggered (301 / 436).
2. Reference agents' known ι not recovered within their intervals. Checked before any LLM
   estimate is computed.
3. Parse-failure rate after retries above 5% for any model (any cell).
4. A model flat on more than 80% of days (share of replicate-days with zero gross exposure in the
   main cell).

If any condition is triggered, the run stops and reports instead of continuing.

## 9. Benchmark and projected runtime

Benchmark (2026-10-08, 10:43–10:50 UTC):
- 20 calls per model: 10 CRYPTO + 10 EQUITY at the serving-default temperature on the pre-window
  date 2025-06-30, with a fresh account state.
- Engine as in §1 with the Deviation 1 settings.
- Outputs are kept in `cache_bench/` and not analysed. Only timing and the parse count are used.

| model | load s | single EQUITY call s | batch of 20 s | s/call in batch | prompt tok (crypto/equity) | output tok (crypto/equity) | valid of 20 |
|---|---|---|---|---|---|---|---|
| qwen3-32b | 24.7 | 11.7 | 13.7 | 0.68 | 737 / 2136 | 57 / 281 | 20 |
| gemma-3-27b | 46.1 | 22.8 | 17.9 | 0.89 | 741 / 2126 | 64 / 293 | 20 |
| mistral-24b | 20.9 | 6.1 | 6.1 | 0.30 | 729 / 2143 | 61 / 304 | 20 |

Projected runtime: 20,000 calls per model (250 day-steps × 80 calls), excluding retries. The
estimate uses the batch-20 per-call time with no further batching gain, so it is conservative.
- qwen3-32b: 0.68 × 20,000 ≈ 13,700 s ≈ **3.8 h**
- gemma-3-27b: 0.89 × 20,000 ≈ 17,900 s ≈ **5.0 h**
- mistral-24b: 0.30 × 20,000 ≈ 6,100 s ≈ **1.7 h**
- **Total ≈ 10.5 h** of GPU time, run sequentially (one model on both GPUs at a time).

Reference agents and estimation run on CPU (minutes).

## Deviations

1. **Engine memory settings (before any evaluation output; serving only, no effect on prompts,
   sampling or data).**
   - §1 specified gpu_memory_utilization=0.90 with CUDA graphs on. The first benchmark attempt ran
     out of memory during CUDA-graph capture, at both 0.90 and 0.85.
   - Switched to `enforce_eager=True`, gpu_memory_utilization=0.90. This is the configuration the
     SYNCRISK project ran successfully with these same three checkpoints on this machine.
   - Effect: speed only. The benchmark in §9 uses these settings.

2. **Bootstrap estimator corrected for duplicated replicates (made before any LLM estimate was
   computed, prompted by the reference-agent validation).**
   - With the plain estimator applied to with-replacement replicate draws, the RANDOM/EQUITY 95%
     interval was [0.013, 0.092] around a point estimate of −0.003, and missed the known ι≈0.
   - Cause: with multiplicities n_r, the between-replicate variance has expectation
     τ²·R/(R−1)·(1−c) and the variance of the replicate mean picks up c·τ², where c = Σn_r²/R². That
     biases ω²* upward by about τ²/R.
   - Fix: each bootstrap draw now uses the estimator that is unbiased for its own multiplicities,
     τ̂² = s̄²(R−1)/(R(1−c)) and ω̂² = var_t(x̄) − c·τ̂². The Newey–West version is analogous. It
     reduces to the PLAN estimator when c = 1/R.
   - Point estimates are unchanged. Replicates are still resampled with replacement, as planned.
   - `tests/test_estimate.py::test_bootstrap_dup_correction_unbiased` covers it.
   - After the fix, all six reference cells recover their known values (`results/ref_validation.json`).


3. **Batch scheduling (serving only; at 2026-10-08 10:55 UTC, after day 8 of Mistral had run).**
   - §4 said all cells advance one day at a time. In practice, each retry round then blocked every
     replicate.
   - The driver now lets each replicate advance independently. Every vLLM batch carries, for each
     unfinished replicate, exactly the call it is waiting on: its next day, or a retry of its
     current day.
   - Prompts, seeds, cache keys, retry rule and state transitions are unchanged. A replay-only run
     reproduced the first 7 cached days with zero new calls.
   - Only batch composition changes, and batch composition already affected floating-point
     numerics.
   - Cache writes also became atomic (temp file + hard link; the link still refuses to overwrite).
   - Runtime: the §9 projection was too low. The benchmark's 20 prompts were identical, so prefix
     caching hid most of the prefill cost, while in the arena prompts differ per replicate from the
     account-state line onward. Observed: about 42 s per 80-call round for Mistral. The realistic
     total is about 18–20 h, not 10.5 h. This doesn't change the design.
