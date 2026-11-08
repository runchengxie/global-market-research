# Volatility robustness implementation plan

> Execute inline using superpowers:executing-plans; fresh whole-branch review before integration.

**Goal:** Decide whether unchanged volatility sizing merits further research using complete fixed historical episodes and transparent independent-source limits.
**Architecture:** Reuse existing volatility_study engine; add a small offline sealed robustness aggregator with explicit stopping arithmetic. Public acquisition/read-only issuer extraction is retained as private provenance, without a credentialed provider integration.
**Tech:** Existing locked root daily-data Python, stdlib; no new runtime dependency unless a demonstrated source-format capability requires it.
**Spec:** ../specs/2026-11-08-volatility-robustness-design.md

## Global constraints

Unchanged original strategy math/parameters; private intent before acquiring outcomes; no threshold tuning, hidden year exclusion, NAV/price substitution or independence overclaim. No broker, scheduler, credentials, account/policy/future-cycle changes. Raw/source results external and immutable.

## Review focus

Missing/duplicate planned year-fee results; source/core-parameter mismatch; hindsight-control label/exposure residual; tolerance direction for negative drawdown; integer ceiling for majority; partial/previously seen years; unavailable source semantics versus actual empirical failure.

### Task1: Freeze and acquire

- [ ] Seal private pre-acquisition intent with original protocol hash, episode list and stop conditions.
- [ ] Bounded credential-free public chart/issuer downloads; preserve receipts/errors and distinguish source kinds. Read issuer workbook without modifying it. Check overlap/calendar/price/distributions only where semantics match.

### Task2: Reusable stopping report

- [ ] RED tests for missing/duplicate year/fees, tolerance direction, partial/seen exclusions, ceil majority, parameter/source/tamper mismatch, missing independent-source evidence and immutable output.
- [ ] Implement offline robustness report over sealed per-episode study directories; verify intended date/core/source bindings and every fee/arm; produce per-episode comparisons and stopping decision, separate independent-source stage.
- [ ] GREEN tests and original study regression checks; bilingual generic operations docs.

### Task3: Execute and deliver

- [ ] Source-bind derived per-year protocols after acquisition while preserving frozen intent; run all fixed episodes without picking winners; aggregate and interpret complete results/gaps.
- [ ] Full/static tests, fresh review, exact-head CI, standing-authorized integration/deployment checks, retained runtime/reproduction/source receipts and task-only Git cleanup.
