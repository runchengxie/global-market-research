# File-backed strategy case Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline. Steps use checkbox syntax.

**Goal:** Verify actual declaration, model-lineage and marked-position inputs before comparing a supplied allocation offline.
**Architecture:** New strategy_case module composes existing declaration receipt, seal utilities and pure daily reviewer. New strategy_cli handles immutable private output only.
**Tech Stack:** Python stdlib and existing root test environment.
**Spec:** docs/superpowers/specs/2026-11-08-strategy-case-design.md

## Global Constraints

No network, credentials, orders, production changes or research imports. Missing policy/model/PIT evidence stays missing. English and zh-CN docs/reports align. Retain external artifacts.

## Review Focus

- Tampered or future files cannot become confirmed evidence.
- Current holdings must derive from verified conid Summary rows, never supplied arbitrary weights.
- Missing sources block comparisons without creating a pretend trained model.
- Scores, universe, target and parent records must agree.
- Cost and shock scenarios must not be described as forecasts or backtests.

### Task 1: Verified case and comparison

Files: create src/competition_tools/competition_review/strategy_case.py and tests/competition_tools/test_strategy_case.py.
Interfaces: build_case(case_file, decision_time) -> dict; compare_weights(current, target, cost_bps) -> dict.
- [ ] Add synthetic fixtures and failing tests for complete arithmetic, missing roles, tamper, policy timing, source parents, snapshot identity and invalid payloads.
- [ ] Run pytest test_strategy_case.py and observe failures.
- [ ] Implement file verification, role payload validation, current conid weights, daily-review composition and explicitly hypothetical comparisons.
- [ ] Run affected suites and lint, then commit.

### Task 2: CLI, operation guide and private investigation

Files: create strategy_cli.py; extend docs/operations/competition-review.md and .zh-CN.md; extend same tests.
Interfaces: run(case_file, output, decision_time) -> dict; CLI --case --output --as-of.
- [ ] Add failing sealed-output, immutable-output and no-output-on-invalid-input tests.
- [ ] Implement new private case report plus bilingual explanation and provenance, no target handoff.
- [ ] Inventory existing relevant declaration/model evidence; preserve scoped findings privately, create a case with only established references, run offline and retain blocked status if appropriate.
- [ ] Full root validation, independent whole-branch review, exact-head PR checks and standing authorized integration/Pages verification; retain source/lock/wheel/log/ledger, clean only this task's Git assets.
