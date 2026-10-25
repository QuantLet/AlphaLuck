# alphaluck pilot: variance components of LLM traders

Design and every choice are in [PLAN.md](PLAN.md), frozen at commit `58c6549` before any model output.
There are three deviations, all made before any LLM estimate was computed (§6 below).

Full machine-generated tables, including the temperature-arm pairs and every interval, are in
[results/tables.md](results/tables.md). Raw numbers are in `results/*.parquet|json`.

Scale:
- 3 open-weight models × 2 arms × 250 days.
- Main cell: R = 20 replicates at each model's serving-default temperature.
- Temperature arm: R = 10 at 0.2 and at 1.0.
- 60,000 decisions from 61,311 cached model calls (including retries), plus three reference agents.

## 1. Verdict

1. **ι is model-specific, not a property of "LLM traders".** At the serving-default temperature:
   - Gemma 3: 0.99 crypto / 0.78 equity
   - Mistral Small 3: 0.78 / 0.84
   - Qwen3: −0.02 [−0.09, 0.20] / 0.11 [0.05, 0.17]

   The range runs from ≈0 to ≈1.
2. **Replication helps, but only modestly.** B/A is 0.3–0.8, so going from R = 1 to R = 20 cuts the
   required season by 22–43%. Three to eight replicates already get within 10% of the R = ∞ floor.
3. **Season length for a Sharpe gap δ = 1** (5% two-sided, 80% power), across the six model pairs:
   - R = 1: **3.6–15.3 years**
   - R = 20: **2.1–12.0 years**

   No feasible number of replicates makes a one-year season decisive between these models.
4. **The shape of A/T + B/(RT) holds.** Empirical/predicted variance is flat in R. The plug-in
   level is off by −34% to +15%. The Newey–West version is within 6% for four of six pairs.
5. **All stop conditions are clear** and the reference agents recover their known ι. Scoring
   decisions instead of P&L (exploratory) shortens the floor for 3 of 6 pairs, lengthens it for 1,
   and is inconclusive for 2.

## 2. ι by model × arm × temperature (metric: daily net P&L)

ι = ω²/(ω²+τ²). Intervals are 95% from the moving-block bootstrap of days (block length b = 10;
b = 5 and 20 alongside) with replicates resampled within model, B = 2,000. ι_LR uses Newey–West
long-run variances, lag 4. Negative values are reported as estimated, not truncated.

| arm | model | temperature | R | ι | 95% CI b=10 | CI b=5 | CI b=20 | ι_LR [CI] | known ι |
|---|---|---|---|---|---|---|---|---|---|
| crypto | gemma-3-27b | **1.0 (default)** | 20 | **0.987** | [0.973, 0.996] | [0.975, 0.995] | [0.972, 0.997] | 0.990 [0.976, 0.997] | |
| crypto | gemma-3-27b | 0.2 | 10 | 0.991 | [0.983, 0.997] | [0.983, 0.996] | [0.982, 0.998] | 0.994 [0.988, 0.998] | |
| crypto | gemma-3-27b | 1.0 (replication cell) | 10 | 0.982 | [0.959, 0.997] | [0.959, 0.997] | [0.958, 0.998] | 0.988 [0.967, 0.998] | |
| crypto | mistral-24b | **0.15 (default)** | 20 | **0.783** | [0.608, 0.921] | [0.639, 0.905] | [0.569, 0.940] | 0.807 [0.610, 0.934] | |
| crypto | mistral-24b | 0.2 | 10 | 0.769 | [0.576, 0.911] | [0.592, 0.899] | [0.553, 0.932] | 0.757 [0.516, 0.922] | |
| crypto | mistral-24b | 1.0 | 10 | 0.419 | [0.250, 0.561] | [0.257, 0.557] | [0.241, 0.571] | 0.427 [0.192, 0.622] | |
| crypto | qwen3-32b | **0.6 (default)** | 20 | **−0.022** | [−0.091, 0.197] | [−0.093, 0.197] | [−0.090, 0.211] | −0.020 [−0.096, 0.243] | |
| crypto | qwen3-32b | 0.2 | 10 | 0.579 | [0.124, 1.000] | [0.143, 1.000] | [0.125, 1.000] | 0.480 [0.055, 1.000] | |
| crypto | qwen3-32b | 1.0 | 10 | 0.370 | [0.123, 0.669] | [0.145, 0.645] | [0.105, 0.690] | 0.524 [0.181, 0.741] | |
| equity | gemma-3-27b | **1.0 (default)** | 20 | **0.776** | [0.678, 0.878] | [0.678, 0.882] | [0.672, 0.891] | 0.772 [0.659, 0.885] | |
| equity | gemma-3-27b | 0.2 | 10 | 0.953 | [0.929, 0.970] | [0.932, 0.969] | [0.928, 0.970] | 0.951 [0.924, 0.969] | |
| equity | gemma-3-27b | 1.0 (replication cell) | 10 | 0.795 | [0.683, 0.928] | [0.688, 0.931] | [0.663, 0.930] | 0.781 [0.661, 0.917] | |
| equity | mistral-24b | **0.15 (default)** | 20 | **0.841** | [0.779, 0.892] | [0.783, 0.885] | [0.772, 0.895] | 0.823 [0.744, 0.892] | |
| equity | mistral-24b | 0.2 | 10 | 0.826 | [0.761, 0.885] | [0.765, 0.882] | [0.758, 0.888] | 0.787 [0.686, 0.872] | |
| equity | mistral-24b | 1.0 | 10 | 0.184 | [0.089, 0.274] | [0.094, 0.280] | [0.097, 0.276] | 0.203 [0.056, 0.344] | |
| equity | qwen3-32b | **0.6 (default)** | 20 | **0.109** | [0.052, 0.167] | [0.054, 0.167] | [0.055, 0.163] | 0.110 [0.030, 0.190] | |
| equity | qwen3-32b | 0.2 | 10 | 0.062 | [−0.037, 0.171] | [−0.029, 0.162] | [−0.030, 0.165] | 0.031 [−0.074, 0.166] | |
| equity | qwen3-32b | 1.0 | 10 | 0.104 | [0.018, 0.197] | [0.015, 0.195] | [0.019, 0.194] | 0.146 [0.002, 0.291] | |
| crypto | RANDOM | — | 20 | −0.015 | [−0.054, 0.042] | [−0.053, 0.038] | [−0.054, 0.039] | −0.021 | **0.000** (MC) |
| crypto | MOMENTUM | — | 20 | 1.000 | [1, 1] | [1, 1] | [1, 1] | 1.000 | **1** (exact) |
| crypto | NOISY-MOMENTUM | — | 20 | 0.521 | [0.413, 0.592] | [0.425, 0.593] | [0.409, 0.591] | 0.479 | **0.497** ± 0.002 (MC) |
| equity | RANDOM | — | 20 | −0.003 | [−0.029, 0.025] | [−0.027, 0.024] | [−0.027, 0.023] | −0.009 | **0.000** (MC) |
| equity | MOMENTUM | — | 20 | 1.000 | [1, 1] | [1, 1] | [1, 1] | 1.000 | **1** (exact) |
| equity | NOISY-MOMENTUM | — | 20 | 0.497 | [0.396, 0.588] | [0.402, 0.583] | [0.397, 0.593] | 0.502 | **0.502** ± 0.001 (MC) |

**Known values.** "MC" means a Monte Carlo population value from 4,000 replicates on the same
path. All six reference cells recover their known value. Separately, a synthetic coverage study of
the interval (`results/bootstrap_coverage.json`) gives 95–100% coverage at true ι ∈ {0, 0.25, 0.5,
0.9}.

**ι depends on temperature, as expected by construction** (figure below).
- **Mistral:** ι falls from about 0.8 at 0.15–0.2 to 0.42 (crypto) and 0.18 (equity) at 1.0. At
  1.0 its first-try invalid JSON rises to 14–23% and its turnover rises 11–21×.
- **Gemma 3:** stays path-dominated even at 1.0. The replication cell, configured identically to
  the main cell, reproduces it (0.982 vs 0.987 crypto; 0.795 vs 0.776 equity).
- **Qwen3:** ι is low at every temperature on equity. On crypto it is non-monotone (0.58 / −0.02 /
  0.37) with very wide intervals.

**Why Qwen3 is different (descriptive diagnostics, not a tuning input).**
- Qwen3 mostly re-submits its own current weights with small edits. Crypto turnover is 0.009/day
  at its default temperature and 0.003 at 0.2.
- Replicates fall into different portfolios early and then hold them. The cross-replicate SD of
  crypto weights rises from 0.03 on day 1 to about 0.16 by day 50, then stays flat. Cross-replicate
  weight dispersion is about 1.0–1.3× the mean absolute weight, against 0.2–0.5× for the other two
  models.
- The variance therefore comes from *which* portfolio a replicate happened to settle into, not from
  the market path. ι stays near 0 in every 50-day window, so this isn't one stretch of the season.
- At temperature 0.2 the crypto replicates are nearly identical and near flat (daily vol 0.47%), so
  ω² and τ² are both tiny, which explains the [0.12, 1.00] interval.
- Mistral's crypto ι instead swings between 50-day windows (0.35–0.98), which is regime-dependent
  τ² (see Threats).

![ι vs temperature](figures/temperature.png)

## 3. Pairs (main cell, metric: daily net P&L)

| arm | pair | ρ_m [95% CI b=10] | A | B | B/A [CI] | R within 10% of floor | T_years δ=1, R=1 | R=20 | R=∞ |
|---|---|---|---|---|---|---|---|---|---|
| crypto | gemma vs mistral | 0.881 [0.767, 0.965] | 1.62e-4 | 1.33e-4 | 0.82 [0.39, 1.95] | 8.2 [3.9, 19.5] | 3.6 [1.4, 6.2] | 2.1 [0.6, 4.2] | 2.0 [0.6, 4.1] |
| crypto | gemma vs qwen | n/a (ω²_qwen < 0) [−3.1, 3.8] | 6.72e-4 | 2.24e-4 | 0.33 [0.18, 0.55] | 3.3 [1.8, 5.5] | 15.3 [10.2, 19.9] | 11.6 [7.6, 15.8] | 11.4 [7.5, 15.6] |
| crypto | mistral vs qwen | n/a (ω²_qwen < 0) [−3.7, 4.2] | 4.16e-4 | 3.37e-4 | 0.81 [0.38, 1.91] | 8.1 [3.8, 19.1] | 15.2 [10.8, 19.3] | 8.7 [4.9, 13.2] | 8.4 [4.5, 13.0] |
| equity | gemma vs mistral | 0.866 [0.801, 0.907] | 1.81e-5 | 1.10e-5 | 0.61 [0.39, 0.94] | 6.1 [3.9, 9.4] | 7.1 [6.1, 8.2] | 4.5 [3.7, 5.5] | 4.4 [3.5, 5.4] |
| equity | gemma vs qwen | 0.200 [−0.150, 0.544] | 9.11e-6 | 7.00e-6 | 0.77 [0.53, 1.15] | 7.7 [5.3, 11.5] | 14.9 [13.6, 16.3] | 8.7 [7.0, 10.5] | 8.4 [6.6, 10.2] |
| equity | mistral vs qwen | 0.162 [−0.226, 0.510] | 4.29e-5 | 1.26e-5 | 0.29 [0.21, 0.42] | 2.9 [2.1, 4.2] | 15.3 [14.4, 16.3] | 12.0 [10.6, 13.3] | 11.8 [10.4, 13.1] |

How the horizons and replicate counts are computed:
- **Horizon:** T_years = z²(A + B/R)/(δ²σ̄²), with σ̄² the pair-average per-instance variance and
  z² = 7.85. This reduces to the equal-variance form in the task.
- **Full grid:** δ ∈ {0.5, 1, 2} × R ∈ {1, 5, 20, 100, ∞} is in `results/tables.md`. δ = 0.5 needs
  roughly 8–61 years and δ = 2 needs 0.5–3.8.
- **Cost-optimal R\*** = √((B/A)(c_d/c_r)):
  - c_d/c_r = 10: 1.7–2.9
  - c_d/c_r = 100: 5.4–9.1
  - c_d/c_r = 1,000: 17–29

  Per-pair intervals are in the tables file.

**Independence check** (replicate deviations e[k,r,t] across models, replicates matched by index):
- 17 of 18 pair × cell combinations are consistent with zero.
- One cell meets the "clearly non-zero" rule set in PLAN.md: crypto at temperature 1.0, Gemma vs
  Mistral, corr = −0.112, day-block CI [−0.162, −0.035].
  - It lies inside the permutation null [−0.18, 0.18].
  - It is one of 18 tests.
  - Its cross term would change B by +4% (B − 2c = 4.54e-4 vs 4.38e-4).
- In the main cells, |corr| ≤ 0.09 and the implied cross term changes B by at most about 5%. The
  assumption that replicate noise is independent across models is not contradicted at a level
  that matters.

**Boundary check.**
- Qwen3's crypto ω² is negative (−4.7e-6), so ρ_m is undefined for its two crypto pairs.
- A parametric bootstrap under the model at the estimated parameters (ω² floored at 0), with the
  same T and R, gives ω̂² < 0 in **50–52%** of simulations and |ρ̂| > 1 in 1.5–2.1%.
- So the negative estimate is what one expects when the true ω² ≈ 0. It is not a rejection of the
  model. No estimated ρ_m exceeds 1.

**Formula check.** For random replicate subsets of size R ∈ {1, 2, 5, 10, 20}, the variance of the
mean daily difference over block-bootstrap resamples is compared with A/T + B/(RT).
- The ratio of empirical to predicted variance is **flat in R** for every pair. So the 1/R
  structure, and with it the B/A trade-off, holds.
- The level is off. The plug-in formula overstates variance in five pairs (empirical/predicted
  0.66–0.88) and understates it for Gemma vs Qwen on crypto (1.09–1.15).
- The Newey–West analogue is within 6% for four pairs. The two Gemma–Qwen pairs stay off
  (crypto 1.21–1.26, equity 0.79–0.87).
- Daily P&L of these agents is therefore serially dependent, mostly negatively, so plug-in horizons
  are biased: probably too long for most pairs and too short for one.

![formula check](figures/formula_check.png)

## 4. Descriptives (no ranking claims)

Main cells at the default temperature. All cells, including the reference agents, are in
`results/tables.md`.

| arm | model | mean daily ret (bp) | vol/instance (%) | Sharpe ann. (mean of reps) [2.5–97.5% over reps] | turnover/day | flat days % | first-try invalid % | parse failure % after retries |
|---|---|---|---|---|---|---|---|---|
| crypto | gemma-3-27b | 0.1 | 2.67 | 0.01 [−0.17, 0.25] | 0.098 | 0.0 | 1.08 | 0.10 |
| crypto | mistral-24b | 13.7 | 2.38 | 1.14 [0.11, 2.35] | 0.134 | 0.5 | 0.00 | 0.00 |
| crypto | qwen3-32b | 0.4 | 1.21 | 0.16 [−0.59, 0.88] | 0.009 | 2.2 | 0.00 | 0.00 |
| equity | gemma-3-27b | 2.7 | 0.34 | 1.23 [0.84, 1.46] | 0.036 | 0.0 | 0.34 | 0.10 |
| equity | mistral-24b | 3.6 | 0.72 | 0.79 [0.13, 1.73] | 0.095 | 0.1 | 0.00 | 0.00 |
| equity | qwen3-32b | −0.3 | 0.22 | −0.27 [−1.65, 1.58] | 0.111 | 10.7 | 0.00 | 0.00 |

- The highest parse-failure rate in any cell is 1.12% (Mistral, equity, temperature 1.0).
- The highest flat share in any main cell is 10.7% (Qwen3, equity).
- No stop condition is triggered (`results/stop_conditions.json`).
- The Sharpe ratios come from 250 days on one market path. §3 shows such numbers can't separate
  these models.

## 5. Phase 4: decision-level score (EXPLORATORY)

The score is s[k,r,t] = Σ_i w_{i,t}(r_{i,t+1} − mean_j r_{j,t+1}): the cross-sectionally demeaned
P&L of the chosen weights. The same decomposition is applied to s.

**Unit-effect scaling.** Each metric is divided by its own pair-average per-instance SD σ̄. The
effect δ is then a standardized gap in that metric. The reported floor ratio is
(A/σ̄²)_score / (A/σ̄²)_pnl = [ι(1−ρ)]_score / [ι(1−ρ)]_pnl. This **assumes the standardized
effect is the same in both metrics**, which is an assumption, not a finding. A ratio below 1 means
scoring decisions shortens the season.

| arm (assets) | pair | ratio [95% CI] | T_years δ=1, R=∞: P&L → score |
|---|---|---|---|
| crypto (6) | gemma vs mistral | 2.53 [1.28, 8.51] | 2.0 → 5.0 |
| crypto (6) | gemma vs qwen | 0.46 [0.21, 0.86] | 11.4 → 5.2 |
| crypto (6) | mistral vs qwen | 0.82 [0.46, 1.34] | 8.4 → 6.9 |
| equity (30) | gemma vs mistral | 0.82 [0.54, 1.23] | 4.4 → 3.6 |
| equity (30) | gemma vs qwen | 0.56 [0.44, 0.70] | 8.4 → 4.8 |
| equity (30) | mistral vs qwen | 0.11 [0.04, 0.22] | 11.8 → 1.4 |

**Reading.**
- Removing the common market move helps most where two models share a lot of market beta but
  differ in cross-sectional selection: the Qwen pairs, and the 30-asset equity arm.
- It hurts where the models' P&L paths were already very similar (Gemma vs Mistral, crypto, with ρ
  of P&L 0.88). Their difference lives mostly in market exposure, which the score removes.
- The equity arm has three ratios below 1 (two significantly). The crypto arm is mixed.
- On the score, ι for LLMs is lower than on P&L in most cells. For example, Mistral equity is 0.16
  on the score vs 0.84 on P&L, so replication matters more for scores. B/A for the score is
  0.85–9.9.
- This is a single-path, single-period exploratory comparison, not evidence that scoring decisions
  generally shortens the season.

## 6. Threats to validity

- **Replay, not live trading.**
  - Decisions are made on 2025-10 to 2026-10 data, after a window start set at the latest cutoff
    bound plus three months.
  - **Qwen3's knowledge cutoff is undocumented.** I bounded it by its release date (2025-04-29),
    which assumes training data does not postdate release. I can't verify the true cutoff of any of
    the three checkpoints.
  - Models are told they manage a real account. They can't act on the market, so there is no price
  impact or adverse selection.
- **No news inputs.** The models see only six price features per asset. ι could be very different
  with news, where models disagree more.
- **Simplified execution.** Fills at the close, 5 bps × turnover, no funding, borrow, margin or
  liquidation (gross exposure up to 2), and crypto is USDT-quoted rather than USD.
- **Local, mid-size, 4-bit models only.** Three checkpoints (24–32B, AWQ/W4A16 quantization), two
  of them community quantizations. Results may not transfer to frontier or full-precision models.
- **Serial dependence and non-stationarity.**
  - The formula check shows the plug-in variance is biased by −34% to +15%.
  - Newey–West with lag 4 fixes most but not all of it.
  - Mistral's crypto ι varies between 0.35 and 0.98 across 50-day windows, so τ² is regime-dependent.
  - Qwen3's replicate dispersion builds up over the first ~50 days.
  - A 250-day pilot can't separate these from noise.
- **Heavy tails in crypto.** Crypto daily P&L has 3–8× the daily volatility of equity. The sizing
  inflation factors (bootstrap SE / Gaussian parametric SE) of 4.5–5.0 for Gemma and Mistral on
  crypto show that Gaussian approximations understate uncertainty there.
- **Unequal variances within pairs.** Qwen3's per-instance vol is 0.3–0.6× the others'. The pair horizon uses the pair-average variance, which is an
  approximation when variances differ this much.
- **Different calendars per arm.** Crypto covers 2026-01-30 to 2026-10-06 and equity covers
  2025-10-08 to 2026-10-06. Arms are never compared day by day, but they are different market
  periods.
- **Seeding is not bitwise reproducible.** vLLM's per-request seeds don't guarantee identical
  outputs under different batch compositions, so re-running a call may give different text. This
  is why every response is cached and the analysis replays from cache. **Not verified:** whether a
  fresh run would reproduce cached outputs.
- **Data not cross-checked.** Yahoo adjusted closes and Binance closes were not checked against a
  second source.
- **Deviations from PLAN.md** (details in its Deviations section):
  1. `enforce_eager` serving: CUDA-graph capture ran out of memory. Affects speed only.
  2. The bootstrap estimator was corrected for duplicated replicates after the reference agents
     exposed an upward bias of about 1/R in ι. Point estimates are unchanged. This was made before
     any LLM estimate.
  3. Asynchronous per-replicate batching. Prompts, seeds and cache keys are unchanged.
  - Runtime: projected 10.5 h, actual about 17.5 h. Per model: Mistral 4.0 h, Qwen3 6.3 h, Gemma
    7.2 h. The benchmark used identical prompts, which hid prefill cost.
  - The pre-planned stop condition on independence ("clearly non-zero") was met in one of 18 cells.
    It is reported, not acted on, because it is within the permutation null.

## 7. What a larger study would need

These figures come from this pilot's own variance estimates
(`results/sizing.json`, `results/n_models.json`).

**Pinning one model's ι to ±0.05** (95% half-width). Method:
1. Run a parametric simulation at that model's estimates.
2. Inflate the result by the pilot's ratio of bootstrap SE to parametric SE, which accounts for
   tails and serial dependence.

| model | arm | half-width now (T=250, R=20) | cheapest design reaching ±0.05 |
|---|---|---|---|
| gemma-3-27b | crypto | 0.010 | already met (T=250, R=5) |
| gemma-3-27b | equity | 0.102 | T≈1,000 days, R=10 |
| mistral-24b | crypto | 0.147 | T≈4,000 days, R=5 (≈11 years of crypto days); not realistic while τ² is regime-dependent |
| mistral-24b | equity | 0.054 | T≈500 days, R=5 |
| qwen3-32b | crypto | 0.154 | not reliably computable: ω̂² ≈ 0 makes the parametric SE collapse (inflation factor 16) |
| qwen3-32b | equity | 0.056 | T≈500 days, R=20 |

The days dimension is binding; the replicate dimension isn't. Beyond R ≈ 10–20, more replicates
barely narrow ι, because the uncertainty in ω² comes from the single market path.

**Pinning the mean ι across LLM traders to ±0.05.**
- At the default temperature, the between-model SD of ι is 0.53 (crypto) and 0.41 (equity).
- That requires n = (1.96·SD/0.05)² ≈ **440 (crypto) and 250 (equity) models**.
- Uncertainty in the SD from only three models makes the range 70 to more than 10,000.
- This target isn't feasible. ι should be reported **per model** (and per temperature), not as one
  number for "LLM traders".

**Suggested design for a follow-up.**
- 6–10 models from distinct families, including at least one model with a documented cutoff
  well before the window.
- R = 10 at the default temperature, plus R = 10 at two other temperatures.
- At least 750–1,000 equity days, which requires older cutoffs or a live forward run.
- Keep the Newey–West/block-bootstrap machinery and the formula check, because the plug-in variance
  is biased here.
- Run live, forward, to remove the replay threat.

## Provenance and reproduction

- **Market data:** `PROVENANCE.csv` (source, request URL, UTC time, rows, SHA-256), with raw
  responses in `data/raw/`.
- **Models:** `MODEL_HASHES.sha256` and the revisions in PLAN.md.
- **Model responses:** `cache/` holds every model call, write-once: 61,311 files, 365 MB, kept on
  disk and out of git because of size. Each file records prompt, response, seed, sampling params,
  revision and UTC time.
- **Derived data:** `data/derived/llm_*.parquet` and `ref_agents.parquet`.
- **Reproduce from cache, no GPU needed:**
  - `python src/run_llm.py --model <m> --replay-only`
  - `python src/run_ref.py`
  - `python src/analyze.py refs && python src/analyze.py llm`
  - `python src/make_tables.py && python src/make_figures.py`
- **Tests:** `pytest tests` covers no look-ahead (including a check that a leaky feature is
  caught), parser, accounting, seeds, write-once cache, no real date in prompts, estimator
  unbiasedness and the duplicate-replicate correction.
