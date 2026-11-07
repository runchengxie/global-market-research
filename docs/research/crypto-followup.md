# Crypto research follow-up

[简体中文](crypto-followup.zh-CN.md) · [Original evidence](crypto-evidence.md) · [Public journal](https://runchengxie.github.io/global-market-research/research/crypto-evidence/#research-journal)

This round supports keeping the models small. A 39-fit, five-epoch four-hour comparison found negative mean forecast skill for all learned families, including the dense MoE. Its learned gate did not improve the mean skill over the parameter-matched single LSTM or the equal-expert model. This is a feasibility screen, not evidence of convergence, statistical superiority or a new independent holdout.

## What changed

| Question | Evidence stage | Finding | Next requirement |
| --- | --- | --- | --- |
| Can the forward process be audited? | Six-receipt snapshot,2026-11-07 09:41 UTC |16 committed forecasts,6 scored;0 deadline or reconstruction errors;10 timely hourly bars | Let the finite process finish and audit again |
| Why was the original model often cash? | Saved-score analysis, no refit | Hourly price-only 99 th-percentile predictions 3.6–4.3 bp, below 20 bp in all three folds | Treat decision sensitivity separately from forecast quality |
| What do the factors mean? | Two official definitions confirmed | Net sentiment and standardized sentiment deviation documented; third ID, first publication and revision timing remain unverified | Provider-owned versioned metadata |
| Does a learned gate help? |39 retrospective fits,234 cost/rule cases | Negative mean skill; dense gate not better than matched/equal controls | New predeclared hypothesis before more capacity |

The audit uses a fixed prefix of sealed append-only receipts. Mature unscored forecasts are not dropped; two awaited later captures at the snapshot. Six scores cannot establish predictive value, and their pooled skill was about−5.53%. There were no observed revisions in this prefix. The underlying finite process and frozen producer remain unchanged. The published page is an as-of snapshot, not live monitoring.

## Comparable model design

All models receive the same twelve-bar window of seven price/asset features on four-hour BTC/ETH data and the original common eligible dates. The factor intersection defines eligibility, but the new models do not consume factor values. Decisions use completed-bar features, one full-bar entry delay and next-open exits. Windows never cross assets. The Ridge baseline uses the 84 flattened inputs, not just the last bar, so it is a new baseline rather than a rerun of the original seven-feature screen.

Models and actual parameter counts: Ridge 85 coefficients/intercept; single LSTM 8 units 641; matched single LSTM 16 units 1,793; three equal LSTM 8 experts 1,753; three learned-gate LSTM 8 experts 1,753. Equal and dense count the same instantiated parameters, including an unused equal-model router. Every dense input computes all three experts and mixes their hidden sequence representations. The equal model is a jointly trained equal mixture, not an average of independently trained forecasts.

Three expanding test folds remain April–May, June–July and August–September 2026. The final 30 calendar days before each test are validation; fit-label exits must precede validation decisions, and validation-label exits must precede test decisions. Input and target scaling use fit data only. Ridge fits once per fold. Neural variants use seeds 11/29/47, five fixed epochs, batch 256, Adam 0.001, one CPU thread, no hyperparameter search, auxiliary loss or early stopping. Five epochs were deliberately a bounded feasibility budget; this experiment cannot distinguish architectural limits from undertraining.

Within each fit/seed/fold, choose the 0/10/20 bp long/cash hurdle by 10 bp one-way validation net return, breaking ties toward the larger hurdle. Save the choice before the test account calculation. Report both that choice and fixed 20 bp under 0/10/25 bp costs. This does not create a clean new test: these historical periods were already examined. Never choose a winner or revise the running forward model using these outcomes.

Thirty-nine fits completed in 17.58 seconds under 45 started-fit/900 second caps and an exclusive plan-bound claim. Retained evidence includes exact source, input/plan seals, safe NumPy checkpoints with reconstruction, fit-only scalers, validation/test scores, selected rules, accounts, gates and a ledger. There are 234 fold/seed/rule/fee cases. Returns aggregate by median, skill/exposure/turnover by mean and drawdown by worst case. Fold/seed ranges are descriptive, not uncertainty intervals; seeds share dates and are not independent market samples. Holding share and turnover are asset-average diagnostics rather than NAV-weighted exposure measures.

At 10 bp under validation-selected rules, mean skills were approximately Ridge−5.650%, single−0.492%, matched−0.203%, equal−0.260%, dense−0.281%. Median returns were−6.794%,−0.084%,0%,0%,0%. Zero median return is largely cash behavior and does not demonstrate useful prediction. The journal retains all 234 cases and gate distributions rather than only this summary.

## Reproduce without changing the active observer

Set an external `UV_PROJECT_ENVIRONMENT`; in `research/crypto-mm`, install `uv sync --locked --group dev --extra predictive --extra neural`. Existing intraday producer modules and its installed frozen wheel are unchanged; do not install this environment over a running producer.

```sh
python -m competition_tools.evaluation.crypto_audit --protocol '<sealed-protocol>' --output '<new-audit-directory>'
python -m crypto_mm.exploration.cli diagnose --study '<sealed-original-study>' --output '<new-diagnostics-directory>'
python -m crypto_mm.exploration.cli freeze --dataset '<sealed-dataset>' --study '<sealed-original-study>' --source-revision '<clean-40-character-commit>' --output '<new-plan-directory>'
python -m crypto_mm.exploration.cli run --plan '<plan-directory>/plan.json' --output '<new-comparison-directory>'
```

A plan is single-use: partial/unknown results and claims remain retained. Changing the output directory does not reset fit allowance. Do not rerun the published plan merely to reproduce a web table: the explicit projection consumes its sealed artifacts. Root tools and independent research packages exchange files/CLI calls and never import each other's code.

Next, audit the observer after its original stop condition, obtain [factor provenance](crypto-factor-provenance.md), and decide whether a separately frozen, longer observation or convergence experiment is justified. No broker, execution schema, system scheduler or production configuration was changed.
