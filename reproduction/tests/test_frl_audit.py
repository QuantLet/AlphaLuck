"""Consistency test for the letter's audit outputs.

Checks that paper/frl/benchmark_cost_sensitivity.json, written by
`make frl-audit`, agrees with the macros the letter quotes from
paper/numbers.tex, and that the stated exclusions are carried in the output.
The benchmark excludes post-freeze funding and terminal liquidation costs; the
cost sensitivity is a terminal adjustment only and is not a margin test.
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRL = os.path.join(ROOT, "paper", "frl")


def macro(name: str) -> str:
    text = open(os.path.join(ROOT, "paper", "numbers.tex")).read()
    text += open(os.path.join(FRL, "audit_addition_numbers.tex")).read()
    m = re.search(r"\\newcommand\{\\%s\}\{(.*)\}" % name, text)
    if not m:
        raise KeyError(name)
    return m.group(1).replace(r"\ensuremath{-}", "-")


def main() -> int:
    errors = []
    cost = json.load(open(os.path.join(FRL, "benchmark_cost_sensitivity.json")))
    base = next(s for s in cost["scenarios"] if s["debit_pp"] == 0)
    checks = [
        ("alExAnteNetPct", f"{base['frozen_return_pct']:.1f}"),
        ("alExAnteGapPp", f"{base['advantage_pp']:.1f}"),
        ("alExAnteBeats", str(base["accounts_ahead"])),
    ]
    for name, got in checks:
        want = macro(name)
        if got != want:
            errors.append(f"{name}: numbers.tex {want}, cost sensitivity {got}")
    counts = [s["accounts_ahead"] for s in cost["scenarios"]]
    # Prose and appendix use generated macros for terminal sensitivities.
    ten = next(s for s in cost["scenarios"] if s["debit_pp"] == 10)
    for name, expected in (("alCostGapPct", f"{base['advantage_pp']:.2f}"),
                           ("alCostTenAhead", str(ten['accounts_ahead']))):
        if macro(name) != expected:
            errors.append(f"{name}: generated audit macro differs from JSON")
    funding = json.load(open(os.path.join(ROOT, "data", "derived",
                                         "hourly_funding_benchmark_sensitivity.json")))
    row = next(r for r in funding['results'] if r['freeze_h'] == 24)
    for name, expected in (("alFundingHoldPct", f"{row['hold']/3200:.2f}"),
                           ("alFundingRealPct", f"{row['actual']/3200:.2f}"),
                           ("alFundingAhead", str(row['better']))):
        if macro(name) != expected:
            errors.append(f"{name}: generated funding macro differs from JSON")
    if counts != sorted(counts, reverse=True):
        errors.append(f"accounts ahead not monotone in the debit: {counts}")
    if "no new margin test" not in cost.get("limitation", ""):
        errors.append("cost sensitivity lost its stated limitation")
    audit = json.load(open(os.path.join(FRL, "referee_audit.json")))
    for key in ("leave_one_arm", "leave_one_return_day", "hac1_aggregate",
                "hac1_equal_daily", "price_ages", "daily_mark_intervals"):
        if key not in audit:
            errors.append(f"referee_audit.json lacks {key}")
    if not os.path.exists(os.path.join(FRL, "audit_reconciliation.tex")):
        errors.append("audit_reconciliation.tex missing")
    for e in errors:
        print("FAIL", e)
    if not errors:
        print("frl audit outputs consistent with numbers.tex "
              f"(advantage USD {cost['advantage_dollars']:,.2f}; "
              f"ahead at debits 0/1/5/10/20%: {counts})")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
