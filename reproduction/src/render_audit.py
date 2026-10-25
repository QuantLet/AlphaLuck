"""Splice the generated tables into the narrative to produce AUDIT.md.

Keeps every number in AUDIT.md machine-generated, so nothing is transcribed by
hand and `make all` regenerates the report end to end.
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import prov

ROOT = prov.ROOT
TABLES = os.path.join(ROOT, "data", "derived", "tables.md")
FOLLOWUP = os.path.join(ROOT, "data", "derived", "tables_followup.md")
CHECKS = os.path.join(ROOT, "data", "derived", "tables_checks.md")
EXTRA = os.path.join(ROOT, "data", "derived", "tables_extra.md")


def sections(text: str) -> dict[str, str]:
    out, key, buf = {}, None, []
    for line in text.splitlines():
        if line.startswith("### "):
            if key:
                out[key] = "\n".join(buf).strip()
            key, buf = line[4:].strip(), []
        else:
            buf.append(line)
    if key:
        out[key] = "\n".join(buf).strip()
    return out


def main() -> None:
    narrative = open(os.path.join(ROOT, "audit_narrative.md")).read()
    raw = open(TABLES).read()
    sec = sections(raw)

    inventory = sec["Inventory"]

    order = [
        "T1 Descriptive audit, per arena-season and model (official window)",
        "T2a Season 1 similarity, all 15 pairs",
        "T2b Season 1.5 similarity: different models vs the same model in another competition",
        "T3 Per-model precision (daily returns, official window)",
        "T4 Pairwise precision and required season length (single wallets)",
        "T5 Season 1.5 on the organiser's ranking unit (equal-weight over 4 competitions)",
        "T5b Required season length on that aggregate",
        "T6 Same model, four independent competitions: final return %",
    ]
    blocks = [f"### {k}\n\n{sec[k]}" for k in order]
    tables = "\n\n".join(blocks)

    recon_key = "T7 Reconciliation, all 38 wallets"
    tables += (
        "\n\n### T7 Reconciliation of all 38 wallets against the organiser's "
        "published equity\n\n"
        "`pub_equity` is the organiser's own `dollar_equity` at its last "
        "timestamp inside the season window; `recon_equity` is rebuilt from "
        "on-chain fills, funding and transfers; `tips` are unsolicited public "
        "USDC transfers into the wallet, added before comparison.\n\n"
        + sec[recon_key]
    )

    out = narrative.replace("{{INVENTORY}}", inventory).replace("{{TABLES}}", tables)

    # follow-up items {{F1}}..{{F12}} and checks {{C1}}..{{C4}},
    # keyed by the leading token of each header
    fup = {**sections(open(FOLLOWUP).read()), **sections(open(CHECKS).read()),
           **sections(open(EXTRA).read())}
    for key, body in fup.items():
        tag = key.split()[0]
        out = out.replace(f"{{{{{tag}}}}}", f"**{key}**\n\n{body}")

    left = re.findall(r"\{\{[A-Za-z0-9_]+\}\}", out)
    if left:
        raise SystemExit(f"unfilled placeholders: {sorted(set(left))}")
    with open(os.path.join(ROOT, "AUDIT.md"), "w") as fh:
        fh.write(out)
    print(f"wrote AUDIT.md ({len(out):,} chars)")


if __name__ == "__main__":
    main()
