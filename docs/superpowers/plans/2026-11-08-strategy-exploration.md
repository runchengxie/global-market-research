# Simple-strategy evidence exploration implementation plan

> Execute inline using superpowers:executing-plans; one fresh whole-branch reviewer.

**Goal:** Complete inspectable daily baseline diagnostics and private account/strategy evidence without changing trading policy.
**Architecture:** Pure etf_paths helper; optional daily_paths on existing etf_rehearsal; immutable private reports use existing seals and data roots.
**Tech stack:** Existing locked root daily-data Python profile; no new dependencies.
**Spec:** ../specs/2026-11-08-strategy-exploration-design.md

## Global constraints

Preserve v1 default, real-ledger and actual-strategy gates. No orders, broker/network collection, scheduler, platform editing or implicit approval. Missing inputs fail rather than fill. All research remains retrospective/non-executable and private account outputs remain outside Git.

## Review focus

Initial fee drawdown must include wealth1; paths use constant units not daily fixed weights; cash accrues by elapsed calendar time; all missing intermediate marks fail; v2 zero-cash endpoints reconcile with existing interval formula.

### Task1: Daily-path arithmetic and integration

- [ ] Add failing tests for initial loss/cost, constant units, cash elapsed time, invalid marks/order, insufficient funding; add opt-in integration checks to existing nonflat fixture.
- [ ] Add etf_paths.path_metrics(reference,weights,marks,cost_bps,cash_rate) with exact asset identity, positive marks, aware increasing clocks, nonnegative unlevered weights/fees/cash; return every marked NAV, anchored drawdown, final return, max drawdown and initial turnover.
- [ ] Extend etf_rehearsal.run(...,daily_paths=False) and CLI --daily-paths. Opt-in exact21points, same endpoints, three cash cases; no default behavior change.
- [ ] Verify RED/GREEN; document bilingual meaning and reproduction.

### Task2: Evidence run and delivery

- [ ] Recompute sealed Flex diagnostics, write private daily table and official-input gap list; no eligibility certificate.
- [ ] Run all historical cases from retained source bytes, preserve costs/cash/drawdown and limitations; prepare initial future checkpoint instructions without invented record.
- [ ] Write bilingual private strategy brief with actual placeholder state, candidate rules, missing approvals and stop conditions.
- [ ] Full tests/static, fresh review, exact-head CI; standing-authorized merge and deployment verification; retention and task-only cleanup.
