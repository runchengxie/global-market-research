# ETF data and historical calculation rehearsal

[简体中文](etf-rehearsal.zh-CN.md) · [Candidate cycle](research-candidates.md)

Run actual calculations without relabeling them as an accepted strategy. The offline rehearsal reuses the existing one-interval shadow arithmetic, keeps all three candidates and 0/10/25bp fee cases, and never calls a broker or changes a data/ledger acceptance gate.

## Sources and meaning

The bounded local inventory located legacy USD/SGD daily MIDPOINT CSVs, whose available_at fields are empty. It did not establish usable USMV history in the checked project roots. The current shared data platform is primarily an A-share owner; its PIT assets are not automatically suitable for a U.S. ETF. These are scoped findings, not global absence claims.

Four bounded credential-free public chart requests retained USMV,1321.T,USD/SGD and USD/JPY bytes privately, with request ranges, receipt times and hashes. This is a diagnostic fallback, not a production provider integration, verified historical publication record or grant of publication rights. The offline parser verifies source seals, symbol/currency, arrays, order, duplicates and positive finite values. It exposes null rows and out-of-range exclusions. In the acquired snapshot each FX response appended a current quote beyond the requested historical end; those rows are excluded rather than allowed into historical calculations. No missing core SMA/endpoint value is forward-filled.

[Yahoo's adjusted-close description](https://help.yahoo.com/kb/SLN28256.html) includes split and dividend adjustments. This exercise constructs vendor-adjusted opening units as open × adjusted_close / close and does not add dividend cash again. That is an adjusted-price return proxy, not an executable opening price, proof of historical adjustment availability or a certified dividend-reinvestment ledger.

## Fixed historical exercise

The three already-exposed signal dates are April1,July1,October1,2026. Each signal uses exactly200 completed XNYS sessions through that close, enters at the next modeled US open and exits20open-to-open intervals later. The original reference stock weights are from the retained November6 report; applying those weights to earlier windows is hindsight. No historical performance here represents actual earlier account decisions or independent out-of-sample evidence.

A keeps both reference stocks, B starts at50%USMV, C starts at0%/50% based on the initial close strictly above SMA200. The Japanese reference uses its last completed adjusted close at each US endpoint; FX uses the last reported daily open at/before that endpoint, with a72hour age cap. SGD per JPY = SGD per USD ÷ JPY per USD. Endpoint event times and values are retained. Scheduled closes and chart bar timestamps are modeled event clocks, not independently proven publication times or simultaneous tradable quotes.

All27cases call the same plain arithmetic used by the shadow evaluator. Initial fee = sum(abs(candidate−reference stock weights)) × bps/10000. The zero-return residual must fund that cost. Holdings are constant within each interval, with no recurring rebalancing, borrowing, terminal liquidation, tax, impact or financing model. This does not produce a daily NAV/drawdown account. In particular, the standalone real-ledger corporate-action/timing gate remains unchanged; never mark real observations synthetic or add a trusted-action flag to obtain a passing replay.

## Reproduce from retained external bytes

The schema is `competition.etf_rehearsal_inputs.v1`, with `core_conid`, `japan_conid` and exact `sources` keys usmv/japan/usdsgd/usdjpy. Each source record has an absolute external path and SHA256. Source parent directories must be sealed and contain the collection receipt with matching symbol, received status, hash and requested range; the input manifest directory is sealed too. Rehearsal requires the reference snapshot to contain exactly USMV/USD and1321.T/JPY, with SGD base currency. Other portfolios need a separately specified adapter, not silent asset removal.

```bash
python -m competition_tools.competition_review.etf_rehearsal \
  --manifest /external/sealed-inputs/manifest.json \
  --snapshot /external/sealed-flex-bundle \
  --output /external/new-rehearsal
```

Use the locked root `daily-data` profile. This command is offline. Outputs are new, external, sealed and bilingual; raw licensed/provider/account records stay private. Private results retain every case, SMA decision, as-of mark, excluded row count, input hash and limitation. Do not select a winner from this exercise or revise the frozen future cycle after inspecting outcomes.

## Ranker and first-cycle follow-up

Tracing the actual DailyWatch20 code identified prepared-feature/forward-price label policies, a model factory and persisted-model lifecycle. Expected publication artifacts include model.ubj, model_metadata.json and selection_receipt.json with compatibility and hash checks. Financial-state ranking experiments predict a different target from the declared relative stock-return strategy. Source reuse, trained artifacts and account/declaration binding are three distinct questions. Bounded filename checks and source hashes are retained privately; missing artifacts in those roots do not establish absence on other team systems. No model is deserialized, trained or copied into execution.

The first future cycle retains its initial November9close+30-minute deadline and November10entry. New historical bytes support diagnostic calculations, but do not create the November9close receipt, verify all source/action/FX semantics or confirm actual policy. The current interval remains pending. If required evidence misses the frozen deadline, record blocked/missing and create a separately frozen later cycle; never backfill or silently shift this one.
