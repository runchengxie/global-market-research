# Daily evidence reconciliation implementation plan

> Implement inline with superpowers:executing-plans and a fresh whole-branch review.

**Goal:** Produce a reproducible, missing-aware daily platform/broker evidence table.
**Architecture:** One offline daily_reconciliation module reuses existing declaration/snapshot/statement contracts; private holiday and checkpoint evidence remain unaccepted.
**Tech stack:** Existing locked root daily-data profile, no new dependency.
**Spec:** ../specs/2026-11-08-daily-reconciliation-design.md

## Global constraints

No official-rate inference, eligibility certificate, generic unreviewed importer, platform/broker action, scheduler or changed frozen policy. Same labels/numbers do not prove semantic equivalence. Preserve raw evidence and all missing rows; keep private materials external.

## Review focus

Account/currency/declaration mismatches; tampered/future inputs; platform dates absent at broker and reverse; duplicated executions; zero/missing metric distinction and non-equivalent rates.

### Task1: Reconciliation table

- [ ] RED tests for missing-platform rows, partial/platform-only days, zero vs null, descriptive gap, mismatched account/base/declaration, tampered sources/ledger, immutable output.
- [ ] Implement run(declaration_root,snapshot_root,output,*,statement_bundle=None,now=None), _join(broker_rows,execution_counts,platform_rows), current-time CLI. Reuse validation before fresh sealed bilingual output. No backdating CLI.
- [ ] GREEN targeted and existing statement/Flex regression tests, bilingual operations docs and competition-review links.

### Task2: Concrete private evidence and delivery

- [ ] Generate real current missing-platform reconciliation using existing sealed declaration/Flex inputs; preserve export-search scope and browser limitation.
- [ ] Inspect holiday blockers against exact last completed XTKS session, source presence and mark age. Keep frozen72-hour policy unchanged and record future policy options separately.
- [ ] Preserve first checkpoint preparation/status with no fabricated future observation; explicit missing official export and source contract checklist.
- [ ] Full/static tests, fresh whole-branch review, exact-head CI, standing-authorized integration/deployment verification, retention and task-only Git cleanup.
