Prediction Arena trading versus holding — 2026-11-02

Read Raport_replicare.txt. Primary outcome: terminal wealth difference with identical external funding. Time-weighted returns use transaction-price valuations at formation, immediately before each wallet's single later deposit, and at the endpoint. Modified Dietz is a secondary comparison. These are valuation proxies, not executable liquidation prices. Assume USDC = USDC.e = USD 1; POL investment return is excluded, while wallet-paid gas is charged as an expense at historical POL/USDC prices.

Recalculate saved-data results (Python 3, standard library):
  python calculate_replication.py
  python calculate_twr.py
  python formation_sensitivity.py
  python -m unittest test_replication.py test_formation_sensitivity.py
  python build_report.py
Re-run earlier ledger checks with: python independent_inputs/test_history.py

Re-fetch public sources (Python 3 and pyarrow):
  python collect_valuations.py
  python collect_prices.py
  python collect_funding_prices.py
Collectors resume saved row groups. The independent archive revision is pinned in independent_inputs/range_reader.py. The original collection used a locally intercepted HTTPS connection. Public collectors now use normal certificate verification; the archived responses and numerical results are unchanged. Polymarket price-history DNS lookup failed and the Coinbase endpoint returned HTTP 403. Actual price data therefore came from independently indexed on-chain fills and the Binance public archive. initial_access.json preserves those access attempts. The unused POL/USDT probe file is retained as a probe only; all gas calculations use POL/USDC.

Source attribution: Envio / moose-code, Polymarket On-Chain Complete v1, CC BY 4.0, https://huggingface.co/datasets/moose-code/polymarket-onchain-v1 ; extracted and transformed. Binance public spot data: https://github.com/binance/binance-public-data . Earlier explorer inputs: PolygonScan and Blockscout. Original files and source URLs are retained. Full underlying operator decision logs remain in the earlier Prediction Arena audit archive; derived order/linkage records needed here are included in independent_inputs.

The scripts implement the period and assumptions stated in the report. Bounds allow each unknown binary outcome price independently in [0,1], so they may be wider than bounds imposing cross-outcome constraints. Historical redemption evidence, rather than a future state snapshot alone, gates contractual payout valuations. Zero-payout redemption events prove resolution but are not wallet income. Gas is charged only to its payer once. Holding retains settlement claims without forced redemption and has no post-formation trading gas. All comparisons are descriptive; no statistical significance or universal policy ranking is asserted.

Revision: formation_sensitivity.py adds 12/24/48-hour comparisons from the reconciled cash and position ledgers. The endpoint remains fixed. Results are in results/formation_sensitivity.json and .csv.

Public release: v2.1.0, 2 November 2026. The independent-history report records an earlier audit stage; the current trading-versus-holding results are in prediction_arena/results and the enclosing README.
