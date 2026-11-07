# Flex reconciliation implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline with one final whole-branch review.

**Goal:** Produce a checked observed stock/cash snapshot from the expanded read-only Flex report.
**Architecture:** Pure flex_reconciliation.py and a small flex_cli.py integration; use existing strict report/Decimal helpers, never research or execution imports.
**Tech Stack:** Python3.12 stdlib/Decimal and existing private seal workflow.
**Spec:** docs/superpowers/specs/2026-11-08-flex-reconciliation-design.md

## Global constraints
No orders, targets, broker login, token/query/scheduler/production activation. No private account data in Git. Reported dates are not certified official sessions. Observed weights are not target weights.

## Review focus
Mixed-date FX or positions; base summary double counting; short/negative cash handling; incomplete identity/marks; offsetting unsupported assets hiding a zero residual.

### Task 1: Pure reconciliation and CLI
- [ ] Write failing synthetic FX/valuation/NAV/cash/LOT and stale/missing/conflicting-source tests.
- [ ] Implement latest-date checks and component statuses, documented fixed tolerances and conservative weights; emit snapshot.json through existing collector.
- [ ] Verify CLI regression/seal behavior and EN/zh-CN documentation.

### Task 2: Actual verification and integration
- [ ] Offline re-inspect the retained new query result and update the private marked-holdings/cash report and source receipts.
- [ ] Run affected/full tests, Ruff/import boundaries, whole-branch review and necessary regressions.
- [ ] PR/exact-head CI/standing authorized integration/main deployment verification/private retention/task-only cleanup.
