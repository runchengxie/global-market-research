# Daily platform and broker evidence table

[简体中文](daily-reconciliation.zh-CN.md) · [Competition review](competition-review.md)

Produce a missing-aware daily table before interpreting eligibility or strategy activity. The command recomputes the ledger from a sealed reconciled Flex snapshot, verifies the declaration receipt and optionally consumes the existing [reviewed statement bundle](competition-review.md). It never logs in, downloads account data, infers organizer formulas or submits orders.

```bash
python -m competition_tools.competition_review.daily_reconciliation \
  --declaration-root /external/captured-declaration \
  --snapshot-root /external/sealed-reconciled-flex \
  --output /external/new-daily-table
```

Without `--statement-bundle /external/reviewed/bundle.json`, platform columns remain null. Output includes a sealed `reconciliation.json` and bilingual reports. It retains all reported NAV/execution dates and, when supplied, every elapsed calendar label, including partial/missing days. Executions are counted once per source trade identifier; zero reported records is not proof of no actual trading. An existing ledger.json must reproduce exactly. Snapshot receipt/time/hash/account checks precede output.

A supplied bundle must bind the same declaration hash, pseudonymous account and base currency, reference hashed raw files, use fractional rates, and pass the existing calendar/coverage/availability checks. This is reviewed normalization of preserved evidence, not a new raw CSV parser. Keep absent data absent; do not fill example rates. Missing inputs, tampering or mixed accounts must not become confirmed daily facts.

Broker stock gross/NAV is a proxy, not the official position rate. The reported numeric proxy-minus-supplied gap is descriptive: zero does not prove agreement and nonzero does not prove error. Same date labels do not authenticate timezone/session alignment. Source/organizer_confirmed labels remain attributed assertions. No output certifies official eligibility, changes the participation scorer, or authorizes trading.

## Obtaining the platform evidence

In the owner-supplied platform layout, open **Strategy management → strategy details → Position rate and turnover rate**. Look for a visible export/download control or chart menu; these instructions do not assert that the platform offers one. If a table is visible, retain its full date range, units and completeness. A chart or screenshot may document displayed values but is not a complete raw daily export, calendar or formula specification.

If no export is available, ask the organizer for the account-bound daily table and calculation definitions. Keep that reply and original attachment outside Git. Suggested request (draft only; this tool sends nothing):

> Please provide our strategy's daily position rate, daily turnover rate, cumulative flat-day details and the underlying calculation definitions, including the calendar/denominator, timezone, intraday positions, FX/derivatives, and whether rates are fractions or percentages. Please also clarify the process for supplementing the strategy description when it differs from actual placeholder holdings.

Do not share the Flex token or broker login to obtain this export. An optional local browser connection can be used only when available; unavailable browser access does not authorize private API discovery or searching unrelated credentials.

## Prospective and holiday work

The [candidate observation](candidate-observations.md) uses its frozen future window; preparing a table is not a completed future observation or an installed schedule. Keep missing or late captures missing. For [daily ETF paths](etf-rehearsal.md), investigate stale Japanese marks by comparing the last chart session with the last scheduled completed XTKS session. A holiday-consistent last mark can still fail the frozen 72-hour cap. Record that distinction separately; do not change the cap or overwrite the blocked historical result after inspecting returns. Any alternative valuation policy needs a separately frozen research version, not retroactive acceptance.
