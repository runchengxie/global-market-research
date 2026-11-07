# Private competition review

[简体中文](competition-review.zh-CN.md)

Preserve registration evidence outside Git, then compare the declared method with dated implementation and account evidence. A strategy name does not establish its implementation. User-provided platform text is attributed evidence, not independent verification.

Run the offline inventory with the `daily-data` optional profile:

```bash
python -m competition_tools.competition_review.cli \
  --declaration-root "$DATA_ROOT/global-market-research/operations/competition-declaration/<record>" \
  --snapshot-root "$DATA_ROOT/global-market-research/operations/account-dashboard" \
  --output "$DATA_ROOT/global-market-research/research/competition-review/<new-run>"
```

The declaration directory contains declaration.json, declaration.md, declaration.zh-CN.md and receipt.json listing the SHA-256 of those three files. Exclude credentials and account identifiers before capture. Outputs are private, newly created and sealed. A seal detects later changes; it does not verify the underlying source.

The CLI inventories existing snapshots without connecting to a broker. Snapshot gross value/NAV is an observation proxy, not an official daily position rate. Same-time conflicting snapshots are excluded; missing or partial days remain unknown. XNYS and XTKS are illustrative calendars, not an official global-account calendar. Without `--statement-bundle`, the CLI supplies no complete daily facts. The optional normalized bundle accepts reviewed fractional rates and provenance; there is no arbitrary Flex XML importer.

Under [organizer rule 4.2](https://fundconnecthk.com/quant-league/legal/competition-rules/), the full-period mean daily position rate must be at least 50% with at most ten flat trading days, **or** mean daily turnover must be at least 100%. Intraday close-out alone is not a flat day. These are award/defense candidacy conditions, not a universal requirement to rebalance frequently. Elapsed-period arithmetic does not certify full-period eligibility. Confirm the calendar, rate definitions and complete daily statements with the organizer.

The draft retains missing policy parameters as null. `review_decision` evaluates supplied evidence only: unconfirmed policy, account mismatch, missing/stale/future sources or noncausal timestamps block the review. A complete synthetic case may yield maintain_candidate or review_required; neither authorizes trading. Policies require a benchmark and declaration/model hashes, typed positive limits and nonnegative integer buffers. Each source supplies effective_at and available_at; effective ≤ available ≤ decision, with effective-age limits. Scores must name the PIT/universe/model parent hashes; targets must name the score parent hash. Source hashes bind supplied references, not semantic correctness or external authenticity. It does not train or validate a Ranker, verify PIT completeness, or generate executable targets.

Before allocation recommendations, establish a benchmark, PIT universe and factor provenance, model checkpoint, dated scores, Top-K/buffer definitions, marked current weights, risk limits, fees and FX. Keep price-only baselines distinct from a declared fundamental Ranker. Do not infer current concentrations from historical average cost. Platform collection freshness and local collector freshness are separate checks. Preserve edit locks and follow organizer procedures for declaration changes.

## Reviewed daily statements

Supply `--statement-bundle /external/inputs/bundle.json` to include an explicitly reviewed export. The normalized JSON schema identifier is `competition.statement_bundle.v1`. Required fields:

| Field | Meaning |
| --- | --- |
| `declaration_sha256`, `account_ref`, `base_currency` | Captured declaration hash, pseudonymous account binding and three-letter base currency |
| `rate_unit`, `reviewed_by` | Must be `fraction`; reviewer attribution (not an authentication signature) |
| `sources` | Nonempty list of `{id, path, sha256}`; paths are relative to the bundle directory and must stay inside it |
| `calendar` | `{id, status, full_period, period_start, period_end, source_ids, sessions}`; status is `unconfirmed` or `organizer_confirmed`, full_period must be true |
| `calendar.sessions` | Ordered unique `{session_date, opens_at, closes_at}`; aware timestamps, nonoverlapping windows inside the full contest period |
| `definitions` | `position_rate`, `turnover_rate`, `flat_day`, each with `{status, description, source_ids}` |
| `days` | Unique completed-session labels with `complete_day`, fractional rates or null, `had_any_position`, `had_any_trade`, `covered_through`, `available_at`, `source_ids` |

The full contest interval is 2026-10-25T16:00:00Z through 2027-01-26T22:00:00Z. Labels must fall within the contest civil-date envelope (UTC−12 to UTC+14) and no more than one calendar day from either window endpoint; this plausibility check does not choose an official labeling timezone. A complete-day claim must cover its session close and be available by the review time. Partial days stay unknown. Missing sessions are included in elapsed denominators as unknown, not dropped. Rates may exceed one for leveraged accounts, but the unlevered future-position scenario is then disabled. Daily overrides of account/currency must match the bundle. Every referenced file hash is checked before a new output is created. The supplied calendar completeness, metric definitions and reviewer identity remain attributed assertions; `organizer_confirmed` is not independently authenticated by this tool. No output certifies award eligibility.

For the existing daily reviewer, pass `--policy /external/policy.json --decision-inputs /external/decision-inputs.json` together. Both must bind the captured declaration hash; when a statement bundle is supplied, both account references must also match it. This evaluates supplied weights and causal source references only; it does not reconstruct broker positions or Ranker outputs. Output includes `policy-review.json`; without these arguments it retains `policy-draft.json`. The bilingual report and audit.json reflect the supplied statement/review statuses.

## Export and recovery sequence

1. Obtain the organizer's full daily calendar, position/turnover definitions, flat-day treatment and scoring export. Preserve the original file and its date/time. Confirm account binding privately.
2. Obtain a read-only [IBKR Activity Flex report](https://ibkrguides.com/reportingreference/reportguide/activity%20flex%20query%20reference.htm) covering the whole elapsed period: Trades, Cash Transactions, NAV Summary in Base and marked Open Positions/FX fields needed for reconciliation. Field availability depends on the configured query. No token or login belongs in the bundle.
3. Reconcile base-currency NAV, marked holdings, gross turnover, trades/fees, cash transfers and report date coverage. End-of-day zero holdings alone cannot establish a flat day; activity and carried positions matter. Do not invent the organizer formula from available columns.
4. Have a reviewer prepare the normalized bundle with source hashes and reviewed definitions. Keep unresolved definitions unconfirmed. A source receipt is evidence of file identity, not correctness.
5. Re-run into a new private directory; compare coverage and blockers with the previous sealed report. Only after current marks and declaration-aligned model evidence exist should allocation changes be assessed.

The implementation search must distinguish dataset acquisition checkpoints, price/CNN research and synthetic fixtures from a trained fundamental Ranker. Preserve the search scope and exclusions; an absent filename is not proof that no team member has the missing implementation.
