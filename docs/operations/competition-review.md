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

The CLI inventories existing snapshots without connecting to a broker. Snapshot gross value/NAV is an observation proxy, not an official daily position rate. Same-time conflicting snapshots are excluded; missing or partial days remain unknown. XNYS and XTKS are illustrative calendars, not an official global-account calendar. The CLI intentionally supplies no complete daily facts. The pure `daily_rows` interface accepts reviewed fractional rates; there is no arbitrary Flex XML importer.

Under [organizer rule 4.2](https://fundconnecthk.com/quant-league/legal/competition-rules/), the full-period mean daily position rate must be at least 50% with at most ten flat trading days, **or** mean daily turnover must be at least 100%. Intraday close-out alone is not a flat day. These are award/defense candidacy conditions, not a universal requirement to rebalance frequently. Elapsed-period arithmetic does not certify full-period eligibility. Confirm the calendar, rate definitions and complete daily statements with the organizer.

The draft retains missing policy parameters as null. `review_decision` evaluates supplied evidence only: unconfirmed policy, account mismatch, missing/stale/future sources or noncausal timestamps block the review. A complete synthetic case may yield maintain_candidate or review_required; neither authorizes trading. Policies require a benchmark and declaration/model hashes, typed positive limits and nonnegative integer buffers. Each source supplies effective_at and available_at; effective ≤ available ≤ decision, with effective-age limits. Scores must name the PIT/universe/model parent hashes; targets must name the score parent hash. Source hashes bind supplied references, not semantic correctness or external authenticity. It does not train or validate a Ranker, verify PIT completeness, or generate executable targets.

Before allocation recommendations, establish a benchmark, PIT universe and factor provenance, model checkpoint, dated scores, Top-K/buffer definitions, marked current weights, risk limits, fees and FX. Keep price-only baselines distinct from a declared fundamental Ranker. Do not infer current concentrations from historical average cost. Platform collection freshness and local collector freshness are separate checks. Preserve edit locks and follow organizer procedures for declaration changes.
