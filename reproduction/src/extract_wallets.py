"""Re-derive the S1.5 wallet array from the committed organiser bundle.

The live bundle stores the 40 Season-1.5 addresses as a flat array and resolves
a run's wallet with its own helper, minified to:

    f = e => { let t = String(e),
                   n = t.match(/(?:run_|sub_)?(\\d{1,2})/),
                   r = n ? Number.parseInt(n[1], 10) : Number.parseInt(t, 10);
               if (!Number.isNaN(r) && r >= 0 && r < a.length) return a[r] }

i.e. walletAddress = a[run_id]. This script extracts `a` in source order so the
mapping is reproducible from the raw file rather than pasted in by hand.
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import prov

BUNDLE = os.path.join(prov.RAW, "nof1_app_bundle.js")
OUT = os.path.join(prov.RAW, "nof1", "wallet_array.json")
PAT = re.compile(r'a=\[("0x[a-fA-F0-9]{40}"(?:,"0x[a-fA-F0-9]{40}")*)\]')


def main() -> None:
    src = open(BUNDLE).read()
    m = PAT.search(src)
    if not m:
        raise SystemExit("address array not found in bundle")
    arr = json.loads("[" + m.group(1) + "]")
    if len(arr) != len(set(arr)):
        raise SystemExit("duplicate addresses in array")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as fh:
        json.dump({"address_array_indexed_by_run_id": arr}, fh, indent=1)
    print(f"extracted {len(arr)} addresses -> {os.path.relpath(OUT, prov.ROOT)}")


if __name__ == "__main__":
    main()
