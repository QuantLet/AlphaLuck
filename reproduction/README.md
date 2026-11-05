# AlphaLuck reconstruction package

This tree contains the archived Hyperliquid and AI-Trader inputs and the
Alpha Arena calculations. The repository is available at
https://github.com/QuantLet/AlphaLuck.

The self-contained [replication supplement](../replication_20261102/README.txt)
provides the Prediction Arena data and calculations, corrected Alpha Arena
formation sweeps, both joint-stress directions, and prior-only threshold checks.
Use its commands to reproduce the revised threshold results without organiser
snapshots. Derived thresholds do not independently validate the source margin
observations or prove the absence of collateral transfers.

The additional cost, cash/index, instrument-deletion and overlapping-window
checks can be run from this directory with:

```sh
python src/reproduce_additional_checks.py --root .
python src/reproduce_threshold_results.py
```

The first command writes to `data/derived/additional_checks/` and leaves the
editorial tables intact. The second verifies the corrected sweeps and writes
to `data/derived/reproduction/`. Dependencies are in `requirements.lock`.
Prediction Arena needs only Python's standard library for saved-data replay.

The manuscript sources and submission documents are maintained separately
by the authors; this repository publishes research data, code, numerical
tables and figures.

The [October documentation](README_legacy_20261025.md) records the earlier
pipeline and its limitations. It describes an older manuscript and is not a
statement of the current results. Some end-to-end collection commands need
organiser archives that are not redistributed or optional licensed prices.
See [DATA.md](DATA.md). No raw organiser snapshots or credentials are included.
