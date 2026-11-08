# Prospective strategy and shadow observations

[简体中文](prospective-strategy.zh-CN.md) · [Competition evidence](competition-review.md)

Start by drafting the actual intended policy, then record decisions before evaluating later observations. Neither the current portfolio nor a platform strategy name establishes a trained Ranker or an approved risk budget. These manual tools create private offline evidence; they do not activate trading, schedules or platform edits.

## Draft and record

Use the [file-backed case](competition-review.md#file-backed-strategy-cases) already bound to the declaration and reconciled Flex snapshot:

```bash
python -m competition_tools.competition_review.shadow_cli prepare \
  --case /external/case.json --output /external/new-charter
python -m competition_tools.competition_review.shadow_cli record \
  --case /external/case.json --output /external/new-entry
python -m competition_tools.competition_review.shadow_cli nav \
  --snapshot /external/sealed-flex-bundle --output /external/new-nav-bridge
```

Every output must be new, external to source and nonoverlapping with input evidence. Outputs are sealed with restricted Unix permissions. A seal detects changes; local clock timestamps are not independently authenticated. The CLI has no backdating flag. `record` uses current UTC and labels the holdings report date separately. A blocked record means missing evidence, not an instruction to hold. Run manually whenever a new complete account report and policy review are available; no scheduled job is installed.

The draft leaves approach, benchmark, target weights, risk limits, review calendar/owner and confirmation empty. Specify investment universe, allocation rationale, maximum name/sector/gross exposure, cash/FX treatment, turnover/cost limits, review triggers and pause conditions before confirmation. Observed weights remain descriptive. Recover existing declared fundamental-Ranker inputs, model and dated scores if they exist. Otherwise document the actual intended policy prospectively and resolve declaration changes with the organizer under platform restrictions; do not invent historical rationale. No draft is automatically promoted to the confirmed case policy.

## Later paired observations

After an unblocked entry, supply an external JSON outcome with schema `competition.shadow_outcome.v1` and these fields:

| Field | Required meaning |
| --- | --- |
| `decision_sha256` | SHA256 of the sealed entry's decision.json |
| `account_ref`, `base_currency` | Exact recorded alias and currency |
| `start`, `end`, `available_at` | Aware times: recorded_at ≤ start < end ≤ available_at ≤ evaluation time |
| `returns` | Exact union of recorded current/target conids, each a finite signed base-currency total-return fraction ≥ −1 |
| `benchmark` | Exact benchmark identifier frozen in the recorded policy |
| `non_stock_return`, `benchmark_return` | Attributed finite total-return fractions ≥ −1, same interval/currency |
| `one_way_cost_bps` | Finite nonnegative initial linear stock trading-cost assumption, at most 10000 basis points |

```bash
python -m competition_tools.competition_review.shadow_cli evaluate \
  --entry /external/sealed-entry --outcome /external/outcome.json \
  --output /external/new-comparison
```

The recorded target file must still match its hash. Only nonnegative stock weights totaling at most one per variant are supported. The comparison assumes each recorded allocation at interval start, computes weighted security returns plus the residual non-stock sleeve, and deducts initial sum(abs(target−current)) × cost_bps/10000 for the target variant. It reports paired differences and benchmark excess. The residual includes cash/accruals, not real available funds. These are one-interval hypothetical calculations, not broker performance, execution replay or a multi-period backtest. No fills, cash flows, taxes, nonlinear impact, financing, ongoing rebalancing or terminal liquidation cost are simulated. Source returns and timestamps remain attributed. Do not treat a single favorable interval as evidence of superiority or concatenate entries with overlapping periods as independent samples. Freeze data, costs, benchmark, timing and selection rules before collecting multiple paired out-of-sample periods; preserve time dependence when assessing uncertainty. Missing future observations must remain missing.

## Explain reported NAV movements

`nav` verifies the Flex seal/raw hash, recomputes current holdings and compares the period-ending ChangeInNAV value with the same-date snapshot. It supports one unambiguous account/base-currency/period MTM-mode row, checks signed reported components to an absolute 0.02 base-unit tolerance and exposes omissions. Unsupported modes, unknown nonzero fields, conflicts or residuals fail before output. Identical repeated rows are deduplicated. Reported TWR is preserved raw, not recomputed or assigned inferred units.

The [IBKR Change in NAV reference](https://www.ibkrguides.com/reportingreference/reportguide/changeinnav_fq.htm) distinguishes profit modes and describes reported MTM and currency fields. This tool checks their arithmetic without asserting an independent economic price/FX split. MTM may include FX; separately displayed FX entries are not complete total currency attribution. Never add commission/cash/MTM-performance rows from other sections again. Booked interest and accrual changes may relate economically to another period. Full security-price versus FX attribution would require dated quantities, prices, FX, cash flows and transaction accounting reconciled on one consistent grid; this bridge does not claim that.

## Keep three research lanes distinct

| Lane | Next evidence | Boundary |
| --- | --- | --- |
| Competition | Prospective policy, declaration-aligned model chain, marked account, paired shadow periods | No automatic execution or qualification certification |
| Crypto | Price/sentiment availability and coverage, realistic costs, venue/product, simple price-only and sentiment-ablated baselines | Finer candles are not automatically independent samples; research does not authorize a competition product |
| MoE | Parameter-matched single-model, fixed-average/ordinary-ensemble controls, routing diagnostics, multiple seeds and forward periods | Architecture explanations and synthetic examples are not strategy performance |

Define the research question and acceptance protocol before selecting results. Existing leaf research packages retain their own data/timing/accounting assumptions; root tools consume files, not research imports. Promotion requires separate review of evidence and executable handoff, not a research-directory name or a favorable chart.

For a later evaluation, the case must supply `shadow_window: {start, end}` with aware times not earlier than recording. The entry freezes this window, the verified policy benchmark and the case one-way cost assumption. Outcome start/end, `benchmark` identifier and cost must exactly match. Missing registration permits a diary entry but blocks later evaluation; intervals and benchmarks cannot be selected after results.

The existing [crypto follow-up](../research/crypto-followup.md) already contains a 39-fit retrospective comparison: learned dense routing did not improve mean forecast skill over matched/equal controls. Its six-receipt forward audit is explicitly an as-of 2026-11-07 snapshot, not current monitoring. The useful next exploration is audit of additional retained forward observations under the frozen producer, plus provider-owned historical publication/version metadata; do not select a new winner from already inspected test dates or alter the active producer in this workflow.

For equities/MoE, the existing [objective study](../research/sequence-target-study.md) already defines classification-versus-return regression, matched/linear/equal/sparse controls, paired block intervals and a continuation rule. Reuse its sealed results and future-preparation gate rather than launching another architecture search from the competition diary. Its historical windows are exposed; a new future interval needs its own frozen protocol. These records establish concrete work to inspect, not a claim that MoE or sentiment improves competition returns.

For explicit candidate rules and a first dated cycle, see [three research candidates](research-candidates.md).
