# Reviewed statements implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline; one whole-branch review at the end.

**Goal:** Make reviewed daily account evidence consumable and document actual strategy implementation gaps.
**Architecture:** One focused statement validator under competition_review and a small extension of its existing CLI. Pure participation arithmetic remains canonical. Actual records stay external.
**Tech Stack:** Python 3.12 stdlib, existing Decimal/path/hash/seal helpers; optional calendar dependency unchanged.
**Spec:** docs/superpowers/specs/2026-11-07-competition-statements-design.md

## Global constraints
No network/broker collection, credentials, executable targets, platform or scheduler edits. Existing sealed evidence is immutable. Missing/partial days unknown. All public docs English/zh-CN aligned. Input claims do not certify official eligibility.

## Review focus
- Source paths cannot escape input parent or point into output.
- Future or partial-day observations cannot establish completed-day facts.
- Calendar completeness is a reviewed assertion, not inferred from supplied days.
- Mixed account/currency and declaration binding fail closed.
- Reproducible CLI reports must change when supplied daily evidence changes.

### Task 1: Statements and CLI
- [ ] Add failing synthetic statement tests for complete/missing/intraday/OR cases and malformed provenance, dates and source paths.
- [ ] Implement statements.py validation and add CLI optional bundle and paired policy/decision arguments; preserve old calls.
- [ ] Test CLI ingestion end to end, dynamic summaries, hash checking and no overwrite; document exact normalized contract and export preparation.

### Task 2: Evidence exploration and delivery
- [ ] Inventory existing exports and strategy evidence, retaining scope/exclusions/hash receipts outside Git; write private EN/zh-CN findings and recovery/research sequence.
- [ ] Run focused/full tests, lint/import checks and fresh-context whole-branch review; fix material findings with regression coverage.
- [ ] PR, exact-head CI, authorized integration, main/deployment verification, private retention and task-only cleanup.
