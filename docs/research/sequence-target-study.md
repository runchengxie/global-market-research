# Sequence objective schemes and forward preparation

[简体中文](sequence-target-study.zh-CN.md)

This bounded screen compares the existing probability-of-a-large-rise scheme with expected next-open return regression. It asks whether the existing features support useful forecasts before increasing expert capacity. The schemes change target, loss and allocation hurdle together; results cannot be attributed to labels alone. All historical windows have already been exposed.

## Frozen comparison

Both schemes use the same ten-stock split-adjusted snapshot, relative ten-feature20-session windows, next-open to following-open labels and purged chronological folds. Classification predicts returns above0.2% with BCE; regression uses MSE with target mean/std estimated only on fitting rows, then restores return units. Fitted priors, linear models (Logistic/Ridge alpha1), matched single LSTM, equal experts and dispatched top2 MoE are compared. Linear models fit once per fold/objective; three neural seeds are11/23/37. All neural schemes have at most30epochs, patience5,batch128,Adam.001 and two threads. The frozen seven-fold plan has140fits/175cases, under180fits and6hours. Three seeds are exploratory screening.

Fixed decisions are probability>.5 or expected return>.001; the return hurdle approximates two-sided5bps costs and is unchanged in0/5/20/40bps sensitivity runs. Validation chooses among five predeclared thresholds per scheme and also defines a constant-exposure control. Every candidate is retained; validation was already used for early stopping. Report actual exposure and volatility, not hindsight exact risk matching. Opening/final liquidation fees, cash-funded fractional long sleeves and no dividends/financing remain the existing accounting assumptions.

Prediction scores use Brier/AUC for classification and raw-return MSE/MAE for regression, each against its fitted prior. Both report daily cross-sectional rank correlation with the same future returns; constant ranks remain undefined. No regression output is called a probability. Paired account/loss intervals use20-session blocks,2000draws, seed averaging per market date and independent fold boundaries; no stitched NAV or multiplicity correction.

## Commands

Install the equity leaf with locked `predictive` and `neural` extras; keep environments/output external. Freeze a plan before running:

```bash
python -m equity_lab.study.sequence.target_cli plan --manifest '<manifest>' --expected-sha256 '<sha256>' --output '<new-plan.json>'
python -m equity_lab.study.sequence.target_cli run --manifest '<manifest>' --expected-sha256 '<sha256>' --plan '<frozen-plan.json>' --output '<new-run-directory>'
python -m equity_lab.study.sequence.target_cli analyze --run '<sealed-run-directory>' --output '<new-analysis-directory>'
python -m equity_lab.study.sequence.target_cli calendar --start 2026-11-09 --end 2027-02-05 --output '<new-calendar.json>'
```

Each case saves target transforms, feature scalers, checkpoints/linear coefficients, validation and test score tables, routing loads and accounts. Saved scores are reconstructed before completion. Cooperative deadline checks surround fit batches and case processing; interrupted cases are excluded from completed counts. Partial/invalid status cannot pass the continuation rule. Inputs are reverified before sealing; no existing bundle is overwritten. The analysis outputs inspectable JSON and a concise Markdown report; the earlier probability browser does not reinterpret regression data.

## Continue or defer MoE

For each complete objective scheme, sparse fixed-policy return must beat linear, matched and equal at5bps with positive lower95% paired intervals; each contrast separately needs positive20bps mean difference and at least5of7 positive fold mean daily differences. It also needs positive lower95% Brier/raw-MSE improvement over the fitted prior and a positive lower95% return difference versus its own validation-exposure control. These unadjusted retrospective criteria are a development rule, not statistical confirmation. Even a pass only means `promising_retrospective`; expansion, research acceptance and execution stay false until independent forward evidence exists. Failed conditions and risk gaps remain visible.

## Evidence and future preparation

The root stdlib-only packet consumes the leaf's modeled XNYS calendar and exact frozen plan hashes. It reuses the data owner's six-blocker audit and maps the manifest/receipt as candidate evidence, never independent proof:

```bash
python -m competition_tools.evaluation.sequence_readiness \
  --manifest '<manifest>' --expected-sha256 '<sha256>' \
  --calendar '<calendar.json>' --calendar-sha256 '<sha256>' \
  --plan '<plan.json>' --plan-sha256 '<sha256>' \
  --source-revision '<commit>' --output '<new-packet-directory>'
```

All candidates/objectives are frozen without choosing historical winners. The calendar includes the two opens following the final signal. It is modeled exchange scheduling, not observed availability. Status is `frozen_preparation_blocked`; no registered holdout, acceptance, broker call, collection job or shared pointer is created. The current historical snapshot does not provide future features. Independently evidenced security identities, dated universe, actions/dividends, availability, owner/source-use terms and holdout access governance remain prerequisites.

## Crypto transfer question

Evaluate retained grain separately from service capability. In the inspected inputs, the complete eight-product Binance study is daily; the BTC/ETH AIVIX factor snapshot is daily and has no independent historical availability evidence; the hourly DEX pilot is blocked. Do not infer complete hourly prices from hourly API support, factor timestamps or archive packaging. Daily bars are not book events. A subsequent BTC/ETH spot4h/1h screen should first establish immutable causal OHLCV coverage, missing intervals, price/quote identity, execution delay and cost sensitivity. Keep derivatives funding and maker assumptions out until matching data/accounting exist. Finer bars do not create proportionally independent observations.

See [the research page](https://runchengxie.github.io/global-market-research/research/lstm-moe/) and [frozen-model diagnostics](sequence-diagnostics.md).

[The completed BTC/ETH intraday screen and separate observation record](crypto-evidence.md) now provide verified hourly coverage,24 fixed linear fits and explicit factor-availability limits. Crypto MoE remains untrained.
