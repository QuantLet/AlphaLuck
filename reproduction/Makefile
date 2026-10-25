PY := .venv/bin/python

.PHONY: all setup download build recon analyse followup checks figures quantlets tables numbers audit paper frl frl-figures frl-appendix frl-audit frl-review frl-organiser frl-extensions frl-words bib test verify-raw verdict clean-derived clean-paper

# The published Quantlets (QuantLet/AlphaLuck) carry their own styling;
# `make quantlets` regenerates local copies with the draft style, so it is
# run on its own, not as part of `all`.
all: download build recon analyse followup checks tables audit figures numbers frl-review test

setup:
	uv venv --python 3.13.9
	uv pip install -r requirements.lock

# Every raw file present on disk against the SHA-256 in PROVENANCE.csv.
# Missing licensed or optional files (EODHD, pilot archives) are reported, not failed.
verify-raw:
	$(PY) src/verify_raw.py

# Phase 2 -- cached: nothing already in data/raw/ is re-requested.
download:
	$(PY) src/download_organiser.py
	$(PY) src/extract_wallets.py
	$(PY) src/download_hl.py
	$(PY) src/download_candles.py
	$(PY) src/download_aitrader.py

build:
	$(PY) src/build.py

recon:
	$(PY) src/reconcile.py
	$(PY) src/canonical.py

# Phases 3-5 of the original audit.
analyse:
	$(PY) src/analyse.py
	$(PY) src/replicates.py

# Follow-up items 1-5.
followup:
	$(PY) src/competitions.py
	$(PY) src/variance_components.py
	$(PY) src/similarity_ci.py
	$(PY) src/icc_ci.py

# Robustness checks and referee additions.
checks:
	$(PY) src/check_identification.py
	$(PY) src/check_scaling.py
	$(PY) src/check_variance_shares.py
	$(PY) src/check_risk_trait.py
	$(PY) src/pnl_decomposition.py
	$(PY) src/risk_seasons.py
	$(PY) src/vol_fixed_denominator.py
	$(PY) src/referee1_covariate.py
	$(PY) src/referee2_permutation.py
	$(PY) src/referee3_wallet_rankcorr.py
	$(PY) src/referee4_horizon.py
	$(PY) src/sharpe_horizon.py
	$(PY) src/inference_audit.py
	$(PY) src/provenance_table.py
	$(PY) src/return_sources.py
	$(PY) src/mark_invariance.py
	$(PY) src/persistence.py
	-$(PY) src/pnl_external_marks.py
	$(PY) src/exante_benchmark.py
	$(PY) src/dxap_league.py

figures:
	$(PY) paper/code/make_figures.py

quantlets:
	$(PY) paper/code/make_quantlets.py

tables:
	$(PY) src/make_tables.py
	$(PY) src/make_tables_followup.py
	$(PY) src/make_tables_checks.py
	$(PY) src/make_tables_extra.py

# Paper macros and LaTeX tables: every number the manuscript quotes.
numbers:
	$(PY) paper/code/make_numbers.py

audit:
	$(PY) src/render_audit.py

# Build the manuscript. Requires a TeX distribution (latexmk + pdflatex).
paper: numbers figures
	cd paper && latexmk -pdf -bibtex -interaction=nonstopmode alphaluck_draft.tex

# Verify every bibliography entry against Crossref / arXiv.
bib:
	$(PY) paper/code/audit_bib.py

# Regenerate only figures used in the FRL paper; the optional archived pilot
# is not an input to this manuscript.
frl-figures:
	$(PY) paper/code/fig2_risk_trait.py
	$(PY) paper/code/fig3_risk_return.py
	$(PY) paper/code/fig5_pnl_decomposition.py
	$(PY) paper/code/fig8_formation_hour.py
	$(PY) paper/code/fig9_gap_bridge.py
	$(PY) paper/code/fig10_formation_week.py
	$(PY) paper/code/fig11_accounts.py
	$(PY) paper/code/fig12_liquidation_stress.py

# Finance Research Letters version: paper + separate highlights file.
frl: numbers frl-figures frl-review
	cd paper/frl && latexmk -pdf -bibtex -interaction=nonstopmode alphaluck_frl.tex
	cd paper/frl && latexmk -pdf -interaction=nonstopmode highlights.tex
	cd paper/frl && latexmk -pdf -bibtex -interaction=nonstopmode online_appendix.tex

# Referee audit and benchmark cost sensitivity for the letter. Writes
# paper/frl/referee_audit.json, paper/frl/audit_reconciliation.tex and
# paper/frl/benchmark_cost_sensitivity.json. The cost sensitivity is a
# terminal adjustment only: no post-freeze funding, no liquidation cost.
frl-audit:
	$(PY) paper/frl/referee_audit.py
	$(PY) paper/frl/benchmark_cost_sensitivity.py
	$(PY) src/funding_hourly_sensitivity.py
	$(PY) paper/frl/render_audit_additions.py

# Descriptive paired-date and exposure-specific reviewer analyses.
frl-review: frl-audit
	$(PY) paper/frl/paired_denominator_sensitivity.py --out paper/frl/review_results/inference
	$(PY) src/frozen_book_robustness.py --output data/derived
	$(PY) paper/frl/render_reviewer_revision.py
	$(MAKE) frl-organiser

# Hourly organiser snapshots (positions, margins, liquidation prices) against
# the on-chain reconstruction, the 6 December conversations summary and the
# exposure-denominator check (src/exposure_mechanics.py). Needs
# data/raw/nof1_hourly/ (organiser files, not redistributed; see DATA.md).
frl-organiser:
	$(PY) src/organiser_hourly.py
	$(PY) src/organiser_conversations.py
	$(PY) src/exposure_mechanics.py
	$(PY) paper/frl/render_organiser_hourly.py
	$(PY) src/export_formation_quantlet.py
	$(MAKE) frl-extensions

# Analyses suggested by the collaborator's source notes: the exchange oracle
# recovered from funding payments (--no-fetch reuses data/external/oracle/;
# drop it to re-query the public info endpoint), declared exit plans against
# on-chain episodes, and interim standing against later exposure by arm.
# Descriptive; the last two need data/raw/nof1_hourly/. Then the frozen book
# against realised trading before costs, exposure-matched and index-hedged,
# and resampled model ranks (src/holding_vs_trading.py; its index windows
# read the formation-hour sweep written by frl-organiser). Last, the same
# comparison on AI-Trader's published position logs (src/aitrader_replication.py).
frl-extensions:
	$(PY) src/oracle_validation.py --no-fetch
	$(PY) paper/frl/render_oracle_numbers.py
	$(PY) src/exit_plan_adherence.py
	$(PY) src/tournament_effect.py
	$(PY) src/holding_vs_trading.py
	$(PY) src/aitrader_replication.py

# Online appendix to the letter.
frl-appendix: numbers frl-figures frl-review
	cd paper/frl && latexmk -pdf -bibtex -interaction=nonstopmode online_appendix.tex

# Word count of the FRL main text. texcount is not on every machine and
# failed silently where it was absent, so this is a Python counter whose
# exclusions are explicit: abstract, floats and their captions, displayed
# maths, \input tables, bibliography and back matter.
frl-words:
	@$(PY) paper/code/wordcount.py paper/frl/alphaluck_frl.tex

# Fails if any regenerated number differs from the committed numbers.tex.
test:
	$(PY) tests/test_numbers.py --allow-missing-manuscripts
	$(PY) tests/test_frl_audit.py
	$(PY) tests/test_frozen_book_robustness.py data/derived
	$(PY) tests/test_inference_regression.py
	$(PY) tests/test_build_marks.py
	$(PY) tests/test_exante_missing_marks.py
	$(PY) tests/test_funding_metadata.py
	$(PY) tests/test_organiser_hourly.py
	$(PY) tests/test_oracle_validation.py
	$(PY) tests/test_exit_plan.py
	$(PY) tests/test_tournament_effect.py
	$(PY) tests/test_holding_vs_trading.py
	$(PY) tests/test_aitrader_replication.py

verdict:
	@sed -n '/## 1. Verdict/,/^<details>/p' AUDIT.md
	@awk '/^### Inventory/{f=1;next} /^### T1/{f=0} f' data/derived/tables.md

clean-derived:
	rm -f data/derived/*.parquet data/derived/*.csv data/derived/*.md data/derived/*.json

clean-paper:
	cd paper && latexmk -C
	rm -rf paper/figures/_check
