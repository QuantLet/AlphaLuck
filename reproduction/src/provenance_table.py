"""What is documented, what is inferred, and what is not known at all.

The referee's point is that common prompt text does not establish identical
operating conditions, and that the paper leans on treatment definitions whose
evidence is partly the behaviour they are used to explain. The honest response
is not an argument but a table: each element of the design, the status of the
evidence for it, and the source.

Three statuses, and they are kept strictly apart:

    documented     stated by the organiser in material dated inside the
                   season, or recorded on-chain, where the record is the fact
    retrospective  evidence that exists only after the season closed -- the
                   archived prompts, the interface labels as they stand now --
                   and which therefore cannot establish what was true during it
    unknown        not established by the retrieved evidence

Anything resting on behaviour alone is marked retrospective, never documented,
because behaviour is what the arm definitions are used to explain and cannot
also serve as independent evidence for them.

Writes data/derived/i5_provenance.csv and the appendix table.
"""
from __future__ import annotations

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import prov

DER = os.path.join(prov.ROOT, "data", "derived")

ROWS = [
    # (element, status, what is known, source)
    ("Account addresses",
     "documented",
     "The 38 analysed account addresses are recovered from organiser "
     "bundles and run metadata",
     "alphaarena.ai bundle; PROVENANCE.csv"),
    ("Fills, funding, ledger",
     "documented",
     "Public exchange fills, funding and ledger records; equity is compared "
     "with 38 selected organiser snapshots and, in Season 1.5, with the "
     "organiser's hourly snapshots",
     "Hyperliquid info endpoint"),
    ("Initial capital",
     "documented",
     "Analytical capital is normalised to USD 10,000; ledger records include "
     "late initial transfers and Season 1 tips, excluded from trading P&L",
     "On-chain ledger"),
    ("Season start and end",
     "documented",
     "Organiser close dates and recorded inception anchor the window; "
     "Season 1 opens early to include its first fills and closes at UTC day-end",
     "Organiser site and metadata; exchange records"),
    ("Number of arms and their membership",
     "documented",
     "Four arms, eight models each, from the organiser's own API",
     "alphaarena.ai API"),
    ("Arm 1 and 2 rules",
     "retrospective",
     "Named in the interface as New Baseline and Monk Mode; the only prompt "
     "texts available are archived copies dated after the close",
     "Interface labels; archived prompts"),
    ("Arm 3 and 4 rules",
     "retrospective",
     "Labelled Situational Awareness and Max Leverage; archived prompts "
     "suggest leaderboard visibility and leverage instructions but cannot "
     "verify in-season rules",
     "Interface labels; archived prompts"),
    ("Prompt text during the season",
     "unknown",
     "No prompt captured inside the window; the archived conversations all "
     "postdate the close, so in-season and post-season prompts cannot be "
     "compared",
     "--"),
    ("Model versions and checkpoints",
     "unknown",
     "Only the organiser's display names are published; neither the API "
     "version nor the serving checkpoint of any model is stated",
     "--"),
    ("Inference settings",
     "unknown",
     "In-season temperature, sampling parameters, context handling and "
     "system prompts are not established by the retrieved evidence",
     "--"),
    ("Decision frequency",
     "unknown",
     "The invocation cadence is not established by the retrieved evidence; "
     "fill times do not identify decision frequency",
     "--"),
    ("Tool failures, retries, timeouts",
     "unknown",
     "Not published and not visible on-chain; an unfilled intention leaves "
     "no record",
     "--"),
    ("Execution path",
     "unknown",
     "Order type, routing and any manual intervention are not published; "
     "only the resulting fills are observable",
     "--"),
]


def main() -> None:
    d = pd.DataFrame(ROWS, columns=["Element", "Status", "What is known",
                                    "Source"])
    d.to_csv(os.path.join(DER, "i5_provenance.csv"), index=False)
    n = d["Status"].value_counts()
    print("=== provenance of the design ===\n")
    for st in ("documented", "retrospective", "unknown"):
        print(f"  {st:<15} {n.get(st, 0):>2}")
    print(f"\n  {len(d)} elements in total")
    print("\nEvery element resting on behaviour alone is marked "
          "retrospective, not documented:\nbehaviour is what the arm "
          "definitions are used to explain.")
    print("\nwrote i5_provenance.csv")


if __name__ == "__main__":
    main()
