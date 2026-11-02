"""Wallet registry. Every address carries the organiser source URL it came from.

No address is guessed. Two independent organiser sources:

S1 (crypto, Oct 2025): the archived Season-1 front-end bundle contains an
explicit, *labelled* map model-id -> walletAddress.
  src: https://web.archive.org/web/20251101120000id_/https://nof1.ai/_next/static/chunks/pages/_app-a5ae0a367d6e6067.js

S15 (tokenised equities, Nov-Dec 2025): the live bundle holds a flat address
array indexed by run_id -- the bundle's own resolver is
  f = run_id => addressArray[run_id]
and /api/since-inception-values maps run_id -> (competition_id, model_id).
  src: https://www.alphaarena.ai/_next/static/chunks/pages/_app-16433bc4d70bcfd6.js
  src: https://www.alphaarena.ai/api/since-inception-values
"""
from __future__ import annotations

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

S1_BUNDLE = (
    "https://web.archive.org/web/20251101120000id_/https://nof1.ai/"
    "_next/static/chunks/pages/_app-a5ae0a367d6e6067.js"
)
S15_BUNDLE = (
    "https://www.alphaarena.ai/_next/static/chunks/pages/_app-16433bc4d70bcfd6.js"
)
S15_RUNS = "https://www.alphaarena.ai/api/since-inception-values"

# Season 1 -- labelled directly in the archived bundle.
SEASON1 = {
    "gpt-5": "0x67293d914eafb26878534571add81f6bd2d9fe06",
    "claude-sonnet-4-5": "0x59fa085d106541a834017b97060bcbbb0aa82869",
    "gemini-2.5-pro": "0x1b7a7d099a670256207a30dd0ae13d35f278010f",
    "grok-4": "0x56d652e62998251b56c8398fb11fcfe464c08f84",
    "deepseek-chat-v3.1": "0xc20ac4dc4188660cbf555448af52694ca62b0734",
    "qwen3-max": "0x7a8fd8bba33e37361ca6b0cb4518a44681bad2f3",
}

# Season 1 window, from the organiser's public announcement (18 Oct - 3 Nov 2025).
# Observed first fill is 2025-10-17T22:03Z, so the window is opened slightly early.
S1_START_MS = 1760738400000  # 2025-10-17T22:00:00Z
S1_END_MS = 1762214400000    # 2025-11-04T00:00:00Z

# Season 1.5 window: all 32 runs report inception 2025-11-19T21:0xZ.
S15_START_MS = 1763586000000  # 2025-11-19T21:00:00Z
S15_END_MS = 1765843200000    # 2025-12-16T00:00:00Z

# Organiser-stated official season ends. S1.5 is quoted verbatim on
# www.alphaarena.ai: "The official competition has ended as of December 3rd,
# 2025 at 5:00 PM EST" (= 2025-12-03T22:00Z). For S1 the organiser's own posts
# and press coverage give 3 November 2025; no clock time was published, so the
# end of that UTC day is used and the choice is reported.
S1_OFFICIAL_END_MS = 1762214399000   # 2025-11-03T23:59:59Z
S15_OFFICIAL_END_MS = 1764799200000  # 2025-12-03T22:00:00Z
OFFICIAL_END = {"S1": S1_OFFICIAL_END_MS, "S15": S15_OFFICIAL_END_MS}
SEASON_START = {"S1": S1_START_MS, "S15": S15_START_MS}


def _norm(model_id: str) -> str:
    """'deepseek/deepseek-chat-v3.1' -> 'deepseek-chat-v3.1'."""
    return model_id.split("/")[-1]


def _from_csv() -> list[dict] | None:
    """Fall back to the committed wallets.csv when the raw payloads are absent.

    This repository does not ship the organiser's API responses (see DATA.md),
    and the live bundle URL embeds a deployment hash that will eventually 404.
    wallets.csv carries the resolved mapping and its source for every address,
    so the analysis still runs from a clean clone even if the mapping can no
    longer be re-derived from the bundle.
    """
    path = os.path.join(ROOT, "wallets.csv")
    if not os.path.exists(path):
        return None
    import csv

    rows = []
    with open(path) as fh:
        for r in csv.DictReader(fh):
            s1 = r["season"] == "S1"
            rows.append({
                "season": r["season"],
                "season_label": r["season_label"],
                "competition_id": int(r["competition_id"]),
                "run_id": int(float(r["run_id"])) if r["run_id"] else None,
                "model": r["model"],
                "address": r["address"],
                "start_ms": S1_START_MS if s1 else S15_START_MS,
                "end_ms": S1_END_MS if s1 else S15_END_MS,
                "source_url": r["source_url"],
                "source_kind": r["source_kind"],
            })
    return rows or None


def registry() -> list[dict]:
    """One row per (season, competition, model) with its address and source."""
    arr_path = os.path.join(ROOT, "data", "raw", "nof1", "wallet_array.json")
    runs_path = os.path.join(ROOT, "data", "raw", "nof1",
                             "since-inception-values.json")
    if not (os.path.exists(arr_path) and os.path.exists(runs_path)):
        fallback = _from_csv()
        if fallback is not None:
            return fallback
        raise SystemExit(
            "No organiser payloads and no wallets.csv. Run "
            "`python src/download_organiser.py` first."
        )

    rows = []
    for model, addr in SEASON1.items():
        rows.append(
            {
                "season": "S1",
                "season_label": "Alpha Arena Season 1 (crypto perps)",
                "competition_id": 1,
                "run_id": None,
                "model": model,
                "address": addr,
                "start_ms": S1_START_MS,
                "end_ms": S1_END_MS,
                "source_url": S1_BUNDLE,
                "source_kind": "organiser bundle, explicit labelled map (Wayback)",
            }
        )

    with open(arr_path) as fh:
        arr = json.load(fh)["address_array_indexed_by_run_id"]
    with open(runs_path) as fh:
        runs = json.load(fh)["sinceInceptionValues"]

    for r in sorted(runs, key=lambda r: (r["competition_id"], r["run_id"])):
        rid = r["run_id"]
        rows.append(
            {
                "season": "S15",
                "season_label": "Alpha Arena Season 1.5 (tokenised US equities)",
                "competition_id": r["competition_id"],
                "run_id": rid,
                "model": _norm(r["model_id"]),
                "address": arr[rid],
                "start_ms": S15_START_MS,
                "end_ms": S15_END_MS,
                "source_url": f"{S15_BUNDLE} + {S15_RUNS}",
                "source_kind": "organiser bundle address[run_id] + organiser run metadata",
            }
        )
    return rows


def tag(row: dict) -> str:
    """Stable per-wallet filename tag."""
    if row["season"] == "S1":
        return f"S1__{row['model']}"
    return f"S15__c{row['competition_id']}__{row['model']}"


if __name__ == "__main__":
    for r in registry():
        print(tag(r), r["address"])
