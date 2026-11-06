# Sequence Target Study Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Compare classification and return regression under frozen controls; inventory evidence and freeze blocked forward preparation; evaluate explicit MoE continuation conditions.

**Architecture:** Independent leaf fit/target-run/analysis modules consume existing SampleSet/Fold/account and model APIs. Root readiness consumes versioned audit/calendar files without leaf imports. Immutable private bundles bind all sources and status.

**Tech Stack:** Existing locked Python3.12, numpy/pandas/sklearn1.7.2/torch2.10/exchange-calendars4.13.2; stdlib root.

**Spec:** docs/superpowers/specs/2026-11-07-sequence-target-study-design.md

## Global Constraints

- Fixed snapshot/relative10/lookback20/sevenfolds; objectives classification and regression.
- Neural matched/equal/sparse, seeds11/23/37; linear once per fold/objective;140fits<=180,6hr,30epochs,batch128,patience5.
- Fit-only target/feature scaling; validation-only selection; source/inputs verified before seal; partial never complete.
- No broker/acquisition/acceptance, no new shared pointers; output/environment external.
- Existing public APIs and probability-only browser unchanged; preserve unrelated worktree.

## Review Focus

- Constant/single-class targets and constant cross-sectional ranks remain explicit, finite and reproducible.
- Modifying future test labels/prices cannot change fit normalization or chosen validation threshold.
- Linear seed duplication cannot invent market observations or overrun fit accounting.
- Interruptions, late budget expiration, missing files or resealed inputs cannot produce completed/pass status.
- Calendar preparation and candidate records never become registered/accepted holdouts by self-attestation.

### Task1: Objective fit and saved-score contract
- [ ] Write failing tests for fit-only normalization, raw/probability score reconstruction and constant-target cases.
- [ ] Create `models/sequence/objectives.py` for objective loss/target encoding and `study/sequence/target_fit.py` for neural/linear checkpoint artifacts using existing model definitions.
- [ ] Run tests and record deterministic classification/regression reconstruction.
- [ ] Commit.

### Task2: Bounded target runner and continuation evaluator
- [ ] Write failing synthetic integration tests for both targets, clock identity, finite budget, partial seals and explicit gate outcomes.
- [ ] Create `study/sequence/target_study.py`, `target_analysis.py`, `target_cli.py`; implement fixed/validation/exposure/control accounts and proper losses/IC, paired uncertainty,7-fold rule checks.
- [ ] Include modeled forward calendar export as separate CLI preparation action.
- [ ] Verify no reconstruction changes legacy account/model behavior; commit.

### Task3: Evidence/readiness packet and guides
- [ ] Write failing root tests for candidate evidence, malformed/late calendar, exact bindings and no self-promotion.
- [ ] Create `competition_tools/evaluation/sequence_readiness.py` using owner auditor/requirements and file-only input; bind frozen configuration and future calendar.
- [ ] Add EN/ZH `docs/research/sequence-target-study*.md` with commands and limitations; link existing sequence docs; CI neural test glob includes new sequence tests.
- [ ] Run root/leaf/full affected suites, boundaries, Ruff/build/public scan; commit exact source.

### Task4: Actual exploration and delivery
- [ ] Archive source, create external task environment and frozen plan before fitting.
- [ ] Run140fit screen with checkpointed status and budget; reverify snapshot; analyze actual results and preparation evidence.
- [ ] Independently review; fix substantive issues and rerun required affected evidence.
- [ ] Push/open PR with authorized aggregates and truthful status; all checks against current main; integrate and verify main/Pages.
- [ ] Retain inputs/results/runtimes and cleanup only this task's branch/worktree; report actual gate outcomes and blockers.
