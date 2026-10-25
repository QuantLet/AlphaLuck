"""One external corroboration: the replay league of Barton et al. (2026).

Our design objection to Alpha Arena is that it has no true replicates -- each
model trades a single path, so the model's own effect cannot be separated from
the market's without the replicated runs of section 4. Barton et al. (2026)
publish aggregate results from a design that does have replicates: a league in
which each model is scored on the same set of replayed scenarios, with regret
measured against the realised best action, bootstrap intervals, and Holm-adjusted
tests against the leading model.

That is their result on their data, not ours, and it is replay rather than live
trading. We read their published file only to quote it correctly: how many
scenarios each model faced, how wide the intervals are, and the smallest
Holm-adjusted p-value obtained by any frontier model against the leader. If
that p-value is large, their properly replicated design still cannot separate
frontier models, which is the point worth citing.

Their baseline arms (always-flat, random, a momentum heuristic, a production
agent) are excluded from the frontier comparison and reported separately: a
baseline is not a language model, and the momentum heuristic is the only arm
that is clearly worse than the rest.

Source: https://github.com/ProjectDXAI/continuous-record-llm-trading-agents
(data/league.csv), released CC BY 4.0. Committed with attribution.
"""
from __future__ import annotations

import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import prov

DER = os.path.join(prov.ROOT, "data", "derived")
REPO = "ProjectDXAI/continuous-record-llm-trading-agents"
URL = f"https://raw.githubusercontent.com/{REPO}/HEAD/data/league.csv"


def main() -> None:
    path = prov.fetch("dxap/league.csv", URL)
    d = pd.read_csv(path)
    d.columns = [c.strip() for c in d.columns]

    # Their baseline arms are prefixed "BASE"; everything else is a model.
    base = d[d["model"].str.startswith("BASE")]
    mods = d[~d["model"].str.startswith("BASE")].copy()

    # Holm-adjusted p against the leading arm. Blank for the leader itself and
    # for the baselines, so the comparison is over the frontier models that
    # carry one.
    tested = mods.dropna(subset=["holm_p_vs_leader"])
    cells = sorted(d["cells"].unique())

    out = {
        "n_models": int(len(mods)),
        "n_baselines": int(len(base)),
        "model_names": sorted(mods["model"]),
        "cells": int(cells[0]) if len(cells) == 1 else cells,
        "n_tested": int(len(tested)),
        # the smallest adjusted p is the best chance any model had of being
        # separated from the leader; if even that is large, none are
        "holm_p_min": float(tested["holm_p_vs_leader"].min()),
        "regret_lo": float(mods["regret4_bps"].min()),
        "regret_hi": float(mods["regret4_bps"].max()),
        "ci_lo_min": float(mods["ci_lo"].min()),
        "ci_hi_max": float(mods["ci_hi"].max()),
        "skill_absmax": float(mods["skill"].abs().max()),
        "baseline_flat_regret": float(
            base[base["model"].str.contains("always-flat")]["regret4_bps"].iloc[0]),
        "source_url": URL,
        "licence": "CC BY 4.0",
    }

    # Do the model intervals all overlap? If the widest lower bound is below
    # the narrowest upper bound, no pair is separated by its intervals alone.
    out["intervals_all_overlap"] = bool(
        mods["ci_lo"].max() < mods["ci_hi"].min())

    with open(os.path.join(DER, "dxap_league.json"), "w") as fh:
        json.dump(out, fh, indent=1)

    print("=== Barton et al. (2026) replay league, from their data/league.csv ===\n")
    print(f"  models                 {out['n_models']} "
          f"({', '.join(out['model_names'])})")
    print(f"  baseline arms          {out['n_baselines']}")
    print(f"  scenarios per arm      {out['cells']}")
    print(f"  regret across models   {out['regret_lo']:.1f} to "
          f"{out['regret_hi']:.1f} bps")
    print(f"  interval span          {out['ci_lo_min']:.1f} to "
          f"{out['ci_hi_max']:.1f} bps")
    print(f"  all model intervals overlap: {out['intervals_all_overlap']}")
    print(f"  smallest Holm-adjusted p vs leader ({out['n_tested']} tested): "
          f"{out['holm_p_min']:.4f}")
    print(f"  largest |skill| among models        {out['skill_absmax']:.3f}")
    print(f"  always-flat baseline regret         "
          f"{out['baseline_flat_regret']:.1f} bps")
    print(f"\n  source {URL}\n  licence {out['licence']}")


if __name__ == "__main__":
    main()
