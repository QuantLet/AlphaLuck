### X1 P&L decomposition, season totals (signed contributions, USD)

| season   |   book $ |   exposure |   timing |   slippage |    fees |   funding |     net |   net % of book |
|:---------|---------:|-----------:|---------:|-----------:|--------:|----------:|--------:|----------------:|
| S1       |    60000 |    -10,397 |   -2,131 |        616 |  -5,271 |      -974 | -18,157 |             -30 |
| S15      |   320000 |     13,514 |  -42,852 |    -19,162 | -36,893 |     1,163 | -84,231 |             -26 |

The identity *equity change = exposure + timing − slippage − fees + funding* closes to at most 0.00% of a $10,000 book per wallet.

### X2 S1.5 P&L decomposition by model (four wallets each, $40,000 book)

| model                |   exposure |   timing |   slippage |   fees |   funding |     net |   net % of $40k |
|:---------------------|-----------:|---------:|-----------:|-------:|----------:|--------:|----------------:|
| typhoon              |      7,066 |    1,164 |     -1,961 | -1,504 |       -37 |   4,728 |              12 |
| gpt-5.1              |      1,809 |    1,558 |     -2,570 | -3,073 |        59 |  -2,217 |              -6 |
| gemini-3-pro-preview |      1,339 |   -6,880 |     -1,794 | -4,328 |       211 | -11,451 |             -29 |
| qwen3-max            |        524 |   -4,686 |     -1,323 | -6,114 |      -131 | -11,729 |             -29 |
| deepseek-chat-v3.1   |      2,343 |   -7,610 |     -1,539 | -5,993 |       427 | -12,371 |             -31 |
| kimi-k2-thinking     |        138 |   -3,339 |     -4,106 | -6,079 |       322 | -13,063 |             -33 |
| claude-sonnet-4-5    |       -143 |   -6,032 |     -4,344 | -4,732 |        52 | -15,199 |             -38 |
| grok-4               |        436 |  -17,027 |     -1,527 | -5,069 |       259 | -22,928 |             -57 |

### X3 S1.5 P&L decomposition by arm (eight wallets each, $80,000 book)

|   competition_id |   exposure |   timing |   slippage |    fees |   funding |     net |   net % of $80k |
|-----------------:|-----------:|---------:|-----------:|--------:|----------:|--------:|----------------:|
|                1 |      4,959 |  -14,794 |     -4,874 |  -8,177 |       513 | -22,374 |             -28 |
|                2 |        864 |     -716 |     -2,247 |  -4,783 |       214 |  -6,668 |              -8 |
|                3 |      2,181 |   -9,425 |     -8,261 | -17,269 |       351 | -32,423 |             -41 |
|                4 |      5,509 |  -17,916 |     -3,780 |  -6,663 |        85 | -22,765 |             -28 |

### X4 Season 1 P&L decomposition by model ($10,000 book each)

| model              |   exposure |   timing |   slippage |   fees |   funding |    net |   net % of $10k |
|:-------------------|-----------:|---------:|-----------:|-------:|----------:|-------:|----------------:|
| qwen3-max          |     -1,542 |    4,893 |        291 | -1,669 |      -469 |  1,504 |              15 |
| deepseek-chat-v3.1 |     -4,948 |    5,979 |        351 |   -729 |      -223 |    429 |               4 |
| claude-sonnet-4-5  |     -1,998 |     -715 |         89 |   -590 |      -141 | -3,356 |             -34 |
| grok-4             |     -2,749 |   -1,340 |       -412 |   -391 |      -114 | -5,007 |             -50 |
| gemini-2.5-pro     |        757 |   -5,251 |        342 | -1,347 |         2 | -5,496 |             -55 |
| gpt-5              |         83 |   -5,697 |        -44 |   -545 |       -28 | -6,232 |             -62 |

### X5 Risk metrics by model and season

| model                | season                |   mean_leverage |   daily_vol |   share_in_market |   turnover_per_day |   final_return_pct |
|:---------------------|:----------------------|----------------:|------------:|------------------:|-------------------:|-------------------:|
| claude-sonnet-4-5    | S1                    |           4.482 |       0.149 |             0.996 |              9.477 |            -33.558 |
| deepseek-chat-v3.1   | S1                    |           6.724 |       0.195 |             0.999 |              9.844 |              4.293 |
| gemini-2.5-pro       | S1                    |           7.947 |       0.225 |             1.000 |             40.587 |            -54.955 |
| gpt-5                | S1                    |           7.892 |       0.207 |             1.000 |             21.136 |            -62.323 |
| grok-4               | S1                    |           7.269 |       0.150 |             1.000 |              9.754 |            -50.068 |
| qwen3-max            | S1                    |           7.474 |       0.165 |             0.997 |             31.123 |             15.041 |
| claude-sonnet-4-5    | S1.5 (mean of 4 arms) |           3.807 |       0.065 |             0.947 |             56.654 |            -37.997 |
| deepseek-chat-v3.1   | S1.5 (mean of 4 arms) |           8.577 |       0.150 |             0.989 |             55.814 |            -30.928 |
| gemini-3-pro-preview | S1.5 (mean of 4 arms) |           6.141 |       0.069 |             0.985 |             38.326 |            -28.628 |
| gpt-5.1              | S1.5 (mean of 4 arms) |           3.081 |       0.035 |             0.988 |             29.544 |             -5.542 |
| grok-4               | S1.5 (mean of 4 arms) |           9.733 |       0.126 |             0.995 |             72.875 |            -57.319 |
| kimi-k2-thinking     | S1.5 (mean of 4 arms) |           4.872 |       0.099 |             0.930 |             53.080 |            -32.659 |
| qwen3-max            | S1.5 (mean of 4 arms) |           3.729 |       0.052 |             0.951 |             63.485 |            -29.323 |
| typhoon              | S1.5 (mean of 4 arms) |           5.826 |       0.062 |             0.950 |              9.888 |             11.819 |

### X6 Does a model's risk appetite carry across seasons?

| match_set             |   n | metric           |   spearman |   spearman_p_exact |   perm_p_one_sided |   pearson |   S1_mean |   S15_mean |   S15_over_S1 |
|:----------------------|----:|:-----------------|-----------:|-------------------:|-------------------:|----------:|----------:|-----------:|--------------:|
| strict (same version) |   4 | mean_leverage    |     -0.200 |              0.800 |              0.621 |     0.438 |     6.488 |      6.462 |         0.996 |
| strict (same version) |   4 | daily_vol        |      0.400 |              0.600 |              0.379 |     0.546 |     0.165 |      0.098 |         0.597 |
| strict (same version) |   4 | share_in_market  |      1.000 |              0.000 |              0.043 |     0.953 |     0.998 |      0.971 |         0.973 |
| strict (same version) |   4 | turnover_per_day |      0.000 |              1.000 |              0.539 |     0.111 |    15.049 |     62.207 |         4.134 |
| strict + family       |   6 | mean_leverage    |     -0.314 |              0.544 |              0.748 |     0.124 |     6.965 |      5.845 |         0.839 |
| strict + family       |   6 | daily_vol        |     -0.086 |              0.872 |              0.600 |    -0.166 |     0.182 |      0.083 |         0.456 |
| strict + family       |   6 | share_in_market  |      0.638 |              0.173 |              0.100 |     0.953 |     0.999 |      0.976 |         0.978 |
| strict + family       |   6 | turnover_per_day |     -0.429 |              0.397 |              0.819 |    -0.456 |    20.320 |     52.783 |         2.598 |

Models common to both seasons: claude-sonnet-4-5, deepseek-chat-v3.1, grok-4, qwen3-max (n = 4). Season 1 is crypto perpetuals over 17 days; Season 1.5 is tokenised US equities over 15 days, so this is a cross-asset, cross-window test.

### X7 Does risk account for the model effect in returns?

| specification                          | covariate      |   F_model | df      |    p_F |   ss_model |   partial_R2_model |   sse_full |   beta_cov |   r2_total |   perm_p |   share_of_between_model_SS_removed |
|:---------------------------------------|:---------------|----------:|:--------|-------:|-----------:|-------------------:|-----------:|-----------:|-----------:|---------:|------------------------------------:|
| A: model + arm                         | -              |    4.2533 | (7, 21) | 0.0046 | 12237.6153 |             0.5864 |  8631.5965 |   nan      |     0.6565 |   0.0028 |                              0.0000 |
| B: + volatility on initial capital     | vol_fixed      |    4.4175 | (7, 20) | 0.0041 | 12009.8029 |             0.6072 |  7767.6666 |   275.7177 |     0.6909 |   0.0069 |                              0.0186 |
| C: + gross exposure on initial capital | leverage_fixed |    5.9246 | (7, 20) | 0.0008 | 12595.6198 |             0.6746 |  6074.2764 |     6.4226 |     0.7583 |   0.0003 |                             -0.0293 |
| D: + volatility on current equity      | daily_vol      |    3.1044 | (7, 20) | 0.0219 |  9356.6695 |             0.5207 |  8611.3325 |    44.3246 |     0.6573 |   0.0267 |                              0.2354 |
| E: + gross leverage on current equity  | mean_leverage  |    3.4142 | (7, 20) | 0.0145 |  9890.4581 |             0.5444 |  8276.6443 |    -2.4669 |     0.6706 |   0.0168 |                              0.1918 |

### X8 Permutation p-values beside the F-based ones (model labels permuted within arm, 10,000 draws)

| outcome                                  | test           | df     |       F |    p_F |   p_perm | perm_scheme             |
|:-----------------------------------------|:---------------|:-------|--------:|-------:|---------:|:------------------------|
| final return % (published, sec 9/13)     | F_model_oneway | (7,24) |  3.2544 | 0.0142 |   0.0037 | model labels within arm |
| final return % (published, sec 9/13)     | F_model_armFE  | (7,21) |  4.2533 | 0.0046 |   0.0037 | model labels within arm |
| final return % (published, sec 9/13)     | F_arm          | (3,21) |  3.4555 | 0.0349 |   0.0370 | arm labels within model |
| cumulative return % arithmetic (sec 15)  | F_model_oneway | (7,24) |  2.1310 | 0.0791 |   0.0106 | model labels within arm |
| cumulative return % arithmetic (sec 15)  | F_model_armFE  | (7,21) |  2.8083 | 0.0314 |   0.0106 | model labels within arm |
| cumulative return % arithmetic (sec 15)  | F_arm          | (3,21) |  3.5428 | 0.0322 |   0.0262 | arm labels within model |
| leverage-scaled cumulative % (sec 15/16) | F_model_oneway | (7,24) |  2.4448 | 0.0483 |   0.0325 | model labels within arm |
| leverage-scaled cumulative % (sec 15/16) | F_model_armFE  | (7,21) |  2.8388 | 0.0301 |   0.0325 | model labels within arm |
| leverage-scaled cumulative % (sec 15/16) | F_arm          | (3,21) |  2.2892 | 0.1079 |   0.1157 | arm labels within model |
| vol-standardised cumulative (sec 15)     | F_model_oneway | (7,24) |  1.8441 | 0.1246 |   0.0474 | model labels within arm |
| vol-standardised cumulative (sec 15)     | F_model_armFE  | (7,21) |  2.4688 | 0.0514 |   0.0474 | model labels within arm |
| vol-standardised cumulative (sec 15)     | F_arm          | (3,21) |  3.7101 | 0.0276 |   0.0308 | arm labels within model |
| daily Sharpe (sec 16)                    | F_model_oneway | (7,24) |  1.8441 | 0.1246 |   0.0460 | model labels within arm |
| daily Sharpe (sec 16)                    | F_model_armFE  | (7,21) |  2.4688 | 0.0514 |   0.0460 | model labels within arm |
| daily Sharpe (sec 16)                    | F_arm          | (3,21) |  3.7101 | 0.0276 |   0.0269 | arm labels within model |
| realised daily volatility (sec 17)       | F_model_oneway | (7,24) |  6.8874 | 0.0002 |   0.0001 | model labels within arm |
| realised daily volatility (sec 17)       | F_model_armFE  | (7,21) | 12.6936 | 0.0000 |   0.0001 | model labels within arm |
| realised daily volatility (sec 17)       | F_arm          | (3,21) |  7.7441 | 0.0011 |   0.0022 | arm labels within model |
| mean gross leverage (sec 17)             | F_model_oneway | (7,24) |  3.7549 | 0.0069 |   0.0006 | model labels within arm |
| mean gross leverage (sec 17)             | F_model_armFE  | (7,21) |  8.1805 | 0.0001 |   0.0006 | model labels within arm |
| mean gross leverage (sec 17)             | F_arm          | (3,21) | 10.4288 | 0.0002 |   0.0002 | arm labels within model |
| share of time in market (sec 17)         | F_model_oneway | (7,24) |  0.6876 | 0.6815 |   0.3349 | model labels within arm |
| share of time in market (sec 17)         | F_model_armFE  | (7,21) |  1.1264 | 0.3841 |   0.3349 | model labels within arm |
| share of time in market (sec 17)         | F_arm          | (3,21) |  6.1061 | 0.0037 |   0.0052 | arm labels within model |
| turnover per day (sec 17)                | F_model_oneway | (7,24) |  0.6842 | 0.6841 |   0.1206 | model labels within arm |
| turnover per day (sec 17)                | F_model_armFE  | (7,21) |  1.4759 | 0.2293 |   0.1206 | model labels within arm |
| turnover per day (sec 17)                | F_arm          | (3,21) | 10.2562 | 0.0002 |   0.0002 | arm labels within model |

### X9 Wallet-level risk-return relation, within arm, n = 32

| metric           |   mean_within_arm_rho |   perm_p_one_sided |   perm_p_two_sided |   pooled_centred_rank_rho |   pooled_perm_p_one_sided |   pooled_perm_p_two_sided |   naive_spearman_all32 |   naive_p_all32 |   rho_arm1 |   rho_arm2 |   rho_arm3 |   rho_arm4 |
|:-----------------|----------------------:|-------------------:|-------------------:|--------------------------:|--------------------------:|--------------------------:|-----------------------:|----------------:|-----------:|-----------:|-----------:|-----------:|
| daily_vol        |               -0.5119 |             0.0023 |             0.0047 |                   -0.5119 |                    0.0023 |                    0.0047 |                -0.4967 |          0.0038 |    -0.4286 |    -0.1190 |    -0.6667 |    -0.8333 |
| mean_leverage    |               -0.3452 |             0.0343 |             0.0671 |                   -0.3452 |                    0.0365 |                    0.0709 |                -0.4326 |          0.0134 |    -0.0476 |    -0.1190 |    -0.7143 |    -0.5000 |
| turnover_per_day |               -0.4464 |             0.0087 |             0.0172 |                   -0.4464 |                    0.0087 |                    0.0172 |                -0.6114 |          0.0002 |    -0.6429 |     0.0000 |    -0.9524 |    -0.1905 |
| share_in_market  |                0.2746 |             0.9257 |             0.1489 |                    0.2746 |                    0.9273 |                    0.1510 |                -0.0649 |          0.7241 |     0.1905 |     0.3571 |     0.7785 |    -0.2275 |

### X10 Required horizon for a Sharpe gap of 1 at R = 1, under long-run variances

| frequency   | variant   | lrv_method   |   T_years_median |   T_years_q25 |   T_years_q75 |   T_years_min |   T_years_max |   ratio_to_iid |
|:------------|:----------|:-------------|-----------------:|--------------:|--------------:|--------------:|--------------:|---------------:|
| daily       | pooled    | iid          |           11.280 |         9.412 |        12.152 |         8.222 |        13.807 |          1.000 |
| daily       | pooled    | NW lag 1     |            9.457 |         8.787 |        10.507 |         7.514 |        13.120 |          0.838 |
| daily       | pooled    | NW lag 2     |            9.556 |         8.143 |        10.095 |         7.206 |        12.545 |          0.847 |
| daily       | pooled    | NW lag 3     |            9.456 |         8.016 |        10.465 |         5.954 |        13.719 |          0.838 |
| daily       | pooled    | block 2      |            9.473 |         8.804 |        10.386 |         7.073 |        12.568 |          0.840 |
| daily       | pooled    | block 3      |            9.095 |         7.917 |         9.750 |         6.150 |        11.712 |          0.806 |
| daily       | arm_day   | iid          |           10.429 |         8.869 |        11.594 |         5.975 |        13.418 |          1.000 |
| daily       | arm_day   | NW lag 1     |            8.805 |         8.164 |         9.799 |         6.088 |        12.730 |          0.844 |
| daily       | arm_day   | NW lag 2     |            8.378 |         7.770 |         9.651 |         6.089 |        13.117 |          0.803 |
| daily       | arm_day   | NW lag 3     |            8.336 |         7.145 |         9.829 |         5.881 |        14.400 |          0.799 |
| daily       | arm_day   | block 2      |            8.981 |         7.754 |         9.904 |         5.842 |        12.518 |          0.861 |
| daily       | arm_day   | block 3      |            7.911 |         7.270 |         9.299 |         5.353 |        11.900 |          0.759 |
| 4h          | pooled    | iid          |           11.532 |        10.427 |        12.048 |         8.476 |        14.629 |          1.000 |
| 4h          | pooled    | NW lag 1     |           10.742 |         9.612 |        11.474 |         7.581 |        13.473 |          0.932 |
| 4h          | pooled    | NW lag 2     |           10.902 |         9.270 |        11.503 |         7.581 |        13.306 |          0.945 |
| 4h          | pooled    | NW lag 3     |           10.874 |         9.361 |        11.502 |         7.678 |        13.516 |          0.943 |
| 4h          | pooled    | block 2      |           10.703 |         9.622 |        11.459 |         7.617 |        13.185 |          0.928 |
| 4h          | pooled    | block 3      |           10.989 |         9.304 |        11.585 |         7.468 |        13.427 |          0.953 |
| 4h          | arm_day   | iid          |           11.070 |         9.730 |        12.060 |         7.753 |        14.047 |          1.000 |
| 4h          | arm_day   | NW lag 1     |           10.013 |         9.502 |        11.019 |         6.566 |        12.317 |          0.905 |
| 4h          | arm_day   | NW lag 2     |           10.042 |         8.786 |        11.128 |         6.607 |        12.965 |          0.907 |
| 4h          | arm_day   | NW lag 3     |           10.031 |         8.824 |        11.039 |         6.726 |        13.252 |          0.906 |
| 4h          | arm_day   | block 2      |           10.079 |         9.498 |        11.080 |         6.550 |        12.390 |          0.911 |
| 4h          | arm_day   | block 3      |           10.058 |         8.722 |        11.100 |         6.588 |        12.961 |          0.909 |

### X11 Autocorrelation of daily return differences across the 28 pairs

| frequency   | variant   |   acf_lag1_mean |   acf_lag2_mean |   acf_lag3_mean |   acf_lag1_median |   acf_lag2_median |   acf_lag3_median |   acf_lag1_min |   acf_lag2_min |   acf_lag3_min |   acf_lag1_max |   acf_lag2_max |   acf_lag3_max |   n_pairs |
|:------------|:----------|----------------:|----------------:|----------------:|------------------:|------------------:|------------------:|---------------:|---------------:|---------------:|---------------:|---------------:|---------------:|----------:|
| daily       | pooled    |         -0.0619 |         -0.0179 |          0.0053 |           -0.0477 |           -0.0085 |            0.0028 |        -0.3220 |        -0.2383 |        -0.1041 |         0.0959 |         0.1573 |         0.1748 |        28 |
| daily       | arm_day   |         -0.0427 |         -0.0200 |          0.0062 |           -0.0182 |           -0.0166 |            0.0109 |        -0.2325 |        -0.2134 |        -0.1549 |         0.1308 |         0.0888 |         0.1560 |        28 |
| 4h          | pooled    |         -0.0185 |          0.0236 |         -0.0090 |           -0.0151 |            0.0234 |           -0.0064 |        -0.1743 |        -0.0646 |        -0.0968 |         0.0982 |         0.1139 |         0.0339 |        28 |
| 4h          | arm_day   |         -0.0356 |          0.0195 |         -0.0040 |           -0.0204 |            0.0143 |           -0.0102 |        -0.2268 |        -0.0736 |        -0.0632 |         0.0938 |         0.1122 |         0.0519 |        28 |

### X12 Does risk appetite persist past the official season end?

| metric             |   rho wallets (n=32) |   perm p |   perm p (within arm) |   rho model means (n=8) |   Kendall W across periods |
|:-------------------|---------------------:|---------:|----------------------:|------------------------:|---------------------------:|
| mean_leverage      |               0.9021 |   0.0000 |                0.0000 |                  0.9048 |                     0.9524 |
| mean_leverage_init |               0.8409 |   0.0000 |                0.0000 |                  0.9286 |                     0.9643 |
| daily_vol          |               0.6096 |   0.0002 |                0.0025 |                  0.8333 |                     0.9167 |

### X13 Two-way ANOVA in the post-season period alone

| metric             |   F model (in-season) |   ICC (in-season) |   F model (post) |   p (post) |   ICC (post) |   ICC 2.5% |   ICC 97.5% |   F arm (post) |   p arm (post) |
|:-------------------|----------------------:|------------------:|-----------------:|-----------:|-------------:|-----------:|------------:|---------------:|---------------:|
| mean_leverage      |                8.1805 |            0.6422 |           3.7318 |     0.0089 |       0.4058 |     0.0604 |      0.7961 |         8.5089 |         0.0007 |
| mean_leverage_init |                2.1096 |            0.2172 |           4.2007 |     0.0049 |       0.4445 |     0.0940 |      0.8157 |         4.6468 |         0.0121 |
| daily_vol          |               12.6936 |            0.7451 |           3.2266 |     0.0175 |       0.3576 |     0.0213 |      0.7697 |         6.1310 |         0.0037 |

Post-season window 2025-12-03 22:00 to 2025-12-12 16:04 (8.8 days, 10 trading days per wallet, 74,741 fills against 166,984 in-season).
