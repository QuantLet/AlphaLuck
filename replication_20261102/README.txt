AlphaLuck: replication supplement, 4 November 2026

This supplement accompanies Trading versus Holding in a Live Language-Model
Competition and its online appendix. It covers the Alpha Arena
formation-threshold calculations and the Prediction Arena comparison.
Repository: https://github.com/QuantLet/AlphaLuck.

No downloads or credentials are needed for the commands below. Use Python 3.11
or newer. Prediction Arena calculations use only the standard library. The
Alpha Arena calculations require numpy, pandas, scipy and pyarrow.
An environment version record is included in environment.json.

ALPHA ARENA
  cd alpha_arena
  python src/reproduce_threshold_results.py
  python -m unittest discover -s tests

The first command recalculates all 336 formation hours, both joint-stress
sweeps, the nine stresses at 24 hours, and all 18 threshold-timing scenarios.
It checks the reported results and writes data/derived/reproduction/.
Threshold inputs are derived estimates aligned for funding; their observation
offsets distinguish preceding from later snapshots. The raw organiser archive
is not included. Reproducing calculations from these inputs does not
independently validate the organiser's observations or the absence of margin
transfers. The earlier reconstruction code and additional checks are in the repository
under reproduction/. Raw organiser observations remain excluded.
Case B and worst observed values are sensitivity scenarios, not formal bounds.

PREDICTION ARENA
  cd prediction_arena
  python calculate_replication.py
  python calculate_twr.py
  python formation_sensitivity.py
  python -m unittest test_replication.py test_formation_sensitivity.py
  python independent_inputs/test_history.py

The results directory includes account-level values, both valuation-bound
specifications, and formation checks at 12, 24 and 48 hours. Terminal dollar
differences are primary. Time-weighted returns are secondary estimates based
on transaction marks at intermediate dates. They are not execution guarantees.
The last command verifies the earlier independent wallet-history audit.

Attribution to model decisions and wallet accounting are distinct. GPT remains
separate at all three formations because of an unmatched subsequent order.
Mystery starts in cash at every tested formation. Formation sensitivity shares
one closing date and is not an independent sample of experiments.

Prediction Arena sources and licences are documented in prediction_arena/
README.txt and the retained collection files. The Envio dataset is CC BY 4.0;
the extracted and transformed records retain its pinned source revision.
Explorer extracts, Binance price files and the derived order linkage are
included. Full operator decision logs are not asserted to be independently
verified. Source URLs are preserved in the input files and collection scripts.

Alpha Arena inputs derive from public Hyperliquid transactions and organiser
observations. The public source endpoints are documented in src/wallets.py,
src/organiser_hourly.py and the saved result metadata. No raw organiser
snapshot files or access credentials are distributed in this supplement.

Collection scripts use default TLS certificate verification. Machine-specific paths in funding metadata have been replaced with relative paths; original source URLs, response hashes and numerical observations are preserved.

ROBUSTNESS CHECKS
  cd robustness_checks
  python replay_checks.py
  python cash_formation_sensitivity.py
These commands need only the standard library. They reproduce omitted-arm,
model-block sign-flip, closing-cost and cash formation-time comparisons from
the included account inputs. See robustness_checks/README.txt for assumptions.

AUTHORS
Daniel Traian Pele, Diana Ioana Micu, Victor Rareș Curescu and
Miruna Mazurencu-Marinescu-Pele.
