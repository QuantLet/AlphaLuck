Prediction Arena independent wallet audit — 2026-11-01

Read Raport_istoric_independent.txt first.

Data attribution: Envio / moose-code, Polymarket On-Chain Complete v1 Dataset, CC BY 4.0, https://huggingface.co/datasets/moose-code/polymarket-onchain-v1 . Extracted and transformed for the five listed wallets. Explorer data: PolygonScan and Blockscout; original CSVs preserved.

Re-run saved-data analysis with Python 3 (standard library):
  python analyze_history.py
  python reconcile_cash.py
  python reconcile_positions.py
  python assess_replication.py
  python test_history.py
  python build_delivery.py

Re-fetch archive: Python 3 plus pyarrow; run extract_archive.py, then extract_conditions.py after analysis has identified redemption conditions. The first scanner resumes completed row groups. Its pinned source revision is in range_reader.py. The original collection used a locally intercepted HTTPS connection. Public collectors now use normal certificate verification; archived responses are unchanged.

Browser export: open each wallet on Blockscout; export token transfers and transactions from 2020-01-01 to retrieval date. On PolygonScan open token transfers, transactions and NFT transfers; select 100 rows and download every page using Download Page Data. Export names, pages and coverage are recorded in polygonscan/export_manifest.json and blockscout/export_manifest.json. Quick token exports truncate some amounts; do not use them alone for a precise balance. Exact details for four missing cash transactions were read separately and saved.

The operator_inputs directory contains derived order records and the prior benchmark diagnostic. The complete decision/event source archive remains in 2026 AlphaLuck/archives/AlphaLuck_PredictionArena_audit_20261101.zip; this new archive does not replace it.

No point returns are produced. Wealth bounds use equal external cash flows, stablecoin parity, common prices for common tokens, and pre-endpoint settlement evidence. POL inventory and its USD valuation are outside those bounds.

Public release: v2.1.0, 2 November 2026. The independent-history report records an earlier audit stage; the current trading-versus-holding results are in prediction_arena/results and the enclosing README.
