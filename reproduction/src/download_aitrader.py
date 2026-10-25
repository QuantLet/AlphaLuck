"""Download the AI-Trader benchmark's position logs and price files.

AI-Trader (Fan et al., HKU; https://github.com/HKUDS/AI-Trader, MIT licence)
ran language-model agents on Nasdaq-100 stocks (hourly), SSE-50 stocks (daily
and hourly) and cryptocurrencies (daily) and committed every agent's position
log -- holdings and cash after each step -- with the price files the agents
traded on. The current repository head no longer carries data/; the files are
taken from commit COMMIT (11 March 2026), the parent of the commit that removed
them, so the URLs are immutable. The runs are historical replays with future
information filtered, not live trading.

Logged to PROVENANCE.csv through src/prov.py; cached, so a second run is a
no-op. Run: python src/download_aitrader.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import prov

REPO = "HKUDS/AI-Trader"
COMMIT = "c8b24a00b106279ec17f434421b8978e0b5e341d"
RAW = f"https://raw.githubusercontent.com/{REPO}/{COMMIT}"
TREE = f"https://api.github.com/repos/{REPO}/git/trees/{COMMIT}?recursive=1"

# Price files the position logs are valued with, and the code that states the
# execution and valuation rules (kept as reference text, never executed).
FIXED = [
    "LICENSE",
    "data/merged.jsonl",
    "data/A_stock/merged.jsonl",
    "data/A_stock/merged_hourly.jsonl",
    "data/crypto/crypto_merged.jsonl",
    "agent_tools/tool_trade.py",
    "agent_tools/tool_crypto_trade.py",
    "tools/price_tools.py",
    "tools/calculate_metrics.py",
    "configs/default_config.json",
    "configs/default_hour_config.json",
    "configs/astock_config.json",
    "configs/astock_hour_config.json",
    "configs/default_crypto_config.json",
]


def main() -> None:
    tree = prov.load(os.path.relpath(prov.fetch("aitrader/tree.json", TREE),
                                     prov.RAW))
    logs = sorted(x["path"] for x in tree["tree"]
                  if x["path"].startswith("data/agent_data")
                  and x["path"].endswith("position/position.jsonl"))
    if not logs:
        raise RuntimeError("No position logs in the pinned tree")
    for path in FIXED + logs:
        # .py and LICENSE are stored as .txt so nothing here is importable.
        name = path if path.endswith((".jsonl", ".json")) else path + ".txt"
        prov.fetch(f"aitrader/{name}", f"{RAW}/{path}", sleep=0.1)
    print(f"{len(logs)} position logs and {len(FIXED)} reference files "
          f"in data/raw/aitrader/ (commit {COMMIT[:7]})")


if __name__ == "__main__":
    main()
