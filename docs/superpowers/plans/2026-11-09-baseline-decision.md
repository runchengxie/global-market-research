# Baseline decision implementation

Spec: [common-ledger design](../specs/2026-11-09-baseline-decision-design.md).

1. Add synthetic regression tests for lagged signals, buy-and-hold drift, entry/exit fees, initial-wealth drawdown, unavailable model rows and denominator completeness. Run them before implementation.
2. Implement a sealed offline study adapter under competition_review using existing source parsing, external paths and cash accounting. Preserve source/freeze chronology and annual/partial episode identities. No optimization or provider calls.
3. Seal a private protocol bound to retained source bytes before outcomes. Run once into a fresh task namespace. Recompute every buy-and-hold trajectory with an independent closed-form reference. Preserve all cases and failures.
4. Produce bilingual private results and a decision brief separating baseline arithmetic, Ranker/model evidence, prior retired volatility configuration, financing and participation unknowns. Keep public docs methodological and exclude private metrics/paths.
5. Validate root tests/lint/boundaries, obtain independent review, merge with required CI and verify deployment if triggered. Retain inputs/results/validation under the task inventory, then clean this task only.
