# Nodit daily chain statistics

[简体中文](nodit.zh-CN.md) · [Providers](environment-and-providers.md)

Manually collect Ethereum mainnet daily active-account and transaction counts with Python's standard library. These are research inputs, without demonstrated predictive value or competition product eligibility; they do not supply equity point-in-time fundamentals.

## Collect and verify

Add `NODIT_API_KEY=` to the existing private project `.env` outside source and fill it locally. On POSIX use file mode `0600`. Supply the absolute path explicitly: only that assignment is parsed, never executed. Do not put credentials in URLs or command arguments. Set `CONFIG_ROOT` and `DATA_ROOT` in your shell first.

```bash
python -m competition_tools.datasets.nodit collect \
  --credential-file "$CONFIG_ROOT/projects/global-market-research/.env" \
  --start 2026-08-18 --end 2026-11-15 \
  --output "$DATA_ROOT/global-market-research/research/nodit/<new-run>" \
  --max-requests 2 --max-cu 300 --max-seconds 120
python -m competition_tools.datasets.nodit verify \
  --output "$DATA_ROOT/global-market-research/research/nodit/<new-run>"
```

Use a new output directory each time. This example covers 90 inclusive UTC dates; adjust dates explicitly. At most 100 complete days are accepted, allowing 30 minutes for publication: at 00:29 UTC yesterday remains unavailable; at 00:30 it becomes eligible. Source-repository destinations and symlink paths are rejected. Output files are owner-private on POSIX.

## Unknown quota and bounded requests

The competition grant's quota and expiration may be unknown. Default and maximum per-run budgets are four requests, 600 **estimated** CU, 120 seconds and 1 MiB per response. The time budget is checked around network operations; socket timeouts are narrowed as time runs out, but blocking DNS/TLS/header/chunk processing can overrun. This is not a hard process deadline; when control returns after expiry, collection stops without publishing success or issuing another request. Successful collection uses two requests at the currently documented 150 CU each, separated by at least two seconds. These limits constrain one invocation, not concurrent runs, account-wide consumption or actual provider billing. They do not prevent provider-side overage charges if configured on the account. Establish the grant's terms before larger acquisitions. No subscription, auto-scaling or payment settings are queried or changed.

`receipt.json` records each attempt and estimated CU before I/O. HTTP errors including 401/403/429 and redirects stop immediately. Network failures retain uncertain-spend evidence. There are no retries, automatic resume, schedules or extra methods. Review a failed receipt before manually starting another invocation. Error bodies are never retained or echoed. Missing/duplicate/unexpected dates, negative/noninteger counts, invalid JSON and secret echoes block success. Safe successful responses with invalid statistics remain as raw evidence. Partial runs retain receipts and any safe raw responses but no success manifest.

## Retained evidence

A successful bundle contains `plan.json`, `receipt.json`, two `raw/*.json` files, `normalized.csv` and `manifest.json`. The plan freezes dates and budgets without credentials. CSV columns are `date,active_accounts,transactions`, ordered by date; these counts are not monetary trading volume. Offline verification checks the exact inventory, SHA-256, raw series and reproducible CSV. Hashes detect edits relative to the manifest; they do not authenticate the source or manifest itself.

Acquisition times do not establish historical first-publication times. Historical revision policy, point-in-time availability, wider coverage and usage rights under the competition grant remain separate evidence gaps. Results retain `accepted_research=false` and `execution_authorized=false`; no broker orders or strategy declarations change. The price endpoint is outside this collector: Nodit documents periodically updated CoinMarketCap prices, which must not be treated as independent real-time exchange prices.

Official references: [authentication](https://developer.nodit.io/en/data/data-api/api-key/), [active accounts](https://developer.nodit.io/en/data/data-api/getdailyactiveaccountsstats/), [transactions](https://developer.nodit.io/en/data/data-api/getdailytransactionsstats/), [CU costs](https://developer.nodit.io/en/guides/compute-unit/), [token prices](https://developer.nodit.io/en/data/data-api/gettokenpricesbycontracts/).
