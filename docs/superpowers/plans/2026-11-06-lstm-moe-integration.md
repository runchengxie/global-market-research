# LSTM/MoE Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans for native implementation, or superpowers:subagent-driven-development if the user chooses delegation. Steps use checkbox syntax for tracking.

**Goal:** Integrate corrected, reproducible sequence-model research into Global Market Research and migrate the old project entry points.

**Architecture:** Optional equity-lab neural models consume a verified daily snapshot through a new adapter. A timestamp-aware experiment runner owns folds, model selection and immutable artifacts; a separate account replays long/cash decisions. Root execution remains independent. Global Pages hosts the replacement research route before old entry points redirect.

**Tech Stack:** Python 3.12, optional PyTorch/scikit-learn/exchange-calendars, existing pandas/NumPy cash-rebalance primitives, Astro and selectively bundled ECharts.

**Spec:** [Approved design](../specs/2026-11-06-lstm-moe-integration-design.md), [中文](../specs/2026-11-06-lstm-moe-integration-design.zh-CN.md). Design approved by user on 2026-11-06; the execution plan and native implementation were confirmed by the user.

## Global Constraints

- Neural dependencies stay optional in equity-lab; no research imports in root execution.
- Source daily snapshot is read-only; outputs and environments are external under the owner data root.
- Retain `accepted_research=false`, previously exposed history, fixed-current universe and no-dividend limitations.
- Primary target is next-open to following-open, threshold 0.002, long/cash cutoff 0.5; no test-set threshold selection.
- Use 400 fit / 80 validation / 63 test sessions, timestamp purging, one-session additional embargo and a 12-hour modeled readiness allowance.
- Primary pooled panel excludes SPY; windows stay within symbol; fit-only shared scaling; no identity embeddings.
- Five seeds 11/23/37/53/71, batch 32, maximum 50 epochs, patience 5.
- LSTM stage: 600 fits / 6 hours; secondary stages: 240 fits / 6 hours each; oversized schedules fail preflight, interrupted runs remain partial.
- No raw data or real derived time series on Pages without existing owner review and documented rights; synthetic interactive fixtures are default.
- Preserve old results, legacy APIs and unrelated work. Global provider merges and deploys before old site migration.
- Keep English/Chinese reader-facing documents aligned. Use existing global locale catalogs for UI text.

## Review Focus

1. Labels available exactly at a cutoff: strict inequality prevents selection/entry at the same instant.
2. Empty routing batches and all-flat portfolios: skip unused experts and retain finite initial equity/cash.
3. Snapshot changes after initial verification: end-of-run recheck invalidates the run.
4. Ensemble members consume real fit budget: preflight and resumability never disguise incomplete comparisons.
5. Synthetic versus private real data: public projection refuses private time series, migration only links a deployed route.

## Task 1: Daily input adapter and timestamp-aware samples

**Files:** Create `research/equity-lab/src/equity_lab/data/sequence_daily.py`, `research/equity-lab/src/equity_lab/study/sequence/{__init__,samples,protocol}.py`, `research/equity-lab/tests/test_sequence_data.py`, `research/equity-lab/tests/test_sequence_protocol.py`. Update optional extras/lock in `research/equity-lab/pyproject.toml` and `uv.lock`.

**Interfaces:** `load_daily_snapshot(manifest_path, expected_sha256) -> DailySnapshot` contains aligned OHLCV, exchange schedule and input bindings; `build_samples(snapshot, lookback=20) -> SampleSet` contains arrays, feature order and audit rows; `make_folds(samples) -> list[Fold]` returns fit/validation/test indices and cutoff metadata. Keep date-session indices separate from UTC availability timestamps. New helpers do not import root Python.

- [ ] Write tests first: corrupt payload fails; missing/duplicate/non-session dates fail; 15-minute feature availability and 12-hour readiness enforce strict cutoffs; next-open label matches hand arithmetic; no symbol-crossing windows; legacy minute-derived adapter remains unchanged.
- [ ] Run `uv run --locked --extra predictive pytest tests/test_sequence_data.py tests/test_sequence_protocol.py -q` from equity-lab. Expected: new behavior fails before implementation, existing fixture loading works. Install/update optional dependencies only after the missing behavior is observed.
- [ ] Implement manifest/receipt binding, safe path verification and strict daily normalization; derive the exact relative feature list in the spec; generate sample audit rows and frozen rolling folds. Reject insufficient data with a reason.
- [ ] Run focused tests and equity-lab Ruff. Expected: all pass, including exact cutoff equality and final short-fold cases.
- [ ] Commit adapter/protocol and synchronized data documentation; record source and validation revisions in the task ledger.

## Task 2: Correct sequence models and true sparse dispatch

**Files:** Create `research/equity-lab/src/equity_lab/models/{__init__.py,sequence/__init__.py,sequence/lstm.py,sequence/transformer.py,sequence/checkpoint.py}`, `research/equity-lab/tests/test_sequence_models.py`. Add the optional `neural` extra and refresh the leaf lock; add a dedicated neural job to `.github/workflows/research.yml`.

**Interfaces:** `SequenceModel(config)` exposes `forward(windows) -> ModelOutput` with logits, router probabilities, chosen experts and dispatch counts; `build_model(config)` builds LSTM/dense/sparse/Transformer variants. `parameter_matched_width(config) -> int`; `save_checkpoint(model, path, metadata)` and `load_checkpoint(path)` round-trip architecture and weights. Neural imports stay out of default paths.

- [ ] Write tests first for controlled dense mathematical parity, actual processed sample counts, empty expert batches, top-2 forward weighting, nonzero top-1 task gradient, selected expert gradient, nearest parameter match, model reload parity and historical-window-only Transformer output shape.
- [ ] Run neural tests. Expected: missing model behavior fails. Default environment must still collect non-neural tests without importing PyTorch.
- [ ] Implement equal/dense/sparse LSTMs, selected-softmax top-1 and renormalized top-2, separately measured auxiliary loss, configurable shared-router variants and 2-layer width-64/4-head Transformer with 4-expert top-2 FFN option. Dispatch before expert computation in training and inference.
- [ ] Run `uv run --locked --extra neural pytest tests/test_sequence_models.py -q`, then the full leaf suite with neural extra. Expected: all pass; neural CI exercises gradients/dispatch instead of silently skipping them.
- [ ] Commit model code, provenance note and CI. Do not copy unlicensed original source; independently implement mathematical architecture with source attribution.

## Task 3: Long/cash replay and paired measurements

**Files:** Create `research/equity-lab/src/equity_lab/study/sequence/{account,metrics}.py`, `research/equity-lab/tests/test_sequence_account.py`, `research/equity-lab/tests/test_sequence_metrics.py`.

**Interfaces:** `replay_sequence(observations, plans, calendar, fee_bps) -> AccountResult` produces fills, cash/units, marks, net/gross measures and reasons. `paired_report(results, block_length=20, draws=2000, seed=20261106) -> dict` returns paired fold/seed diagnostics. Consume sample timestamps from Task 1; reuse `portfolio.cash_rebalance.rebalance`, not incompatible legacy account shortcuts.

- [ ] Write tests: starting losses give -19% for two -10% periods; initial/terminal costs counted once; cash-only has zero return and undefined Sharpe reason; missing held price fails; independent folds never become one NAV; panel capital remains conserved; bootstrap draws retain all same-date stocks and never cross folds.
- [ ] Run focused tests and observe intended missing-behavior failures.
- [ ] Implement next-open fills and terminal exits with fees 0/5/20/40 bps; split-adjusted synthetic price-unit accounting, equal initial stock sleeves, separate SPY; add AUC/log-loss/Brier/reliability diagnostics and paired bootstrap. Preserve unavailable values and reasons.
- [ ] Run focused and full leaf tests. Expected: hand-computed cash paths reconcile and existing accounts stay unchanged.
- [ ] Commit account/metrics and bilingual accounting limitations.

## Task 4: Frozen experiment scheduler, models and immutable bundles

**Files:** Create `research/equity-lab/src/equity_lab/study/sequence/{config,runner,artifacts,cli}.py`, `research/equity-lab/tests/test_sequence_runner.py`, `research/equity-lab/tests/test_sequence_artifacts.py`, `docs/research/lstm-moe.md`, `docs/research/lstm-moe.zh-CN.md`. Update equity-lab READMEs and root architecture links.

**Interfaces:** CLI `python -m equity_lab.study.sequence.cli plan|run|inspect` accepts explicit manifest/hash and new output path; `freeze_schedule(config, folds) -> Schedule`; `run_study(schedule, snapshot, output) -> RunSummary`; `verify_bundle(path) -> dict`. Run schema `equity_lab.sequence_study.v1` binds exact source/input/config/model versions. No CLI calls brokers or root acceptance promotion.

- [ ] Write tests first for nine actual fits per full learned candidate set, 600-fit preflight cap, time budget/partial results, exclusive output creation, checkpoint/scaler/feature-order reload, post-run source mutation rejection and private output paths excluded from public summaries.
- [ ] Run tests and observe failures before implementing orchestration.
- [ ] Implement cash/holding/momentum/logistic/LSTM64/matched/equal/independent/dense/top-2 suite and separately scheduled top-1/feature/router/Transformer ablations. Store full probabilities, chosen experts, loss components, per-expert representations/probes, audit times, fills, metrics, checkpoints, environment, schedule and checksums. Never refit to repair a poor test result.
- [ ] Run an installed synthetic CLI smoke, inspect and replay the resulting bundle; run full leaf tests. Expected: all artifacts bind and reload; malformed or partial reports cannot look completed.
- [ ] Commit orchestration and bilingual usage/docs. Keep primary versus secondary and exploratory status visible.

## Task 5: Bounded real exploratory validation

**Files:** No raw data or generated outputs in Git. Any fixes belong to the earlier owning module with a reproducing regression test. Update only reusable documentation if needed.

**Interfaces:** Use Task 4 installed CLI and explicit existing owner manifest/hash. External run records bind source commits, schedule, environment, hashes and run status.

- [ ] Verify actual dataset inventory and session alignment again; execute a single-seed/single-fold SPY smoke within 10 minutes. Expected: complete valid bundle or explicit diagnosed failure, never promoted evidence.
- [ ] Freeze exact pooled-panel fit schedule; run primary suite within 600 fits / 6 hours, checking time and recording progress between fits. Expected: completed comparisons or explicit partial status without altering frozen candidates.
- [ ] If primary completed, run separate Transformer and feature/router ablation schedules within their individual 240-fit / 6-hour caps. Expected: completed/partial/pending reported independently.
- [ ] Inspect round-trip checkpoints, zero-trade warnings, paired metrics, router loads, dispatch counts and actual synchronized runtime/memory. Record actual CPU/GPU limitations. Recheck inputs on completion.
- [ ] Keep all real results private until publication review/rights permit a specific projection. Do not change acceptance flags, reserve a new holdout or acquire data.

## Task 6: Global research page and interactive charts

**Files:** Create `site/src/pages/research/lstm-moe.astro` (adapt to actual route conventions), an accessible chart component under `site/src/components/`, versioned synthetic fixture under `site/src/data/`, projection tests under existing site validation tooling; update locale catalogs, navigation, package lock and bilingual research docs.

**Interfaces:** Public schema `sequence_public_summary.v1` admits evidence metadata and explicitly synthetic or individually approved aggregates. Excludes raw OHLCV, private source paths and unapproved real series. Page URL is the final canonical migration destination, validated from built/deployed output.

- [ ] Write projection tests first: reject real private series without approved allowlist; synthetic flag and caveats required; zero-trade state rendered; both languages link valid documentation.
- [ ] Run tests and observe missing projection/page behavior.
- [ ] Implement lazy local ECharts line modules, zoom/hover/toggles, HTML confusion matrices and keyboard/no-JS summaries. Keep historical snapshots unchanged. Add links in global navigation and READMEs.
- [ ] Run actual site install/build/projection checks from workflows, check both languages/narrow layout/keyboard, measure compressed JS plus data versus prior PNG. Expected: valid route, accessible fallback and measured payload, without claiming it must be smaller.
- [ ] Commit, obtain independent branch review, run current-combined checks, merge global PR under standing authorization, verify main and Pages route. Preserve task worktree until all unique edits are merged.

## Task 7: Old repository migration notice and closeout

**Files (moe-lstm repository):** Modify `README.md`, `README.zh-CN.md`, `site/src/pages/index.astro`, its locale copy and only necessary route validation/tests. Add no neural dependencies or new training platform.

**Interfaces:** Consume Task 6 verified canonical global URL. Legacy entry points expose migration reason, historical scope, replacement CLI/docs and manual links, with optional delayed homepage navigation. Deep history URLs remain available.

- [ ] Create isolated migration worktree from current main after inspecting/fetching remotes. Verify configured GitHub CLI account and actual push URL; use known public contributor/noreply identity, not personal metadata.
- [ ] Add migration notice and visible links in both languages; preserve historical result/doc assets. Add canonical metadata and auxiliary homepage redirect with no-JS fallback. Do not archive/delete repository.
- [ ] Run old site's existing build/dist checks and migration-link test. Manually verify old homepage, language choice, no-JS manual link and historical deep link. Expected: all lead/read correctly and no redirect loop.
- [ ] Independently review, open PR against user repository, validate current combined main, merge after required checks, verify old Pages and destination. Query remote state before retrying uncertain writes.
- [ ] Verify both merged revisions/deployments; update private retention records required by global AGENTS. Remove only completed task branches/worktrees after merged commits and no unique unsaved work are confirmed. Fast-forward clean primary checkouts. Report PRs, revisions, tests, actual run states, payload measurements and remaining external evidence limits.

## Self-review and execution handoff

All approved design areas map to Tasks 1–7. Review-focus failures map to Tasks 1, 2–3, 4–5, 4–5 and 6–7 respectively. Exact dependency versions and route-validation command names will be read from current official/package metadata and existing repository workflows at implementation time; no guessed passing checks. An implementation ruling must be recorded if the current code invalidates an interface, without silently changing research semantics.

Recommended execution: native implementation in this session, with independent final reviews before each repository merges. This keeps shared sample/account/artifact contracts in one working context. User may instead select per-task subagent implementation/review.
