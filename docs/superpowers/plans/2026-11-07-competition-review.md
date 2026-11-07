# Competition strategy evidence implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deliver a private declaration-aligned participation audit and daily review without changing positions.
**Architecture:** Focused root stdlib modules for participation math, evidence loading, daily review and CLI/report. Optional calendar provider remains lazy. Actual evidence and user-pasted declaration stay outside Git.
**Tech Stack:** Python3.12, Decimal, existing external storage/seal helpers and optional pinned exchange_calendars.
**Spec:** `docs/superpowers/specs/2026-11-07-competition-review-design.md`

## Global Constraints
No broker/network collection, orders, platform/scheduler/config changes or raw private data in Git. Unknown is not zero; local snapshots are not official daily facts. Daily report is not a trading handoff. Existing declaration and edit-lock govern proposals; no retroactive policy claims.

## Review Focus
- Same-time conflicting snapshots cannot be silently selected by file ordering.
- UTC/HKT dates and market session labels must not be conflated, including the contest end at06:00HKT.
- Partial daily information cannot establish flat days or route eligibility.
- Fresh targets require a causally prior PIT/Ranker chain; stale or future inputs must block.
- A proposed policy and advertised account capabilities cannot become execution authorization or proof of registration/account binding.

### Task 1: Participation evidence and arithmetic
Files: `src/competition_tools/competition_review/{__init__,participation,evidence}.py`, `tests/competition_tools/test_competition_review.py`.
Interfaces: `summarize_days(rows)` computes elapsed-only three-valued route statuses; `future_bounds(known_sum,unknown_past,remaining)` is conditional unlevered planning; `load_observations(root,as_of)` returns private observations+source hashes/errors; `calendar_scenario(name,as_of)` returns completed/full contest sessions; `daily_rows(sessions,facts)` preserves unknown fields.
- [ ] Test complete/unknown/OR/intraday cases, duplicate/conflicting inputs and time/session boundaries; observe failures.
- [ ] Implement pure arithmetic and strict offline evidence loading; verify focused tests, commit.

### Task 2: Declaration-aligned daily review
Files: `competition_review/{decision,cli}.py`, additional tests; EN/zh-CN guides under `docs/operations/competition-review*`.
Interfaces: `review_decision(policy,inputs,decision_time)` returns blocked/review_required/maintain_candidate, binding hashes and no order fields. CLI consumes explicit external declaration/snapshot root/optional normalized-facts input, writes a new sealed private report. Draft policy retains required nulls and prospective-only options.
- [ ] Test stale/future/unbound/incomplete sources, causal source chain and valid maintain versus drift/risk review; observe failures.
- [ ] Implement scoped report/CLI and private draft contract; document normalized inputs, official-rule uncertainty, local-vs-platform collection and recovery checklist.
- [ ] Run actual read-only audit, relevant/full tests and independent finalreview; fix findings RED/GREEN; PR/CI/merge/main verification, private retention and task cleanup.
