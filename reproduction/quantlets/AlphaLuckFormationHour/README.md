# AlphaLuckFormationHour

Season 1.5 frozen-book comparison for every formation hour, over the
remaining season and over fixed horizons, and two margin policies that
bracket feasibility.

```
python AlphaLuckFormationHour.py
```

![formation hour](AlphaLuckFormationHour.png)

## What it does

`data/sweep_accounts.csv` holds, for each formation hour 1-336 and each of
the 32 accounts, the hourly-funded frozen and realised results produced by
`src/organiser_hourly.py` in the reconstruction project (the 12-, 24- and
48-hour rows equal the published hourly-funding comparison to 1e-6 USD), and
the outcome under two margin policies:

- **account-wide**: frozen equity against summed asset maintenance margins
  (5 per cent per single stock, 2.5 per cent for XYZ100) on a five-minute grid;
- **passive isolated**: each frozen position keeps its formation isolated
  margin with no transfers; its threshold is the organiser's liquidation price
  for the same position, shifted for frozen funding, and pooled trade prints
  trigger liquidation, which returns (A) or forfeits (B) remaining maintenance
  margin.

Later formations leave less time before the close, so the account rows also
carry frozen minus realised 1, 3 and 7 days after formation (`advantage_24h`,
`advantage_72h`, `advantage_168h`; empty when the horizon passes the close),
and the script reports the advantage to the close per remaining day.

The script recomputes every per-hour aggregate from the account rows, checks
them against `data/reference.json` and fails on any difference.

## Results

| Formation | Marked advantage (pp) | Ahead | Isolated accounts liquidated | Isolated A | Isolated B |
|---|---|---|---|---|---|
| 12 h | 27.33 | 26/32 | 27 | 20.36 | 5.74 |
| 24 h | 29.12 | 26/32 | 26 | 20.44 | 10.10 |
| 48 h | 27.07 | 25/32 | 19 | 29.57 | 24.32 |
| all 336 h | -17.4 to 33.8, positive in 269 | 8-31 | | positive in 307 | positive in 251 |

| Horizon after formation | Formation hours | Frozen ahead | Median (pp) | 24 h formation (pp) | Its percentile |
|---|---|---|---|---|---|
| 1 day | 313 | 249 | 0.9 | 10.7 | 96 |
| 3 days | 265 | 206 | 2.0 | 14.0 | 85 |
| 7 days | 169 | 151 | 7.4 | 22.2 | 89 |
| to the close, per remaining day | 336 | 269 | 0.67 | 2.23 | 96 |

Over equal horizons the frozen book is ahead for most formation hours; the
24-hour formation used in the letter lies near the top of each distribution.

## Boundaries

- Organiser snapshots are not exchange records, and are not included here.
  Organiser liquidation prices follow the isolated-margin formula for the
  actual positions; they describe the frozen book only under the passive
  isolated policy.
- Pooled trade prints missed 2 of 14 actual liquidations whose position was
  unchanged since the last snapshot and raised no false alarm in 37,701
  fill-free intervals; mark prices, partial liquidation, fees and backstop
  rules are not replayed.
- Formation hours share one market path and overlapping horizons are not
  independent observations.
