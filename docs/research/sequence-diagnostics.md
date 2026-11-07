# Frozen sequence-model diagnostics

[简体中文](sequence-diagnostics.zh-CN.md)

Use the private diagnostic browser to inspect why a saved model trades rarely, and whether its comparison changes after accounting for exposure and risk. This is retrospective analysis of already exposed history. It does not create an untouched test, refit a model, establish trading efficacy, or authorize execution.

## Reproduce a private report

Install the independently packaged equity leaf with its locked `predictive` and `neural` extras. Supply the original sealed run and the exact input manifest digest:

```bash
python -m equity_lab.study.sequence.cli diagnose \
  --manifest "$DATA_ROOT/global-market-research/datasets/<snapshot>/manifest.json" \
  --expected-sha256 '<manifest-sha256>' \
  --run "$DATA_ROOT/global-market-research/research/lstm-moe/runs/<sealed-run>" \
  --output "$DATA_ROOT/global-market-research/research/lstm-moe/<new-diagnostic-directory>"
```

The output must be new, external to source and separate from inputs. The diagnostic reconstructs validation and test probabilities from saved checkpoints, scalers and feature order. It requires test-score agreement within absolute tolerance `1e-6` and binary account agreement within `1e-10`. It verifies source input bytes and the original parent checksum binding again before sealing.

A 30-minute processing budget produces an explicitly partial result if exhausted. SIGTERM and keyboard interruption preserve completed records when received inside the diagnostic processing stage. Setup failures can occur before a bundle exists. An interrupted current case can leave account files without a completed record; only summary records count as complete. Inference is checked at operation boundaries, so a single operation can finish after the deadline; it cannot then mark the run completed.

Open `browser.html` directly from disk. It contains the data, scripts, English and Chinese catalogs, SVG curves, numeric tables, and a useful no-JavaScript table. It makes no network requests and starts no server. Filter by model, fold, seed, fee and control; use the file chooser to open another diagnostic `summary.json` (maximum 50 MiB). Public Pages may display verified measured aggregates, comparisons and uncertainty with their sample scope, source revisions and limitations. Keep raw individual predictions, account records and private configuration outside the site. The synthetic example remains separately labeled.

## Interpret the comparisons

Each case reports class frequency, score quantiles, Brier score, log loss, AUC when defined, reliability bins, calibration error and Brier skill against the fitted-period class prior. All scores below 0.5 explain a flat binary account, but do not alone distinguish a sensible prior from an uninformative predictor. Routing summaries distinguish learned gates from fixed equal weighting.

For matched LSTM, equal experts, dense MoE and sparse MoE, compare the original account against constant 25%/50%, validation-frozen exposure, validation-frozen volatility ratio, causal 10% volatility, and a validation-selected threshold. Every control uses the same dates and fee scenarios (0/5/20/40 bps), fractional long-only sleeves, initial opening and final liquidation. These remain adjusted-price accounting units without dividends, financing or leverage.

The five threshold candidates are 0.35, 0.425, 0.5, 0.575 and 0.65. Select only by validation mean daily net return at 5 bps, then closeness to 0.5 and larger threshold for ties. The validation period also informed original early stopping, so this is an additional retrospective selection, not independent confirmation. No calibration model is fitted.

Risk targets use validation data, never realized future test risk. The causal volatility control uses only 20 known close-to-close portfolio returns at each feature cutoff. Reports expose target-allocation gaps, realized mean opening-exposure gaps and realized annual-volatility differences relative to the original model at each fee. These controls do not promise exact realized risk matching. Compare paired dates and uncertainty before adopting a model or threshold.

## Data evidence and future validation

The root CLI calls the existing dataset owner's byte and evidence auditor:

```bash
python -m competition_tools.evaluation.sequence_governance \
  --manifest '<manifest>' --expected-sha256 '<sha256>' \
  --start YYYY-MM-DD --end YYYY-MM-DD --output '<new-external-directory>'
```

Its evidence crosswalk preserves six blockers: point-in-time universe, historical security identity, corporate-action coverage, historical availability, owner provenance (including source-use/publication rights), and holdout governance. A future protocol is a draft requiring owner review and independent evidence. Both acceptance and execution authorization stay false. The command neither reserves a test nor schedules data collection. The draft fixes candidate scope, dates, costs, selection and stopping rules; it does not turn previously inspected dates into unseen data.

## Maintenance evidence

The Code size workflow downloads SHA-verified cloc 2.10 and reports committed source totals and PR deltas by module, separating implementation, tests and other text. Counts include duplicates and exclude lockfiles/dependencies/build output; they are informational, without a line-count quota. Run `competition_tools.code_size --help` for the same local contract. `competition_tools.source_inventory` lists byte-identical files, imports and entry points; missing static callers do not establish dead code. Import-boundary checks prevent model modules from acquiring replay or broker dependencies. CI prints the 15 slowest tests to guide later optimization.

See [the sequence study](lstm-moe.md) for model and accounting assumptions.
