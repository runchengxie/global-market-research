# BTC/ETH price and AIVIX evidence

[简体中文](crypto-evidence.zh-CN.md) · [Measured public page](https://runchengxie.github.io/global-market-research/research/crypto-evidence/)

The fixed 1h/4h Ridge screen does not support a prediction gain from the retained AIVIX factors. All learned arms have negative mean-fold MSE skill against the fit-only mean prior, and factor arms are worse than price-only in this snapshot. Most learned rules hold cash under the frozen 20bp hurdle. A zero median return is not evidence of profitable prediction. The experiment, data preparation and first pre-outcome forecasts are complete engineering records; historical availability and independent prospective evidence remain incomplete.

## Inputs and scope

The immutable BTCUSDT/ETHUSDT spot snapshot covers 2024-10-01 through 2026-10-01 exclusive: 17,520 hourly bars and 4,380 derived four-hour bars per asset, with raw USDT prices. Acquisition read 48 monthly ZIPs and 48 checksum files, transferred 2,028,208 response bytes and verified 5,747,170 expanded bytes. It took 96 attempts within the frozen 112-attempt/32MiB/64MiB/600-second limits. No credentials or private provider calls were used. Archives are verified before normalization; missing hours, wrong UTC grids, nonfinite OHLCV, unexpected ZIP members, invalid closes and timestamp-unit mismatches block the study. Four-hour bars require complete aligned groups.

[Binance's archive specification](https://github.com/binance/binance-public-data) documents interval support, checksum files, archive revisions and the spot timestamp switch to microseconds from January 2025. Preserve downloaded bytes and their checksums; a later download is a new input version.

The external owner retains 2,280 daily AIVIX records for BTC/ETH and three indicator IDs: `CO-A-02-03`, `CO-S-01-01`, `CO-S-01-05`. The five-field contract is `asset`, `indicator`, `period_start_utc`, `period_end_utc`, `value`. Definitions, historical first publication and revision policy have not been independently confirmed. The historical point-in-time factor arm remains blocked. The closed public projection exposes only aggregate results and provenance hashes.

## Fixed screen and measurements

Price-only Ridge(alpha1), daily-factor proxies delayed 24h/72h/192h from period end, and prior/cash/holding/trend controls share the same chronological sample intersection. The 192h control is the 24h proxy shifted by another seven days. The seven price/asset features are one-bar/24h/168h return, 24h volatility, completed-bar range/close, relative 24h volume and ETH identity. Fit-only scaling is saved with each coefficient checkpoint.

Features close at t, entry is the next bar's open at t+one full bar, and exit is at t+two bars. Labels reaching the first test decision are purged. Expanding fits test April–May, June–July and August–September 2026. The study completed 24 deterministic fits and 144 fold/method/fee cases in 7.2 seconds; the cap is 36 fits/600 seconds. The prediction hurdle stays 0.002 at 0/10/25bp one-way fees. There is no threshold search, neural fit or retrospective winner promotion.

Each asset sleeve starts with equal cash and uses fractional long/cash holdings. First entry and terminal liquidation are charged. Portfolio NAV is the mean of the two sleeve NAV paths; drawdown includes initial NAV1 and post-trade marks. The holding-share column is the equal-weighted fraction of asset-bars invested, and turnover is the equal-weighted asset-normalized turnover. These diagnostic definitions are displayed with the results. Return is the median fold return; skill, holding share and turnover are fold means; drawdown is the worst fold. Folds are never stitched. Seven-day paired time-block intervals preserve asset pairing and fold boundaries, with 2,000 fixed-seed draws and no multiple-comparison adjustment.

## Reproduce without resetting budgets

Use explicitly configured `DATA_ROOT` and external `UV_PROJECT_ENVIRONMENT`; Windows environments use `Scripts/python.exe` instead of `bin/python`. The independent package installs its locked optional linear dependencies with `uv sync --locked --group dev --extra predictive`.

The root acquisition API is `freeze_intraday_plan(output, now=aware_utc, source_revision=exact_commit)` followed by `acquire_intraday(plan_file, new_output, IntradayTransport())` from `competition_tools.datasets.binance_intraday`. All paths are external. Keep the plan, exclusive claim, raw archives, ledger and seal. The same frozen plan cannot be invoked again in another directory; inspect a partial run instead of resetting counters.

```sh
python -m crypto_mm.intraday.cli freeze \
  --dataset '<sealed-hourly-dataset-directory>' \
  --sentiment '<owner-published-factor-snapshot.json>' \
  --sentiment-sha256 '<expected-sha256>' \
  --source-revision '<clean-40-character-commit>' --output '<new-plan-directory>'
python -m crypto_mm.intraday.cli run \
  --plan '<frozen-plan-directory>/plan.json' --output '<new-study-directory>'
```

Keep the complete status JSON. Only `completed` runs may supply published results. Saved models reconstruct their scores; coefficients, individual predictions and account paths remain external. A separate producer wheel is frozen for observation so subsequent checkout changes do not silently alter its fingerprint.

## Prospective commitments and finite observation

The protocol freezes the final-fold price-only 1h/4h checkpoints, producer fingerprint, actual UTC clock and resource limits. Root tools call the independently installed leaf CLI through a versioned file contract. The first successful receipt committed four future forecasts and recorded zero scored outcomes. Warmup does not count as new timely observations. Late backfills are separate from bars received before the next modeled entry. Every forecast binds feature/checkpoint hashes, feature cutoff, generation and future entry/exit times; scores arrive only in later receipts. Revisions remain separate, and existing scores are not rewritten. This is self-recorded evidence awaiting review, not a registered independent holdout.

```sh
python -m competition_tools.evaluation.crypto_observation freeze \
  --study '<sealed-study>' --dataset '<sealed-hourly-dataset>' \
  --producer-python '<stable-external-frozen-producer-python>' --output '<new-protocol>'
python -m competition_tools.evaluation.crypto_observation capture --protocol '<protocol>'
python -m competition_tools.evaluation.crypto_monitor \
  --dataset '<sealed-hourly-dataset>' --study '<sealed-study>' \
  --protocol '<protocol>' --output '<new-local-monitor-directory>'
python -m competition_tools.evaluation.crypto_watch \
  --dataset '<sealed-hourly-dataset>' --study '<sealed-study>' \
  --protocol '<protocol>' --output '<new-task-owned-watch-directory>'
```

The optional task-owned process waits an hour between captures and stops within 48 hours of protocol freeze, on cumulative budgets, or on partial/unknown evidence. It changes no system timer, shared service or broker. Keep its state/events, stable environment and source until it stops and retention is reviewed. No private report is automatically uploaded to Pages.

The initial failed worker startup is retained. The replacement protocol's CLI originally omitted its requested predecessor debit; an immutable supplemental debit now binds both original protocol and receipt seals and lowers the replacement protocol total limits to 47 captures, 95 HTTP attempts and 31MiB. Existing protocol bytes and the four committed forecasts are unchanged. Capture/history/monitoring revalidate this debit; copies or edits cannot reset it. The corrected freeze CLI forwards the predecessor parameter. A new protocol may use `--previous-protocol` for an empty failed start; `crypto_observation reconcile --protocol '<current>' --previous-protocol '<failed-start>'` adds the conservative debit without rewriting existing commitments. Unknown transfers are never blindly repeated in their old protocol.

## Publication and health

`crypto_monitor` is local and read-only. It verifies sealed acquisition, experiment and observation evidence, then reports coverage, freshness, late data, revisions, distinct bar/forecast/score counts and cumulative resources. Missing or invalid inputs remain blocked. `scripts/crypto_public_projection.py --dataset ... --study ... --protocol ... --monitor ... --output ...` deliberately projects closed aggregate fields from those sources. It verifies exact source seals and sample/case scope, and records the forecast-chain head for an external publication-time anchor. The published page is an as-of snapshot, not a live feed.

Public Pages may display measured aggregates, intervals, fold and cost comparisons and documented limitations. Individual predictions, raw inputs, account records and private configuration remain external. Static/no-JavaScript tables retain all public facts. New chart/validation/controller modules use strict TypeScript and load chart code on request. Tests reject private fields and obsolete synthetic-only wording and require the public fixture's projection-code hash to match its normalized source.

The stock protocol's six owner-evidence gaps and the registered observation registry remain separate. This crypto pilot does not resolve them, expand execution products, authorize research acceptance or submit orders. See [sequence target study](sequence-target-study.md) and [observation registry](observation-registry.md).

[Follow-up journal and sequence comparison](crypto-followup.md)
