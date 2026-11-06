[English](lstm-moe.md) | [简体中文](lstm-moe.zh-CN.md)

# LSTM and mixture-of-experts research

LSTM/MoE research now lives in `research/equity-lab`. This optional offline study compares learned expert routing with a parameter-matched single LSTM, fixed equal-weight experts, independent ensembles and simple baselines. The original [moe-lstm repository](https://github.com/runchengxie/moe-lstm) preserves the historical implementation and results. The new implementation independently reproduces the architecture's mathematical ideas and does not copy its unlicensed source.

## Install and run

From `research/equity-lab`, set `UV_PROJECT_ENVIRONMENT` to a new external directory under the configured owner data root, then install the optional dependencies:

```bash
uv sync --locked --group dev --extra predictive --extra neural
uv run --locked --extra predictive --extra neural python -m equity_lab.study.sequence.cli plan --manifest /external/dataset/manifest.json --expected-sha256 MANIFEST_SHA256 --output /external/runs/sequence-plan.json
uv run --locked --extra predictive --extra neural python -m equity_lab.study.sequence.cli run --smoke --manifest /external/dataset/manifest.json --expected-sha256 MANIFEST_SHA256 --output /external/runs/sequence-smoke
uv run --locked --extra predictive --extra neural python -m equity_lab.study.sequence.cli run --manifest /external/dataset/manifest.json --expected-sha256 MANIFEST_SHA256 --output /external/runs/sequence-primary
uv run --locked --extra predictive --extra neural python -m equity_lab.study.sequence.cli inspect --output /external/runs/sequence-primary
```

All output destinations must be new. The smoke is one SPY fold, one seed and one epoch; it verifies engineering behavior, not a model's effectiveness. Primary panel fitting excludes SPY. `--secondary` runs separately declared top-1, shared-router, shared-encoder and removed-expert variants with a 60-session input; `--transformer` runs the Transformer comparison; its results are secondary rather than interchangeable with the 20-session primary suite. No broker connection, acquisition, automatic threshold optimization or research promotion occurs.

## Data and time

The input contract is an explicit hash-bound `competition.dataset_manifest.v2` US daily IBKR snapshot with normalized OHLCV, an acquired receipt, split-adjusted prices, USD and an XNYS schedule. Missing sessions, invalid prices or changed payloads fail. Prices are not forward filled. Source files remain read-only; runs retain their input hashes and recheck them after fitting.

The existing owner snapshot contains 10 currently selected stocks plus SPY, 953 sessions between 2023-01-03 and 2026-10-20. It is marked `accepted_research=false`, has already been examined and lacks verified historical availability, complete corporate-action evidence and publication rights. Fixed-current selection may introduce survivorship bias. This is an exploratory retrospective input, not an untouched holdout.

Features end at session t's close, modeled available 15 minutes later. Entry is t+1 open and exit is t+2 open. Labels measure that same open-to-open return; above 0.2% is class 1, otherwise class 0. A score above 0.5 goes long; class 0 stays in cash. Labels become available at exit. Rolling blocks use 400 fit, 80 validation and 63 test sessions, label-availability purging, an additional signal-session embargo and a 12-hour modeled readiness allowance. Audit rows expose actual timestamps and effective counts.

## Models, evaluation and artifacts

Three full-window LSTM experts are mixed at representation level. Dense routing uses all experts. Sparse routing gathers only selected windows per expert, skips empty batches and scatters weighted representations. Top-2 normalizes its selected weights; top-1 retains the selected softmax magnitude so a prediction-task gradient can reach the router. A separate 0.01 load-balancing coefficient is used on sparse paths. It does not prove useful specialization. Dispatch counts, probability weights and representation probes are retained.

The primary suite contains cash, holding, a frozen moving-average momentum rule, logistic regression, LSTM-64, an actually parameter-matched LSTM, equal-weight experts, independent prediction averaging, dense learned routing and top-2 dispatch. All pooled models share eligible stock fit windows and fit-only scaling. Training uses five fixed seeds, at most 50 epochs, patience 5 and batch 32. The primary cap is 600 fits/6 hours; each independent ensemble member consumes a fit. Oversized schedules fail before starting. Interrupted runs remain partial with their pending configurations.

Every fold starts with cash and ends with liquidation. Equal initial stock sleeves are simulated in split-adjusted research price units; there are no dividends, shorts, leverage or interest. This is not a raw-price, action-aware execution ledger. Costs of 0/5/20/40 basis points per side include opening and liquidation. Holdings, cash, fees and marks reconcile. Drawdown includes initial equity 1; undefined Sharpe/AUC and zero trades retain explicit reasons. Independent fold NAVs are not stitched into a continuous track record.

Bundles contain configuration, source revision, environment, input hashes, sample/fold clocks, probabilities, model/scaler state, routing, training losses, fills, marks, classification metrics, account metrics, paired Brier diagnostics and checksums. The bootstrap uses same-date stock aggregates and within-fold date blocks; it is descriptive rather than discovery evidence. Actual CPU dispatch counts and repeated inference timing are recorded. Fewer expert calls do not establish a speedup.

## Public presentation

The [interactive research page](https://runchengxie.github.io/global-market-research/research/lstm-moe/) uses explicitly synthetic data until a particular real projection has documented publication rights and owner approval. It lazy-loads ECharts when requested, offers zoom and model selection, and retains an accessible numeric table. Confusion matrices belong in ordinary tables; no measured counts are invented for the synthetic interface. Existing public research snapshots are unchanged.

See the [full design](../superpowers/specs/2026-11-06-lstm-moe-integration-design.md) for the study's limitations and secondary experiments. Passing tests or completing a run does not establish profitable trading or authorize execution.

Additional declared runs: `--secondary` (routing variants), `--transformer` (single-FFN versus sparse Transformer), and `--features levels|correlation|kmeans|som` (price-level and fit-only selector ablations). Each stage has a separate 240-fit / 6-hour budget.

Measured local production build: the lazily loaded chart dependency closure is approximately 187 KB gzip, versus about 120 KB for the two original PNGs. The chart library is not requested until the reader loads the interactive chart. This improves interaction and defers download; it does not reduce a cold full-chart payload. Sizes are build-specific and exclude common page assets.
