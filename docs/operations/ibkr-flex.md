# Read-only IBKR Flex reporting

[简体中文](ibkr-flex.zh-CN.md) · [Competition review](competition-review.md)

Flex retrieves a saved reporting query with its Current Token and Query ID. It does not need TWS/Gateway or a brokerage login for each retrieval. It returns statement data, not real-time position updates. [IBKR configuration](https://www.interactivebrokers.com/docs/web-api/flex-web-service/client-portal-configuration)

Create one private JSON file under `CONFIG_ROOT/projects/global-market-research/ibkr-flex.json`, outside Git. Keep it owner-private (0600 on POSIX; equivalent owner ACL on Windows):

```json
{
  "token": "",
  "query_id": "",
  "expected_account": "",
  "account_ref": "competition-paper",
  "base_currency": ""
}
```

Fill the token and query as strings, preserving quotes. `account_ref` is a reporting alias. Discovery can run before the expected account is filled; regular collection requires an explicit exact account ID. Base currency may stay empty until reported metadata establishes it; unknown currency remains unknown and no automatic NAV weight or FX conversion is performed. Once configured, a mismatching account or currency blocks collection. The collector does not generate/rotate tokens or modify query templates. Linked accounts depend on the query's account selection. [IBKR token scope](https://www.interactivebrokers.com/docs/web-api/flex-web-service/client-portal-configuration/enable-and-create-access-token)

## Configure the report

Use an **Activity Flex Query in XML format**. For holdings, include Open Positions with **Summary** detail and Account ID, Report Date, Symbol/Conid, Currency, Quantity, Mark Price, Position Value, Multiplier and FX Rate to Base. Account Information needs only Account ID and base Currency. For reconciliation include Trades, Cash Transactions, NAV Summary in Base; Corporate Actions, cash balances and currency conversions support a fuller review. Select fields and accounts deliberately in Client Portal; this CLI does not edit the query.

[Open Positions fields](https://ibkrguides.com/reportingreference/reportguide/open%20positionsfq.htm) distinguish Summary from Lot. The parser does not add LOT, ORDER, symbol summaries and execution rows together. Reported position values stay in their source fields; the broker's Percent of NAV field must not be assumed to mean a whole-account weight.

## Manual commands

Install the root package using its locked test profile or a retained release wheel. These commands create no scheduler:

```bash
python -m competition_tools.competition_review.flex_cli check-config \
  --config "$CONFIG_ROOT/projects/global-market-research/ibkr-flex.json"
python -m competition_tools.competition_review.flex_cli discover \
  --config "$CONFIG_ROOT/projects/global-market-research/ibkr-flex.json" \
  --output "$DATA_ROOT/global-market-research/operations/ibkr-flex/<new-discovery>"
python -m competition_tools.competition_review.flex_cli collect \
  --config "$CONFIG_ROOT/projects/global-market-research/ibkr-flex.json" \
  --from-date 2026-10-26 --to-date 2026-11-06 \
  --output "$DATA_ROOT/global-market-research/operations/ibkr-flex/<new-collection>"
python -m competition_tools.competition_review.flex_cli inspect \
  --config "$CONFIG_ROOT/projects/global-market-research/ibkr-flex.json" \
  --report /external/prior-report.xml \
  --output "$DATA_ROOT/global-market-research/operations/ibkr-flex/<new-inspection>"
```

Discovery saves account/currency/period metadata privately, without the unbound raw report or positions. Inspect performs no network call. `--from-date` and `--to-date` must be supplied together; otherwise the saved query's period applies. Check the returned period and row dates: a requested range does not establish daily coverage. Use completed reporting days for retrospective analysis.

The client uses fixed HTTPS SendRequest/GetStatement endpoints, v3, ignores the response URL, rejects redirects and bounds response size/polling. It requests generation once, waits ten seconds between limited retrieval attempts and stops on transport/auth/permission errors. It does not switch credentials or immediately retry HTTP rate-limit errors. Avoid overlapping processes sharing a token, including other consumers. [Generate](https://www.interactivebrokers.com/docs/web-api/flex-web-service/using-flex-web-service/generate-the-report) · [Retrieve](https://www.interactivebrokers.com/docs/web-api/api-reference/get-statement)

Successful collections contain exact `report.xml`, `observation.json`, `ledger.json`, a credential-free receipt and a seal in a new 0700 directory with 0600 files. Existing output directories are never overwritten. A blocked request records only a sanitized code; no raw service error or credential-bearing URL is logged. The seal detects later file changes, not broker/source authenticity. Private account IDs appear only in the authorized raw/discovery data, never CLI summaries. Use a versioned installed release for any separately authorized scheduled job, never a temporary worktree.

## What the ledger can establish

The ledger counts unique **execution records** and broker order identifiers separately. One order may have many partial fills. It groups contracts by conid, flags missing identity, validates execution dates against each report period, deduplicates identical IDs and blocks conflicting IDs; correction-related/nonstandard executions require review. Commission currencies stay separate. Cash transaction IDs are deduplicated. The stock exposure proxy is gross reported stock value divided by reported NAV for the supplied reporting dates, not the official daily position rate. Missing NAV dates are not filled. Do not map this proxy into an official statement bundle without reviewing the organizer's formula/calendar.

Absent Open Positions means missing holdings evidence, not zero positions. Trades do not establish opening or current positions without opening balances, corporate actions and coverage. Period-end positions do not prove daily history or flat days. NAV changes alone are not flow-adjusted strategy returns. No report creates targets, orders or execution authorization. Continue with the [private review](competition-review.md) after provenance, definitions and account binding are confirmed.

## Observed stock/cash snapshot

Collection and offline inspection also emit `snapshot.json`. It selects the latest date present in stock/NAV observations and requires matching NAV rather than falling back to an older convenient date. It checks quantity × mark × multiplier against local position value, converts with the row's explicit FX, and compares stock net/gross values with NAV before emitting observed weights. These are measured weights, not portfolio targets. LOT rows are excluded. Incomplete identity/marks, model ambiguity or value mismatches block stock weights.

Cash uses `CashReportCurrency` with Currency detail and a matching explicit end date. BASE_SUMMARY is excluded from currency addition. Negative balances remain negative. Only same-date from-currency→base ConversionRates are used: no inversion, cross-rate chaining or stale-rate carry. Cash totals are compared with NAV cash. The NAV bridge separately shows stock, cash, interest and dividend accruals plus a residual; nonzero unsupported assets remain visible even if they offset numerically. This is a named-component check, not a general accounting engine.

Fixed tolerances are 0.01 local currency units for mark/value, 0.02 base currency units for totals/bridge and 1e-8 × max(abs(FX),1) for position/rate consistency. The raw values and residuals remain inspectable; the tolerances are not economic risk limits. Missing sections or unsupported cash-only/model scopes yield needs_review rather than fabricated zero positions. Reconciled status does not certify full daily history, current real-time positions, platform binding or official eligibility. It never creates orders. With BreakoutByDay=No, an aggregate report's period-end holdings must not be described as the complete daily holding history.
