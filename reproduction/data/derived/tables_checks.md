### C1 How often the estimator returns rho_m > 1 when the model is TRUE

| shocks   | sigma across models   |   true iota |   true rho_m |   median # of 28 inadmissible |    5% |    95% |   P(>= 11, as observed) |   median rho_m_hat |   mean iota_hat |
|:---------|:----------------------|------------:|-------------:|------------------------------:|------:|-------:|------------------------:|-------------------:|----------------:|
| gaussian | equal                 |       0.300 |        0.500 |                         4.000 | 0.000 | 11.000 |                   0.051 |              0.573 |           0.287 |
| gaussian | equal                 |       0.300 |        0.800 |                        10.000 | 3.000 | 18.000 |                   0.433 |              0.890 |           0.284 |
| gaussian | equal                 |       0.300 |        0.950 |                        15.000 | 6.000 | 23.000 |                   0.782 |              1.036 |           0.288 |
| gaussian | equal                 |       0.500 |        0.500 |                         1.000 | 0.000 |  4.000 |                   0.001 |              0.538 |           0.474 |
| gaussian | equal                 |       0.500 |        0.800 |                         5.000 | 1.000 | 12.000 |                   0.091 |              0.851 |           0.475 |
| gaussian | equal                 |       0.500 |        0.950 |                        13.000 | 6.000 | 21.000 |                   0.715 |              0.994 |           0.474 |
| gaussian | equal                 |       0.700 |        0.500 |                         0.000 | 0.000 |  1.000 |                   0.000 |              0.525 |           0.673 |
| gaussian | equal                 |       0.700 |        0.800 |                         1.000 | 0.000 |  4.000 |                   0.000 |              0.827 |           0.672 |
| gaussian | equal                 |       0.700 |        0.950 |                         8.000 | 3.000 | 16.000 |                   0.311 |              0.970 |           0.673 |
| t4       | equal                 |       0.300 |        0.500 |                         4.000 | 0.000 | 10.000 |                   0.049 |              0.566 |           0.292 |
| t4       | equal                 |       0.300 |        0.800 |                         9.000 | 2.000 | 18.000 |                   0.364 |              0.875 |           0.286 |
| t4       | equal                 |       0.300 |        0.950 |                        14.000 | 5.000 | 22.000 |                   0.713 |              1.025 |           0.285 |
| t4       | equal                 |       0.500 |        0.500 |                         1.000 | 0.000 |  6.000 |                   0.001 |              0.533 |           0.466 |
| t4       | equal                 |       0.500 |        0.800 |                         5.000 | 1.000 | 12.000 |                   0.114 |              0.841 |           0.462 |
| t4       | equal                 |       0.500 |        0.950 |                        13.000 | 5.000 | 21.000 |                   0.672 |              0.991 |           0.457 |
| t4       | equal                 |       0.700 |        0.500 |                         0.000 | 0.000 |  1.000 |                   0.000 |              0.511 |           0.659 |
| t4       | equal                 |       0.700 |        0.800 |                         1.000 | 0.000 |  6.000 |                   0.002 |              0.818 |           0.655 |
| t4       | equal                 |       0.700 |        0.950 |                         9.000 | 3.000 | 17.000 |                   0.348 |              0.970 |           0.649 |
| gaussian | observed spread       |       0.500 |        0.950 |                        13.000 | 6.000 | 21.000 |                   0.718 |              0.994 |           0.475 |
| t4       | observed spread       |       0.500 |        0.950 |                        13.000 | 5.000 | 21.000 |                   0.672 |              0.989 |           0.453 |

Observed: **11 of 28** pairs daily with arm effects removed, 13 pooled, 15 at 4-hour frequency. Pooled over all 20 simulation cells the count has median 6 and a 5–95% range of 0–19, with P(count >= 11) = 0.302 and P(count >= 13) = 0.223.

### C2a Daily decomposition under each rescaling (does rho_m > 1 persist?)

| scaling      | arms   | variant   |   R |   median_iota |   median raw rho_m |   pairs with rho_m>1 |   pairs |   omega2<0 |   median_B_over_A |
|:-------------|:-------|:----------|----:|--------------:|-------------------:|---------------------:|--------:|-----------:|------------------:|
| raw          | 1-4    | pooled    |   4 |         0.413 |              0.921 |                    9 |      28 |          0 |             4.116 |
| raw          | 1-4    | arm_day   |   4 |         0.487 |              0.924 |                   10 |      28 |          0 |             2.748 |
| raw          | 1-3    | pooled    |   3 |         0.297 |              1.302 |                   19 |      28 |          0 |             5.013 |
| raw          | 1-3    | arm_day   |   3 |         0.339 |              0.940 |                    9 |      21 |          1 |             3.773 |
| per_leverage | 1-4    | pooled    |   4 |         0.367 |              0.953 |                   11 |      28 |          0 |             8.160 |
| per_leverage | 1-4    | arm_day   |   4 |         0.470 |              0.903 |                    8 |      28 |          0 |             5.661 |
| per_leverage | 1-3    | pooled    |   3 |         0.267 |              1.234 |                   14 |      21 |          1 |            10.911 |
| per_leverage | 1-3    | arm_day   |   3 |         0.325 |              1.047 |                   11 |      21 |          1 |             8.801 |
| per_vol      | 1-4    | pooled    |   4 |         0.432 |              0.922 |                   10 |      28 |          0 |            14.061 |
| per_vol      | 1-4    | arm_day   |   4 |         0.498 |              0.860 |                    4 |      28 |          0 |             7.844 |
| per_vol      | 1-3    | pooled    |   3 |         0.326 |              1.139 |                   19 |      28 |          0 |            14.141 |
| per_vol      | 1-3    | arm_day   |   3 |         0.444 |              0.931 |                   12 |      28 |          0 |            11.367 |

### C2b Final-return ANOVA as risk-taking is removed

| outcome                                          | arms   |   ICC one-way |   ICC arm-FE |   F model (7,21) |   p model |   F arm |   p arm |
|:-------------------------------------------------|:-------|--------------:|-------------:|-----------------:|----------:|--------:|--------:|
| final return % (compounded, as published)        | 1-4    |         0.360 |        0.449 |            4.253 |     0.005 |   3.456 |   0.035 |
| final return % (compounded, as published)        | 1-3    |         0.256 |        0.400 |            3.002 |     0.038 |   4.832 |   0.025 |
| cumulative return % (arithmetic sum of daily)    | 1-4    |         0.220 |        0.311 |            2.808 |     0.031 |   3.543 |   0.032 |
| cumulative return % (arithmetic sum of daily)    | 1-3    |         0.116 |        0.247 |            1.983 |     0.131 |   4.380 |   0.033 |
| leverage-scaled cumulative % (per 1x of gross)   | 1-4    |         0.265 |        0.315 |            2.839 |     0.030 |   2.289 |   0.108 |
| leverage-scaled cumulative % (per 1x of gross)   | 1-3    |         0.267 |        0.342 |            2.562 |     0.064 |   2.796 |   0.095 |
| vol-standardised cumulative (= T x daily Sharpe) | 1-4    |         0.174 |        0.269 |            2.469 |     0.051 |   3.710 |   0.028 |
| vol-standardised cumulative (= T x daily Sharpe) | 1-3    |         0.165 |        0.284 |            2.188 |     0.101 |   3.975 |   0.043 |

### C3 Two-way variance shares with 95% day-bootstrap intervals

| outcome                      | model                | arm (rules)          | residual (interaction + luck)   |   F model (7,21) |   p model |   F arm (3,21) |   p arm |
|:-----------------------------|:---------------------|:---------------------|:--------------------------------|-----------------:|----------:|---------------:|--------:|
| final return %               | 0.384 [0.010, 0.471] | 0.145 [0.007, 0.320] | 0.472 [0.341, 0.862]            |             4.25 |     0.005 |           3.46 |   0.035 |
| leverage-scaled cumulative % | 0.284 [0.054, 0.403] | 0.099 [0.000, 0.266] | 0.617 [0.448, 0.864]            |             2.84 |     0.03  |           2.29 |   0.108 |
| daily Sharpe                 | 0.215 [0.000, 0.322] | 0.199 [0.048, 0.403] | 0.586 [0.438, 0.903]            |             2.47 |     0.051 |           3.71 |   0.028 |

### C4 The same split as raw sums-of-squares shares (no truncation at zero)

| outcome                      |   model |   arm (rules) |   residual |
|:-----------------------------|--------:|--------------:|-----------:|
| final return %               |   0.487 |         0.170 |      0.343 |
| leverage-scaled cumulative % |   0.416 |         0.144 |      0.440 |
| daily Sharpe                 |   0.350 |         0.225 |      0.425 |

### C5 Risk metrics by arm (mean over the 8 models)

|   arm |   daily vol |   mean gross lev |   share in market |   turnover / day |   final return % |
|------:|------------:|-----------------:|------------------:|-----------------:|-----------------:|
|     1 |       0.079 |            5.938 |             0.990 |           38.323 |          -27.968 |
|     2 |       0.054 |            3.120 |             0.905 |           23.862 |           -8.335 |
|     3 |       0.091 |            6.135 |             0.987 |          108.510 |          -40.529 |
|     4 |       0.105 |            7.690 |             0.987 |           29.089 |          -28.456 |

### C6 Is each risk metric a model trait? Two-way ANOVA, arm-adjusted ICC, and whether the arms agree on the model ordering

| metric           |   F model (7,21) |   p model |   ICC arm-FE |   ICC 2.5% |   ICC 97.5% |   F arm (3,21) |   p arm |   Kendall W |   p (perm) |
|:-----------------|-----------------:|----------:|-------------:|-----------:|------------:|---------------:|--------:|------------:|-----------:|
| daily_vol        |          12.6936 |    0.0000 |       0.7451 |     0.4502 |      0.9328 |         7.7441 |  0.0011 |      0.8690 |     0.0000 |
| mean_leverage    |           8.1805 |    0.0001 |       0.6422 |     0.3050 |      0.8985 |        10.4288 |  0.0002 |      0.6875 |     0.0006 |
| share_in_market  |           1.1264 |    0.3841 |       0.0306 |    -0.1836 |      0.5009 |         6.1061 |  0.0037 |      0.4289 |     0.0788 |
| turnover_per_day |           1.4759 |    0.2293 |       0.1063 |    -0.1438 |      0.5821 |        10.2562 |  0.0002 |      0.4732 |     0.0454 |

### C7a Rank of each model within each arm, mean gross leverage (1 = least risk)

| model                |   arm1 |   arm2 |   arm3 |   arm4 |   rank_sum |   mean_value |
|:---------------------|-------:|-------:|-------:|-------:|-----------:|-------------:|
| gpt-5.1              |   1.00 |   3.00 |   1.00 |   3.00 |       8.00 |         3.08 |
| qwen3-max            |   3.00 |   2.00 |   5.00 |   1.00 |      11.00 |         3.73 |
| claude-sonnet-4-5    |   2.00 |   5.00 |   4.00 |   2.00 |      13.00 |         3.81 |
| kimi-k2-thinking     |   4.00 |   4.00 |   2.00 |   5.00 |      15.00 |         4.87 |
| typhoon              |   7.00 |   1.00 |   3.00 |   6.00 |      17.00 |         5.83 |
| gemini-3-pro-preview |   5.00 |   6.00 |   6.00 |   4.00 |      21.00 |         6.14 |
| deepseek-chat-v3.1   |   6.00 |   7.00 |   7.00 |   8.00 |      28.00 |         8.58 |
| grok-4               |   8.00 |   8.00 |   8.00 |   7.00 |      31.00 |         9.73 |

### C7b Rank of each model within each arm, realised daily volatility (1 = least risk)

| model                |   arm1 |   arm2 |   arm3 |   arm4 |   rank_sum |   mean_value |
|:---------------------|-------:|-------:|-------:|-------:|-----------:|-------------:|
| gpt-5.1              |   1.00 |   2.00 |   1.00 |   2.00 |       6.00 |         0.03 |
| qwen3-max            |   2.00 |   1.00 |   5.00 |   1.00 |       9.00 |         0.05 |
| typhoon              |   3.00 |   3.00 |   4.00 |   3.00 |      13.00 |         0.06 |
| claude-sonnet-4-5    |   5.00 |   5.00 |   2.00 |   4.00 |      16.00 |         0.07 |
| gemini-3-pro-preview |   4.00 |   4.00 |   3.00 |   5.00 |      16.00 |         0.07 |
| kimi-k2-thinking     |   6.00 |   6.00 |   6.00 |   6.00 |      24.00 |         0.10 |
| grok-4               |   7.00 |   7.00 |   8.00 |   7.00 |      29.00 |         0.13 |
| deepseek-chat-v3.1   |   8.00 |   8.00 |   7.00 |   8.00 |      31.00 |         0.15 |

### C8 Rank correlation between a model's mean risk metric and its mean final return

| metric           |   Spearman rho |   2.5% |   97.5% |   boot sd |   P(rho<0) in bootstrap |   exact p |
|:-----------------|---------------:|-------:|--------:|----------:|------------------------:|----------:|
| daily_vol        |         -0.619 | -0.952 |   0.238 |     0.354 |                   0.863 |     0.102 |
| mean_leverage    |         -0.357 | -0.810 |   0.238 |     0.279 |                   0.853 |     0.385 |
| share_in_market  |         -0.071 | -0.548 |   0.190 |     0.190 |                   0.818 |     0.867 |
| turnover_per_day |         -0.833 | -0.905 |  -0.381 |     0.131 |                   0.999 |     0.010 |

Trading costs over the same window: **$36,893 of fees across the 32 wallets on a $320,000 book in 13 days, 10.1% of capital**, mean 11.2% per wallet net of $1,163 of funding received. Spearman(cost, final return) = -0.571 (exact p = 0.139).
