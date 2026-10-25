"""Candles for the traded coins, plus evidence of what the venue will not serve.

Measured against api.hyperliquid.xyz on 2026-10-08: candleSnapshot retention is
interval-dependent. 5m candles stop being served beyond roughly two weeks and 1h
beyond roughly six months, so for the arena windows (Oct-Dec 2025, i.e. 300-360
days before the audit) only the 4h and 1d intervals return rows. The probe below is
written to data/raw/hl/candle_probe/ so the limitation is documented, not assumed.
"""
from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import prov
import wallets

INFO = "https://api.hyperliquid.xyz/info"


def probe() -> None:
    """Record, for each interval, whether the season windows are served at all."""
    out = []
    for label, start in [
        ("S1_2025-10-18", wallets.S1_START_MS),
        ("S15_2025-11-19", wallets.S15_START_MS),
        ("recent_7d", int(time.time() * 1000) - 7 * 86400000),
    ]:
        for iv in ["5m", "15m", "1h", "4h", "1d"]:
            payload = {
                "type": "candleSnapshot",
                "req": {
                    "coin": "BTC",
                    "interval": iv,
                    "startTime": start,
                    "endTime": start + 5 * 86400000,
                },
            }
            p = prov.fetch(f"hl/candle_probe/BTC_{iv}_{label}.json", INFO, payload)
            with open(p) as fh:
                rows = json.load(fh)
            out.append({"window": label, "interval": iv, "rows": len(rows)})
            print(f"  {label:<16} {iv:<4} rows={len(rows)}")
    with open(os.path.join(prov.ROOT, "data", "derived", "candle_probe.json"), "w") as fh:
        json.dump(out, fh, indent=1)


def main() -> None:
    print("candle retention probe:")
    probe()

    with open(os.path.join(prov.ROOT, "data", "derived", "coins_traded.json")) as fh:
        coins = json.load(fh)

    lo = min(wallets.S1_START_MS, wallets.S15_START_MS)
    hi = max(wallets.S1_END_MS, wallets.S15_END_MS)
    for iv in ["4h", "1d"]:
      print(f"\n{iv} candles, {len(coins)} coins")
      for c in coins:
        safe = c.replace(":", "_").replace("@", "at")
        payload = {
            "type": "candleSnapshot",
            "req": {"coin": c, "interval": iv, "startTime": lo, "endTime": hi},
        }
        p = prov.fetch(f"hl/candles{iv}/{safe}.json", INFO, payload)
        with open(p) as fh:
            rows = json.load(fh)
        print(f"  {c:<12} rows={len(rows)}")


if __name__ == "__main__":
    main()
