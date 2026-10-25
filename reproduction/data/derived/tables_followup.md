### F1 The four competitions are four treatment arms (organiser's own descriptions)

|   competition_id | title                 | subtitle                                                                                                                                    |   prompts_seen |   with_peer_standings |
|-----------------:|:----------------------|:--------------------------------------------------------------------------------------------------------------------------------------------|---------------:|----------------------:|
|                1 | New Baseline          | Trades equities, ingests news/sentiment data, wider action space                                                                            |             29 |                     0 |
|                2 | Monk Mode             | New experimental system prompt & harness, ~50% shorter than baseline, more opinionated guardrails on trading thresholds and risk management |             27 |                     0 |
|                3 | Situational Awareness | Awareness of competition & leaderboard + other model's positions                                                                            |             25 |                    25 |
|                4 | Max Leverage          | Max leverage on every trade, max capital efficiency, tests risk management                                                                  |             19 |                     0 |

### F2 Behavioural metrics by arm, pooled over the 8 models (Friedman, models as blocks)

| metric              |   arm1_mean |   arm2_mean |   arm3_mean |   arm4_mean |   max_over_min_arm_mean |   friedman_chi2 |   p_value |   kendall_W |
|:--------------------|------------:|------------:|------------:|------------:|------------------------:|----------------:|----------:|------------:|
| mean_leverage       |      5.9385 |      3.1198 |      6.1353 |      7.6900 |                  2.4649 |         15.7500 |    0.0013 |      0.6562 |
| median_leverage     |      6.2760 |      3.1586 |      5.8129 |      8.6209 |                  2.7293 |         12.4500 |    0.0060 |      0.5187 |
| p95_leverage        |      9.7148 |      6.0885 |     11.6223 |     12.5330 |                  2.0585 |         15.4500 |    0.0015 |      0.6437 |
| mean_gross_notional |  45886.4687 |  28530.2831 |  37266.8464 |  54664.0917 |                  1.9160 |          6.4500 |    0.0917 |      0.2687 |
| roundtrips_per_day  |     26.9685 |     18.5391 |     38.7583 |     18.5872 |                  2.0906 |         10.5949 |    0.0141 |      0.4415 |
| fills_per_day       |    328.0732 |    241.3186 |    595.8250 |    247.4576 |                  2.4690 |         15.7500 |    0.0013 |      0.6562 |
| median_hold_h       |      0.5233 |      0.7377 |      0.8319 |      0.6505 |                  1.5897 |          9.1500 |    0.0274 |      0.3813 |
| instrument_hhi      |      0.2529 |      0.2460 |      0.2753 |      0.3626 |                  1.4740 |         11.5500 |    0.0091 |      0.4812 |
| share_index_xyz100  |      0.3595 |      0.2384 |      0.3387 |      0.5171 |                  2.1690 |         12.4500 |    0.0060 |      0.5187 |

### F3 Final-return decomposition, with and without an arm fixed effect

| specification                                  |   sd_within_model_pp |   sd_between_model_pp |   ICC |   F_model | df     |   p_model |
|:-----------------------------------------------|---------------------:|----------------------:|------:|----------:|:-------|----------:|
| one-way (audit T6): arms treated as replicates |               23.177 |                17.400 | 0.360 |     3.254 | (7,24) |     0.014 |
| two-way: arm fixed effect removed              |               20.274 |                18.284 | 0.449 |     4.253 | (7,21) |     0.005 |

Arm main effect: F(3,21) = 3.46, p = 0.0349. Arm effects on final return, percentage points against the grand mean: arm 1 -1.6, arm 2 +18.0, arm 3 -14.2, arm 4 -2.1. Arm differences account for 33.0% of what the one-way model charged to within-model luck.

### F4a Daily variance components per model [pooled], R=4, T=13

| model                |   mean_daily_% |   tau_% (replicate sd) |   omega_% (path sd) |   iota |   iota_2.5% |   iota_97.5% |   iota_jk_lo |   iota_jk_hi |
|:---------------------|---------------:|-----------------------:|--------------------:|-------:|------------:|-------------:|-------------:|-------------:|
| claude-sonnet-4-5    |         -3.289 |                  5.083 |               4.692 |  0.460 |       0.100 |        0.934 |        0.233 |        0.554 |
| deepseek-chat-v3.1   |         -2.406 |                 11.908 |               9.469 |  0.387 |       0.100 |        0.919 |        0.305 |        0.480 |
| gemini-3-pro-preview |         -2.660 |                  5.304 |               5.265 |  0.496 |       0.159 |        0.910 |        0.403 |        0.637 |
| gpt-5.1              |         -0.523 |                  3.496 |               1.971 |  0.241 |       0.052 |        0.779 |        0.152 |        0.287 |
| grok-4               |         -6.468 |                 10.592 |               8.649 |  0.400 |       0.160 |        0.905 |        0.289 |        0.431 |
| kimi-k2-thinking     |         -2.439 |                  6.469 |               8.062 |  0.608 |       0.196 |        0.919 |        0.521 |        0.677 |
| qwen3-max            |         -2.892 |                  5.927 |               3.178 |  0.223 |       0.000 |        0.847 |        0.045 |        0.420 |
| typhoon              |          0.673 |                  4.976 |               4.283 |  0.426 |       0.074 |        0.924 |        0.269 |        0.601 |

### F4b Daily variance components per model [arm effects removed], R=4, T=13

| model                |   mean_daily_% |   tau_% (replicate sd) |   omega_% (path sd) |   iota |   iota_2.5% |   iota_97.5% |   iota_jk_lo |   iota_jk_hi |
|:---------------------|---------------:|-----------------------:|--------------------:|-------:|------------:|-------------:|-------------:|-------------:|
| claude-sonnet-4-5    |         -3.289 |                  4.986 |               4.718 |  0.472 |       0.120 |        0.962 |        0.321 |        0.614 |
| deepseek-chat-v3.1   |         -2.406 |                  9.332 |              10.166 |  0.543 |       0.218 |        0.971 |        0.459 |        0.680 |
| gemini-3-pro-preview |         -2.660 |                  4.852 |               5.372 |  0.551 |       0.045 |        0.949 |        0.357 |        0.665 |
| gpt-5.1              |         -0.523 |                  4.716 |               1.175 |  0.058 |       0.000 |        0.714 |        0.000 |        0.094 |
| grok-4               |         -6.468 |                  9.036 |               9.080 |  0.502 |       0.258 |        0.925 |        0.376 |        0.584 |
| kimi-k2-thinking     |         -2.439 |                  5.536 |               8.234 |  0.689 |       0.323 |        0.961 |        0.590 |        0.745 |
| qwen3-max            |         -2.892 |                  4.620 |               3.681 |  0.388 |       0.070 |        0.912 |        0.284 |        0.487 |
| typhoon              |          0.673 |                  4.848 |               4.319 |  0.443 |       0.069 |        0.926 |        0.263 |        0.584 |

### F5 Variance-component summary, and the admissibility diagnostic

| frequency   | variant   |   T_periods |   median_iota |   iota_CI_lo |   iota_CI_hi |   median_rho_m |   median_B_over_A | pairs_with_rho_m>1   |   raw_rho_m_median |   raw_rho_m_max |   omega2<0 |
|:------------|:----------|------------:|--------------:|-------------:|-------------:|---------------:|------------------:|:---------------------|-------------------:|----------------:|-----------:|
| daily       | pooled    |          14 |         0.413 |        0.100 |        0.914 |          0.921 |             4.116 | 9/28                 |              0.921 |           1.486 |          0 |
| daily       | arm_level |          14 |         0.422 |        0.109 |        0.905 |          0.919 |             3.566 | 8/28                 |              0.919 |           1.431 |          0 |
| daily       | arm_day   |          14 |         0.487 |        0.095 |        0.937 |          0.924 |             2.748 | 10/28                |              0.924 |           2.126 |          0 |
| 4h          | pooled    |          84 |         0.409 |        0.236 |        0.854 |          0.871 |             7.252 | 6/28                 |              0.871 |           1.310 |          0 |
| 4h          | arm_level |          84 |         0.407 |        0.226 |        0.858 |          0.866 |             7.056 | 6/28                 |              0.866 |           1.286 |          0 |
| 4h          | arm_day   |          84 |         0.433 |        0.218 |        0.893 |          0.872 |             5.093 | 9/28                 |              0.872 |           1.197 |          0 |

### F6 Pairwise quantities, daily, arm effects removed (28 pairs)

|      |   rho_m |      A |      B |   B_over_A |
|:-----|--------:|-------:|-------:|-----------:|
| mean |  0.8378 | 0.0031 | 0.0079 |     8.1665 |
| 25%  |  0.6779 | 0.0013 | 0.0047 |     1.8131 |
| 50%  |  0.9245 | 0.0028 | 0.0055 |     2.7477 |
| 75%  |  1.0000 | 0.0048 | 0.0109 |     4.7027 |
| min  |  0.3567 | 0.0000 | 0.0044 |     1.0612 |
| max  |  1.0000 | 0.0081 | 0.0169 |   109.9627 |

### F7 Years needed to detect an annualised Sharpe gap, per pair (median over 28 pairs; 'year' = 252 trading days)

| freq   | variant   |   delta |   T_years_R1 |   T_years_R1 (no decomposition) |   T_years_R4 |   T_years_R20 |   T_years_R100 |   T_years_Rinf |   R for within 10% of floor |
|:-------|:----------|--------:|-------------:|--------------------------------:|-------------:|--------------:|---------------:|---------------:|----------------------------:|
| daily  | pooled    |    0.50 |        46.51 |                           43.75 |        18.61 |         10.73 |           9.29 |           8.93 |                       41.16 |
| daily  | pooled    |    1.00 |        11.63 |                           10.94 |         4.65 |          2.68 |           2.32 |           2.23 |                       41.16 |
| daily  | pooled    |    2.00 |         2.91 |                            2.73 |         1.16 |          0.67 |           0.58 |           0.56 |                       41.16 |
| daily  | arm_day   |    0.50 |        43.19 |                           40.55 |        20.68 |         13.74 |          12.49 |          12.18 |                       27.48 |
| daily  | arm_day   |    1.00 |        10.80 |                           10.14 |         5.17 |          3.43 |           3.12 |           3.05 |                       27.48 |
| daily  | arm_day   |    2.00 |         2.70 |                            2.53 |         1.29 |          0.86 |           0.78 |           0.76 |                       27.48 |
| 4h     | pooled    |    0.50 |        46.15 |                           45.98 |        15.85 |          7.72 |           5.98 |           5.55 |                       72.52 |
| 4h     | pooled    |    1.00 |        11.54 |                           11.50 |         3.96 |          1.93 |           1.49 |           1.39 |                       72.52 |
| 4h     | pooled    |    2.00 |         2.88 |                            2.87 |         0.99 |          0.48 |           0.37 |           0.35 |                       72.52 |
| 4h     | arm_day   |    0.50 |        45.32 |                           44.12 |        16.98 |          9.14 |           7.56 |           7.17 |                       50.93 |
| 4h     | arm_day   |    1.00 |        11.33 |                           11.03 |         4.24 |          2.28 |           1.89 |           1.79 |                       50.93 |
| 4h     | arm_day   |    2.00 |         2.83 |                            2.76 |         1.06 |          0.57 |           0.47 |           0.45 |                       50.93 |

### F8 The same, daily, with 95% bootstrap intervals

| variant   |   delta | R=1                  | R=4 (this arena)    | R=20                | R=inf (floor)       |
|:----------|--------:|:---------------------|:--------------------|:--------------------|:--------------------|
| pooled    |     0.5 | 46.51 [13.50, 72.72] | 18.61 [6.21, 44.22] | 10.73 [3.52, 38.11] | 8.93 [2.54, 36.75]  |
| pooled    |     1   | 11.63 [3.37, 18.18]  | 4.65 [1.55, 11.06]  | 2.68 [0.88, 9.53]   | 2.23 [0.63, 9.19]   |
| pooled    |     2   | 2.91 [0.84, 4.55]    | 1.16 [0.39, 2.76]   | 0.67 [0.22, 2.38]   | 0.56 [0.16, 2.30]   |
| arm_day   |     0.5 | 43.19 [10.69, 72.39] | 20.68 [5.46, 46.74] | 13.74 [3.81, 41.42] | 12.18 [3.19, 40.39] |
| arm_day   |     1   | 10.80 [2.67, 18.10]  | 5.17 [1.36, 11.69]  | 3.43 [0.95, 10.36]  | 3.05 [0.80, 10.10]  |
| arm_day   |     2   | 2.70 [0.67, 4.52]    | 1.29 [0.34, 2.92]   | 0.86 [0.24, 2.59]   | 0.76 [0.20, 2.52]   |

### F9 Headline similarity with 95% day-bootstrap intervals


**aggregate signed-exposure correlation**

| quantity                   |   estimate |   ci_lo |   ci_hi |   boot_sd |
|:---------------------------|-----------:|--------:|--------:|----------:|
| different models, same arm |     0.6269 |  0.1600 |  0.7298 |    0.1241 |
| same model, different arm  |     0.6551 |  0.1682 |  0.7317 |    0.1145 |
| difference                 |    -0.0283 | -0.0995 |  0.0151 |    0.0306 |

**same-direction share**

| quantity                   |   estimate |   ci_lo |   ci_hi |   boot_sd |
|:---------------------------|-----------:|--------:|--------:|----------:|
| different models, same arm |     0.9070 |  0.8729 |  0.9384 |    0.0154 |
| same model, different arm  |     0.9259 |  0.8971 |  0.9463 |    0.0114 |
| difference                 |    -0.0189 | -0.0288 | -0.0052 |    0.0063 |

### F10 Similarity by model (exposure correlation)

| model                | vs other models, same arm   | vs itself, other arms   |   difference |
|:---------------------|:----------------------------|:------------------------|-------------:|
| claude-sonnet-4-5    | 0.618 [0.167, 0.711]        | 0.599 [0.279, 0.711]    |        0.019 |
| deepseek-chat-v3.1   | 0.595 [0.212, 0.752]        | 0.668 [0.219, 0.803]    |       -0.073 |
| gemini-3-pro-preview | 0.677 [0.113, 0.790]        | 0.852 [0.059, 0.900]    |       -0.176 |
| gpt-5.1              | 0.674 [0.236, 0.760]        | 0.725 [0.327, 0.831]    |       -0.051 |
| grok-4               | 0.621 [0.134, 0.732]        | 0.617 [0.054, 0.752]    |        0.004 |
| kimi-k2-thinking     | 0.636 [0.148, 0.722]        | 0.647 [0.144, 0.724]    |       -0.011 |
| qwen3-max            | 0.568 [0.122, 0.726]        | 0.515 [0.078, 0.710]    |        0.054 |
| typhoon              | 0.627 [0.157, 0.699]        | 0.619 [0.217, 0.755]    |        0.008 |

### F11 Similarity by arm, so item 1's rule differences are visible


**different-model pairs, within each arm**

| quantity   |   estimate |   ci_lo |   ci_hi |   boot_sd |
|:-----------|-----------:|--------:|--------:|----------:|
| arm 1      |     0.6542 |  0.0754 |  0.7735 |    0.1469 |
| arm 2      |     0.6332 |  0.1677 |  0.7302 |    0.1122 |
| arm 3      |     0.4885 |  0.1152 |  0.6514 |    0.1333 |
| arm 4      |     0.7316 |  0.3039 |  0.8586 |    0.1416 |

**same-model pairs, by which two arms**

| quantity   |   estimate |   ci_lo |   ci_hi |   boot_sd |
|:-----------|-----------:|--------:|--------:|----------:|
| arms 1+2   |     0.6678 |  0.2252 |  0.7316 |    0.1038 |
| arms 1+3   |     0.6207 |  0.1591 |  0.7118 |    0.1161 |
| arms 1+4   |     0.7551 |  0.1702 |  0.8436 |    0.1424 |
| arms 2+3   |     0.5602 |  0.2039 |  0.6673 |    0.1027 |
| arms 2+4   |     0.7027 |  0.1951 |  0.7531 |    0.1194 |
| arms 3+4   |     0.6243 |  0.1701 |  0.7293 |    0.1255 |

### F12 ICC of S1.5 final returns, exact F-based 95% interval

| specification                                  |     F | df     |   p_value |   ICC |   ICC_2.5% |   ICC_97.5% |   sd_model_pp |   sd_err_pp |
|:-----------------------------------------------|------:|:-------|----------:|------:|-----------:|------------:|--------------:|------------:|
| one-way (audit T6; arms treated as replicates) | 3.254 | (7,24) |     0.014 | 0.360 |      0.032 |       0.770 |        17.400 |      23.177 |
| consistency, arm fixed effect removed (item 1) | 4.253 | (7,21) |     0.005 | 0.449 |      0.098 |       0.818 |        18.284 |      20.274 |
