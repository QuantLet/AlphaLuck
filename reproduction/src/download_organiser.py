"""Re-download the organiser's own payloads, which this repository does not ship.

Nof1 publishes no licence or terms of use for alphaarena.ai or its API, so the
raw responses are not redistributed here (see DATA.md). Everything this script
fetches is public and unauthenticated; it is cached by src/prov.py, so a second
run is a no-op, and every file is logged to PROVENANCE.csv with its SHA-256 so
a re-downloaded copy can be checked byte-for-byte against the one the published
results were computed from.

What it fetches:
  live Season-1.5 API      www.alphaarena.ai/api/{leaderboard, account-totals,
                           since-inception-values, trades, conversations,
                           crypto-prices}
  live front-end bundle    the address array that maps run_id -> wallet
  live home page           the official-end statement and the winner's figure
  Season-1 API             the same endpoints via the Wayback Machine capture
                           of 2025-11-12, the last one taken; nof1.ai no longer
                           serves Season 1
  Season-1 bundle          the archived bundle holding the labelled Season-1
                           model -> wallet map
  TradeRank summary        the comparison arena's open dataset

Fragility worth knowing: the live bundle URL embeds a deployment hash. If Nof1
redeploys, that URL 404s and the array must be recovered from a new bundle.
The analysis does not depend on it -- wallets.csv carries the resolved mapping
and its source for every address -- but re-deriving the mapping from scratch
does.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import prov

LIVE = "https://www.alphaarena.ai"
BUNDLE = f"{LIVE}/_next/static/chunks/pages/_app-16433bc4d70bcfd6.js"
WAYBACK = "https://web.archive.org/web/20251112224724id_/https://nof1.ai/api"
S1_BUNDLE = (
    "https://web.archive.org/web/20251101120000id_/https://nof1.ai/"
    "_next/static/chunks/pages/_app-a5ae0a367d6e6067.js"
)
ENDPOINTS = ["leaderboard", "account-totals", "since-inception-values",
             "trades", "conversations", "crypto-prices"]


def main() -> None:
    ok, failed = 0, []

    for ep in ENDPOINTS:
        try:
            prov.fetch(f"nof1/{ep}.json", f"{LIVE}/api/{ep}")
            ok += 1
        except Exception as exc:
            failed.append((f"live /api/{ep}", repr(exc)[:120]))

    for ep in ENDPOINTS:
        try:
            prov.fetch(f"nof1_s1/{ep}.json", f"{WAYBACK}/{ep}")
            ok += 1
        except Exception as exc:
            failed.append((f"Season-1 /api/{ep} (Wayback)", repr(exc)[:120]))

    for name, url in [
        ("nof1_app_bundle.js", BUNDLE),
        ("nof1_s1_bundle.js", S1_BUNDLE),
        ("alphaarena_home.html", f"{LIVE}/"),
        ("traderank/facts.json", "https://www.traderank.ai/data/traderank-facts.json"),
    ]:
        try:
            prov.fetch(name, url)
            ok += 1
        except Exception as exc:
            failed.append((name, repr(exc)[:120]))

    print(f"organiser payloads: {ok} present or fetched, {len(failed)} failed")
    for what, why in failed:
        print(f"  FAILED {what}: {why}")
    if failed:
        print(
            "\nIf the live bundle 404s, Nof1 has redeployed and the URL hash has\n"
            "changed. wallets.csv already carries the resolved address mapping and\n"
            "its source for every address, so the analysis still runs; only\n"
            "re-deriving the mapping from the bundle needs the new URL."
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
