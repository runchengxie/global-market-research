# Crypto factor provenance review

[简体中文](crypto-factor-provenance.zh-CN.md) · [Crypto evidence](crypto-evidence.md)

Two indicator meanings are now documented; historical publication timing remains unverified. The retained daily snapshot still supports exploratory proxy joins, not point-in-time sentiment trading claims.

| Indicator | Current public documentation | Remaining gap |
| --- | --- | --- |
| CO-A-02-03 | Net positive-minus-negative sentiment proportion | Exact historical methodology/version and publication time |
| CO-S-01-01 | Standardized deviation of sentiment from its historical norm | Standardization window, historical version and publication time |
| CO-S-01-05 | Definition not independently confirmed in this review | Definition, version, publication time |

Sources reviewed on2026-11-07: [official CO-A-02-03](https://cryptoracle.gitbook.io/cryptoracle-docs/cryptoracle-open-api-v2.1/api-list/co-real-time-data/indicators/co-a-02-03), [official CO-S-01-01](https://cryptoracle.gitbook.io/cryptoracle-docs/cryptoracle-open-api-v2.1/api-list/co-real-time-data/indicators/co-s-01-01), and [official catalog](https://cryptoracle.gitbook.io/cryptoracle-docs/co-indicator-repository). The current pages redirected to documentation paths named `co-private-data`; reading these public pages used no private API or credentials. The API examples support daily intervals and show period open/close fields. Those fields do not establish first publication, retrieval, revision timestamps or a UTC interpretation. The catalog advertises more granular updates for some indicators; that does not establish our entitlement or the grain of the retained daily snapshot.

The review used the documentation browsing service. Four additional bounded direct documentation downloads returned HTTP errors; these failures are retained rather than reported as downloaded source archives. No provider data API was called. The existing normalized snapshot has only asset, indicator, period start/end and value; adding delay cannot manufacture missing publication history. The24/72/192-hour joins therefore remain hypotheses.

The next admissible input is a provider-owned, versioned data contract stating indicator formula/version, interval boundaries/timezone, first availability, revision policy, retrieval timestamp and raw-response digest. Actual future first-seen receipts can establish future availability, but cannot retroactively establish it for old rows. Until then, continue price-only prospective forecasts and keep the verified historical factor arm blocked.
