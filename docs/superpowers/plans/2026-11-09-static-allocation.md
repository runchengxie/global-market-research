# Static allocation implementation plan

Goal: test fixed diversified sleeves and low-frequency policies with honest timing and accounting.
Architecture: equity-lab standalone CLI consumes external JSON panel/protocol and writes an immutable JSON ledger; reuse portfolio.cash_rebalance. Root and execution remain untouched.
Spec: ../specs/2026-11-09-static-allocation.md

Constraints: stdlib replay, no new dependencies, USD adjusted-unit diagnostic only, no broker or private data in Git.
Review focus: incomplete panels, malformed numbers/dates/weights, next-open lookahead, entry/exit fees and initial losses, overwrite protection.

1. Add tests/test_static_allocation.py first. Verify import fails, then implement backtest/static_allocation.py replay(panel, target, policy, fee_bps, threshold=.05). Check analytical constant-price fees, cash funding, holding drift, monthly timing, previous-close drift timing, anchored drawdown, strict panel validation and boolean rejection.
2. Add module CLI --input --protocol --output: validate full case matrix, record input SHA256, refuse overwrite, retain marks/trades and explicit limitations. Exercise malformed protocol and CLI round-trip.
3. Freeze external protocol before acquisition. Acquire raw USMV/IEF/IAU with receipts, verify exact XNYS sessions and positive prices, materialize aligned panel. Run all27cases, save continuous/annual outcomes and real-account reported bridge interpretation separately. Fail gaps closed; no post-outcome retuning.
4. Update bilingual leaf usage docs. Run leaf locked dev sync, Ruff and full tests; root Ruff and workflow boundaries. Fresh whole-branch review, exact-head CI, merge under standing authorization; retain source/results/validation/runtime and clean only this task worktree/branch.
