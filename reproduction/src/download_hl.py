"""Phase 2 downloader: Hyperliquid public info endpoint, read-only.

Endpoint and limits confirmed against the current docs
(https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint):
  userFillsByTime        startTime/endTime ms inclusive; <=2000 rows per response,
                         only the 10000 most recent fills are retained.
  userFunding            time-ranged ledger; <=500 rows per response.
  userNonFundingLedgerUpdates deposits/withdrawals/transfers; <=500 rows per response.
  clearinghouseState     current snapshot.
  candleSnapshot         <=5000 candles per response.

Everything is paginated by advancing startTime past the last row seen, cached on
disk by prov.fetch, and logged to PROVENANCE.csv.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import prov
import wallets

INFO = "https://api.hyperliquid.xyz/info"
PAGE_FILLS = 2000
PAGE_LEDGER = 500
PAGE_CANDLES = 5000


def _paginate(kind: str, tag: str, addr: str, start: int, end: int, page: int) -> list:
    """Walk a time-ranged request type until the venue stops returning full pages."""
    out, cursor, part = [], start, 0
    seen = set()
    while True:
        payload = {"type": kind, "user": addr, "startTime": cursor, "endTime": end}
        path = prov.fetch(f"hl/{kind}/{tag}.p{part:03d}.json", INFO, payload)
        with open(path) as fh:
            rows = json.load(fh)
        if not rows:
            break
        fresh = []
        for r in rows:
            # de-dup across page boundaries (startTime is inclusive)
            key = json.dumps(r, sort_keys=True)
            if key not in seen:
                seen.add(key)
                fresh.append(r)
        out.extend(fresh)
        times = [r["time"] for r in rows]
        if len(rows) < page or max(times) >= end:
            break
        cursor = max(times)  # advance; dedup handles the inclusive overlap
        part += 1
        if part > 40:  # safety stop
            print(f"    !! {kind} {tag}: pagination guard hit", flush=True)
            break
    return out


def main() -> None:
    reg = wallets.registry()
    coins: dict[str, tuple[int, int]] = {}

    for i, row in enumerate(reg, 1):
        tag = wallets.tag(row)
        addr, start, end = row["address"], row["start_ms"], row["end_ms"]
        print(f"[{i:>2}/{len(reg)}] {tag}", flush=True)

        fills = _paginate("userFillsByTime", tag, addr, start, end, PAGE_FILLS)
        funding = _paginate("userFunding", tag, addr, start, end, PAGE_LEDGER)
        ledger = _paginate(
            "userNonFundingLedgerUpdates", tag, addr, start, end, PAGE_LEDGER
        )
        prov.fetch(
            f"hl/clearinghouseState/{tag}.json",
            INFO,
            {"type": "clearinghouseState", "user": addr},
        )
        print(
            f"    fills={len(fills)} funding={len(funding)} ledger={len(ledger)}",
            flush=True,
        )
        for f in fills:
            c = f["coin"]
            lo, hi = coins.get(c, (start, end))
            coins[c] = (min(lo, start), max(hi, end))

    # 5-minute candles for every coin actually traded, over the union of windows.
    print(f"\ncandles for {len(coins)} coins", flush=True)
    for c, (lo, hi) in sorted(coins.items()):
        part, cursor = 0, lo
        while cursor < hi:
            payload = {
                "type": "candleSnapshot",
                "req": {
                    "coin": c,
                    "interval": "5m",
                    "startTime": cursor,
                    "endTime": hi,
                },
            }
            safe = c.replace(":", "_").replace("@", "at")
            path = prov.fetch(f"hl/candles5m/{safe}.p{part:03d}.json", INFO, payload)
            with open(path) as fh:
                rows = json.load(fh)
            print(f"  {c} part{part} rows={len(rows)}", flush=True)
            if not rows:
                break
            if len(rows) < PAGE_CANDLES:
                break
            cursor = max(r["t"] for r in rows) + 1
            part += 1

    with open(os.path.join(prov.ROOT, "data", "derived", "coins_traded.json"), "w") as fh:
        json.dump(sorted(coins), fh, indent=1)
    print("\ncoins:", sorted(coins))


if __name__ == "__main__":
    main()
