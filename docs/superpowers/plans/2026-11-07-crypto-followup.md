# Crypto follow-up implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Audit forward evidence and run a bounded, comparable retrospective LSTM/MoE study with a public research journal.
**Architecture:** Root audits receipt files and exports closed aggregates; independent crypto leaf diagnoses scores and trains optional models. Existing observer and intraday producer remain unchanged.
**Tech Stack:** Python3.12, optional pinned CPU PyTorch2.10.0, NumPy/sklearn, Astro and strict TypeScript.
**Spec:** `docs/superpowers/specs/2026-11-07-crypto-followup-design.md`

## Global Constraints
Existing forward protocol/producer unchanged; outputs external and sealed.39expected fits/45started cap/900sec, fixed3seeds/5epochs, no private provider calls. All historical model comparisons exploratory. Same four-hour common sample scope and one-bar delay. Public aggregate-only snapshot alongside original snapshot.

## Review Focus
- Future or missing observations must never become mature scores.
- Historical definition evidence does not establish publication latency.
- Window histories cannot cross assets or omit the latest complete bar.
- Partial training cannot be exported as completed or retried under a reset plan.
- Fee-selected threshold must depend only on the validation interval, with test timing purged.

### Task 1: Audit and diagnose
Files: root `evaluation/crypto_audit.py`, root tests; leaf `exploration/diagnostics.py`, leaf tests; provider EN/zh-CN evidence docs.
Interfaces: `audit_protocol(protocol:Path,as_of:datetime)->dict` freezes verified receipt prefix and reconstructs scores; `diagnose_scores(study:Path)->dict` returns fixed distribution aggregates. Retain hashes, no new fit.
- [ ] Test invalid time/score/duplicate commitments and fixed-hurdle quantiles; observe failures.
- [ ] Implement audit and score diagnostics with immutable CLI outputs.
- [ ] Verify focused tests, acquire bounded public documentation and write aligned provenance note; commit.

### Task 2: Bounded comparable models
Files: leaf `exploration/models.py`, `study.py`, `cli.py`, tests; optional neural deps/lock and optionalCI.
Interfaces: `freeze_comparison(dataset,study,output,source_revision)` seals config and input hashes; `run_comparison(plan,output)` exclusively claims plan and writes checkpoints/scores/aggregate summaries. No root imports leaf.
- [ ] Test chronological windows, purging, matched parameter count, router learning and validation-only decisions; observe failures.
- [ ] Implement fixed models/config, budget checks and persisted predictions; verify focused tests and commit.
- [ ] Freeze clean source plan, execute once externally with outer timeout, retain completed/partial receipts; never refit original screen.

### Task 3: Publish journal and integrate
Files: root `scripts/crypto_followup_projection.py`, tests; `site/src/data/crypto-followup.v1.json`, bilingualcatalogs/component, crypto topic integration and browser tests; aligned research guide.
Interfaces: closed `crypto.followup_public.v1` aggregate projection with source seals, no individual forecasts or local paths.
- [ ] Test projection scope/private fields and bilingual/noJS rendering; observe failures.
- [ ] Implement closed export and journal; link documentation; run full applicable checks.
- [ ] Independent whole-branch review, fixes RED/GREEN, exact-headCI, merge, deployed live verification, private retention and task cleanup.
