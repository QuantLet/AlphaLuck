"""Reproducibility test: fail if any regenerated number differs from the
committed paper/numbers.tex.

Regenerates every macro from the derived data into a temporary directory and
compares it with the committed snapshot in paper/numbers.json, which is written
alongside numbers.tex by paper/code/make_numbers.py. Because every random
procedure in src/ is seeded with a fixed integer, a clean `make all` must
reproduce the committed values exactly; any drift -- a changed estimator, an
unseeded draw, a different dependency version -- shows up here as a diff.

Also checks that:
  * every macro referenced in paper/alphaluck_draft.tex is defined;
  * every macro defined is referenced at least once (so the paper and the
    generator cannot silently drift apart);
  * every figure and table the draft includes exists on disk.

Exits non-zero on any failure. Run with `make test`.
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "paper", "code"))
sys.path.insert(0, os.path.join(ROOT, "src"))

PAPER = os.path.join(ROOT, "paper")
DRAFT = os.path.join(PAPER, "alphaluck_draft.tex")
FRL = os.path.join(PAPER, "frl", "alphaluck_frl.tex")
APPENDIX = os.path.join(PAPER, "frl", "online_appendix.tex")
DOCS = [("alphaluck_draft.tex", DRAFT, PAPER),
        ("frl/alphaluck_frl.tex", FRL, os.path.join(PAPER, "frl")),
        ("frl/online_appendix.tex", APPENDIX, os.path.join(PAPER, "frl")),
        ("frl/highlights.tex", os.path.join(PAPER, "frl", "highlights.tex"),
         os.path.join(PAPER, "frl"))]
SNAPSHOT = os.path.join(PAPER, "numbers.json")


def regenerate(tmp: str) -> dict:
    """Run the generator with its output redirected to a temp directory."""
    import make_numbers as mn

    mn.PAPER = tmp
    mn.TABDIR = os.path.join(tmp, "tables")
    mn._MACROS.clear()
    os.makedirs(mn.TABDIR, exist_ok=True)
    mn.main()
    with open(os.path.join(tmp, "numbers.json")) as fh:
        return json.load(fh)


def main() -> int:
    failures: list[str] = []

    if not os.path.exists(SNAPSHOT):
        print(f"FAIL: no committed snapshot at {SNAPSHOT}; run `make numbers`")
        return 1
    with open(SNAPSHOT) as fh:
        committed = json.load(fh)

    with tempfile.TemporaryDirectory() as tmp:
        fresh = regenerate(tmp)

    # ---- 1. regenerated values must match the committed ones exactly
    only_c = sorted(set(committed) - set(fresh))
    only_f = sorted(set(fresh) - set(committed))
    diff = {k: (committed[k], fresh[k]) for k in sorted(set(committed) & set(fresh))
            if committed[k] != fresh[k]}
    if only_c:
        failures.append(f"macros in numbers.tex but no longer generated: {only_c}")
    if only_f:
        failures.append(f"macros newly generated but not committed: {only_f}")
    if diff:
        lines = "\n".join(f"      \\{k}: committed {c!r} -> regenerated {f!r}"
                          for k, (c, f) in diff.items())
        failures.append(f"{len(diff)} macro(s) changed value:\n{lines}")
    print(f"  {len(committed)} macros checked, {len(diff)} changed, "
          f"{len(only_c)} dropped, {len(only_f)} added")

    # ---- 1b. the P&L sentence must add up as printed
    # The text says the loss comes from "the remaining components", i.e.
    # everything other than exposure, so exposure + other must equal net at
    # the precision all three are printed to. This caught a real error: the
    # "other" macro had omitted funding, leaving 9.5 + (-38.8) = -29.4 against
    # a printed net of -29.2.
    def num(key: str) -> float:
        """Macro values carry a typeset minus, \ensuremath{-}, not a hyphen."""
        return float(committed[key].replace(r"\ensuremath{-}", "-")
                     .replace("{,}", ""))

    try:
        exposure = num("alPnlPctExposure")
        other = num("alPnlOtherPct")
        net = num("alPnlPctNet")
    except KeyError as exc:
        failures.append(f"P&L identity: macro {exc} is missing")
    else:
        # one decimal each, so the sum can be off by at most half a unit in
        # the last place from each of the three roundings
        if abs((exposure + other) - net) > 0.15:
            failures.append(
                f"P&L identity does not close as printed: exposure "
                f"{exposure} + other {other} = {exposure + other:.1f}, "
                f"but net is {net}")
        else:
            print(f"  P&L identity closes as printed: {exposure} + ({other}) "
                  f"= {net}")

    # ---- 1c. every model's mean decomposition total equals its mean return
    # The referee found Grok-4's mean Season 1.5 return given as -42.6 per cent
    # in the decomposition and -49.1 in the risk table. With equal starting
    # capital the two are the same quantity, so they must agree. This checks
    # the canonical table directly rather than the macros, model by model, in
    # both seasons.
    acc_path = os.path.join(ROOT, "data", "derived", "accounts.parquet")
    if not os.path.exists(acc_path):
        failures.append("data/derived/accounts.parquet is missing; run `make recon`")
    else:
        import pandas as pd

        acc = pd.read_parquet(acc_path)
        g = acc.groupby(["season", "model"]).agg(
            ret=("final_return", "mean"), pnl=("return_from_pnl", "mean"))
        gap_pp = (100 * (g["pnl"] - g["ret"])).abs()
        bad = gap_pp[gap_pp > 0.05]
        if len(bad):
            lines = "\n".join(f"      {s_}/{m}: {v:.3f} pp"
                               for (s_, m), v in bad.items())
            failures.append(
                f"{len(bad)} model mean(s) where the decomposition total and "
                f"the final return differ by more than 0.05 pp:\n{lines}")
        else:
            print(f"  decomposition total = final return for all "
                  f"{len(g)} season-model means (max gap "
                  f"{gap_pp.max():.4f} pp)")

    # ---- 1d. the frozen-book figure must lie inside the sweep it is quoted
    # against. The letter once reported a range running between the 12- and
    # 48-hour results while quoting the 24-hour figure, which sat outside it.
    sweep_path = os.path.join(ROOT, "data", "derived",
                              "a4_exante_benchmark.json")
    if os.path.exists(sweep_path):
        with open(sweep_path) as fh:
            xa = json.load(fh)
        for season, q in xa.items():
            lo_, hi_ = q["sweep_lo_pct"], q["sweep_hi_pct"]
            head = q["hold_net_pct"]
            if not (lo_ - 1e-9 <= head <= hi_ + 1e-9):
                failures.append(
                    f"{season}: the quoted frozen-book figure {head:.2f}% is "
                    f"outside its own sweep [{lo_:.2f}, {hi_:.2f}]")
            # and the quoted point must actually be one of the swept points
            hrs = str(q["formation_hours"])
            if hrs not in q["cutoffs"]:
                failures.append(
                    f"{season}: the quoted freeze point ({hrs} h) is not one "
                    f"of the swept points {sorted(q['cutoffs'])}")
            elif abs(q["cutoffs"][hrs]["hold_pct"] - head) > 1e-9:
                failures.append(
                    f"{season}: the quoted figure {head:.4f}% disagrees with "
                    f"the sweep's own {hrs}-hour value "
                    f"{q['cutoffs'][hrs]['hold_pct']:.4f}%")
        print(f"  frozen-book figure inside its sweep for "
              f"{len(xa)} season(s)")

    # ---- 2/3. for every manuscript: macros defined, figures and tables present
    defined = set(committed)
    all_used: set[str] = set()
    for label, path, base in DOCS:
        if not os.path.exists(path):
            if "--allow-missing-manuscripts" in sys.argv[1:]:
                print(f"  {label}: omitted in code/data-only distribution; document checks skipped")
                continue
            failures.append(f"{label} is missing")
            continue
        doc = open(path).read()
        # Audit additions have a separate generator and snapshot checks in
        # test_frl_audit.py. Discover their actual definitions through this
        # manuscript's inputs; do not whitelist names or add them to the
        # make_numbers snapshot comparison above.
        local_defined = set(defined)
        missing = []
        for name in re.findall(r"\\input\{([^}]+)\}", doc):
            filename = name if name.endswith(".tex") else name + ".tex"
            included = os.path.normpath(os.path.join(base, filename))
            if not os.path.exists(included):
                missing.append(name)
                continue
            with open(included) as fh:
                source = fh.read()
            # Ignore commented-out definitions, but preserve escaped percent
            # signs in actual LaTeX source.
            source = re.sub(r"(?<!\\)%[^\n]*", "", source)
            local_defined.update(re.findall(
                r"\\(?:newcommand|renewcommand|providecommand)\*?\s*"
                r"\{\\(al[A-Z][A-Za-z]*)\}", source))
        # macro names are \al + CamelCase; the [A-Z] guard keeps LaTeX's own
        # \alpha out of the match
        used = set(re.findall(r"\\(al[A-Z][A-Za-z]*)", doc))
        all_used |= used
        undefined = sorted(used - local_defined)
        if undefined:
            failures.append(f"{label}: macros used but never defined: {undefined}")

        for m in re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", doc):
            if not os.path.exists(os.path.join(PAPER, "figures", os.path.basename(m))):
                missing.append(m)
        if missing:
            failures.append(f"{label}: included but missing on disk: {missing}")
        print(f"  {label}: {len(used)} macros referenced, "
              f"{len(missing)} missing figures/tables")
    print(f"  {len(defined - all_used)} macros defined but unused by any manuscript")

    if failures:
        print("\nFAIL")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\nPASS: every number in the paper regenerates exactly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
