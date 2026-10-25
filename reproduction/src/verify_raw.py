"""Check data/raw/ against the SHA-256 values recorded in PROVENANCE.csv.

Exit status 1 if any present file differs, or if a required organiser file
is missing. Licensed or optional sources (EODHD bars, pilot archives) are
reported as missing but do not fail the check.
"""
from __future__ import annotations

import csv
import hashlib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OPTIONAL = ("data/raw/eodhd/", "archives/")


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ok, bad, missing, optional = 0, [], [], []
    with open(os.path.join(ROOT, "PROVENANCE.csv")) as fh:
        for row in csv.DictReader(fh):
            rel, want = row["path"], row["sha256"]
            path = os.path.join(ROOT, rel)
            if not want or os.path.isdir(path):
                continue
            if not os.path.exists(path):
                (optional if rel.startswith(OPTIONAL) else missing).append(rel)
            elif sha256(path) != want:
                bad.append(rel)
            else:
                ok += 1
    print(f"verify-raw: {ok} match, {len(bad)} differ, {len(missing)} missing, "
          f"{len(optional)} optional missing")
    for rel in bad:
        print(f"  DIFFERS {rel}")
    for rel in missing:
        print(f"  MISSING {rel}")
    return 1 if bad or missing else 0


if __name__ == "__main__":
    sys.exit(main())
