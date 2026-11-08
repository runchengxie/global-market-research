# Three research candidates and the first observation cycle

[简体中文](research-candidates.zh-CN.md) · [Prospective diary](prospective-strategy.md)

Compare a small set of explicit hypotheses before expanding models. These rules are implementer proposals for offline research, not approved account allocations, registered strategies or executable targets. The 50% weight, 200-observation average and cost scenarios were chosen for transparency, not optimized on returns. Start with B as the simplest testable candidate; C tests one incremental initial filter, not a new architecture.

| Candidate | Exact first-interval rule | Question |
| --- | --- | --- |
| A: observed-stock reference | Use the reconciled report's stock weights at the common hypothetical entry, then hold units; normalize residual to zero-yield base-currency cash | What does the observed stock exposure explain? |
| B: fixed half | One initial hypothetical change to 50% explicitly selected USD core equity/ETF and 50% modeled residual; hold units for the full interval | Does a transparent lower exposure improve the risk/turnover tradeoff? |
| C: initial trend half | At the initial cutoff, compare the completed-day split-adjusted USD close with the arithmetic mean of the last 200 completed observations, including that day. Strictly above: 50% core; equal/below: 0%. Then hold units for the full interval | Does one predeclared initial filter add anything over B? |

Missing or unverified history blocks C; it does not mean cash. No candidate rebalances daily. A is a normalized research reference, not literal actual-account buy-and-hold: actual cash spans currencies and accruals. Current stock weights are historical references, not verified future-entry holdings. The existing one-interval evaluator can assess initial-weight hypothetical arithmetic, not automatically run a multi-period account or dynamic trend backtest.

## Timing and limits

Freeze before the initial signal; use a declared XNYS research-session date and an explicit held positive USD stock conid. Do not infer the core from the largest holding. Initial signal cutoff is 30 minutes after that session close; hypothetical entry is the next session open. Twenty subsequent daily close+30-minute checkpoints monitor data and decisions, and exit is the next open after the twentieth checkpoint. Holidays and half-days come from the locked exchange_calendars version with a schedule hash. This is a research calendar scenario, not the official contest calendar or qualified broker session evidence.

For a first declared session of 2026-11-09: signal cutoff 2026-11-09 21:30 UTC; entry November 10 14:30 UTC; checks November 10–December 8; exit December 9 14:30 UTC. November 26 is excluded; November 27 review is 18:30 UTC after its half-day close. Future checks/results have not occurred merely because the plan exists.

Long-only, no leverage or derivatives. B/C initial stock exposure is at most 50%; A retains its observed unlevered reference rather than being forced to satisfy that candidate limit. Freeze initial stock-weight cost scenarios 0/10/25 basis points; report all, never choose the fee or winner afterward. Model residual return as zero consistently. These are scenarios, not actual financing/FX/tax/commission estimates. No ongoing rebalances or terminal liquidation are simulated by the one-interval calculation. Primary reference A; risk-matched reference B. Any later strategy change needs a new future protocol/version; never overwrite this one.

Each checkpoint records available inputs, timestamps, unchanged candidate definitions and blockers. Require the latest completed signal session and verified price/identity/action/FX semantics. Missing, late, conflicting or unreconciled data block a new shadow decision; do not substitute a zero signal, silently move entry dates or submit liquidation orders. Preserve missed observations and all candidates. Process acceptance requires 20 checks and zero causal/reconstruction errors. One cycle is a process pilot; it cannot establish statistical superiority or approve adoption. Daily drawdown/turnover/exposure diagnostics additionally require a separately reconciled valuation series.

## Generate the private proposal

```bash
python -m competition_tools.competition_review.research_cycle \
  --snapshot /external/sealed-flex-bundle --output /external/new-cycle \
  --core-conid '<explicit-conid>' --first-session 2026-11-09 \
  --material-deadline 2026-11-13T10:00:00Z
```

The CLI uses current UTC and rejects expired cutoffs, past signal deadlines, an invalid/core-not-USD holding, leveraged references or a cycle outside the contest envelope. It writes a new sealed proposal.json and bilingual report, no targets.json, order or scheduler. Readiness remains blocked until verified input evidence and future observations exist. Use the existing [shadow diary](prospective-strategy.md) to capture actual prospective records and exact outcome bindings. Do not fabricate a fundamental model or mark an actual policy confirmed just to unblock this research proposal.

The core may be an ETF already held by the account; it still needs provider/security-identity confirmation. For example, [USMV's issuer objective](https://www.ishares.com/us/products/239695/USMV) targets U.S. lower-volatility equities. That does not make it a global allocation or a separately trained fundamental Ranker, and this example is not a product recommendation.

## Finish the model-material review

Use a bounded read-only inventory of tracked source in relevant strategy/provider/model repos, with exact revisions, file hashes, working-tree status and exclusions retained privately. Related local repositories contain real XGBRanker/fundamental implementations. Distinguish generic model adapters, prepared-feature rankers and financial-state prediction experiments from a declaration-aligned future-stock-return model. The existence of source does not establish a trained checkpoint or the basis of account orders; an unbound checkpoint does not establish source absence.

Propose November 13, 2026 18:00 Hong Kong time (10:00 UTC) as the material cutoff, subject to team acknowledgement. Required deliverables:

- Declaration identity, intended target/market/universe and responsible owner.
- PIT inputs, financial vintage/availability and historical security identities.
- Training source revision, immutable fitted checkpoint and training cutoff.
- Dated scores, reviewed prospective policy/targets and parent hashes.
- Contemporaneous decision/account/order references linking the declared model to actual holdings.

At cutoff, unresolved binding stays unverified. Follow the organizer process for any prospective actual-policy/declaration change; do not rewrite historical rationale. This task sends no team/organizer message and assumes no team acknowledgement.

## Data work before more capacity

Audit whether existing owner datasets actually include the chosen core, required adjusted history, dividends and base FX. A fixed ten-stock snapshot cannot be assumed to cover a held ETF. For crypto sentiment, provider-owned formula/version, first publication, revision policy and retrieval/raw hashes remain required; new first-seen receipts cannot retroactively establish historical availability. Preserve the frozen price-only forward producer. For MoE, reuse the deferred objective study and its six data/holdout evidence classes; no new architecture fits are justified by the proposal alone. Keep all three lanes separate from executable competition handoff.
