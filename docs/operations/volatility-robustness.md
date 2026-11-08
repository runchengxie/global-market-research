# Unchanged-parameter volatility robustness

[简体中文](volatility-robustness.zh-CN.md) · [Original sizing study](volatility-study.md)

Use a frozen research stopping rule to decide whether a sizing configuration deserves more investigation. This is not a universal investment utility standard, independent price validation, historical preregistration or account adoption gate. The original sizing math and future competition cycle remain unchanged.

## Freeze intent and retain sources

Before acquiring/evaluating new outcomes, seal an external intent.json (`competition.volatility_robustness_intent.v1`). Bind the original sealed protocol hash and its exact core parameters: lookback_returns, annualization, target_volatility, cap, fixed_reference_weight, one_way_cost_bps, buffer_sensitivity, cash_return, leverage_allowed, parameter_optimization, execution_authorized, match_tolerance. The aggregator compares types/values canonically with the original protocol; changing both new intent and studies cannot silently replace the original parameters.

The intent also records aware frozen_at, calibration_start/end, ordered episodes with id/evaluation_start/end/full_calendar_year/previously_examined/include_in_decision, positive decision_fees drawn from the original cost scenarios, required_share_numerator/denominator, numerical_tolerance and material_improvement, and execution_authorized false. The aggregator recomputes XNYS full-year boundaries and overlap with the original calibration/evaluation windows. Only new full-year episodes count; all prior/partial episodes remain displayed. Required passes use integer ceiling, not rounding down. No eligible episodes means unknown.

Acquire original public bytes with bounded requests and receipts, without bypassing authentication/browser challenges or using broker credentials. Preserve issuer workbooks unchanged and read them without executing formulas. NAV/share, raw market close, adjusted prices and performance indices are different data. Matching distribution dates/rounded amounts does not certify independent adjusted OHLC, split history or PIT availability. Report provider/issuer scope and unresolved upstream lineage explicitly; do not substitute NAV as a tradable opening price. Do not publish raw restricted/licensed source files.

After acquisition, source-bind per-episode copies of the original study protocol without changing the intent/core. Use the existing volatility_study CLI for each episode. Annual cash-wealth1 resets and entry/terminal fees make these separate episodes, not a continuous full-span account. Create a sealed runs.json (`competition.volatility_robustness_runs.v1`) with recorded_at, intent_sha256, source_manifest_file/source_manifest_sha256 and entries of id/root/study_sha256. Missing planned entries are retained as missing rather than dropped.

## Aggregate complete evidence

```bash
python -m competition_tools.competition_review.volatility_robustness \
  --intent /external/sealed-intent \
  --original-protocol /external/original-sealed-protocol \
  --runs /external/sealed-runs-manifest \
  --corroboration /external/optional-sealed-source-audit \
  --output /external/new-robustness-report
```

The offline command checks seals, input byte hashes, acquisition/freeze/report chronology, unchanged core, exact episode dates, source/asset/currency bindings and every arm/cost scenario. Sealed studies are supplied calculation evidence; the aggregator does not rerun their price accounting. Each exposure-matched control must retain its hindsight/nontradable label and agree with the primary arm's mean actual exposure within the frozen tolerance.

Return gap = volatility return minus matched fixed return. Drawdown gap = volatility maximum drawdown minus matched fixed maximum drawdown, so positive means a smaller loss. A comparison passes only when both gaps are at least negative numerical_tolerance and at least one is at least material_improvement. At **every** decision fee, the specified share of new full years must pass. Sensitivity fees remain displayed, and missing any planned year/arm/fee makes the overall decision unknown. No threshold tuning after results.

Outputs preserve every episode/fee comparison, exclusions, majority arithmetic, match checks, source hashes and limitations in robustness.json/bilingual reports. Research outcomes are continue_candidate_under_frozen_rule, retire_primary_candidate_under_frozen_rule or an explicit unknown state. Independent-source scope is separate. A source corroboration bundle uses schema competition.volatility_source_corroboration.v1 and must bind the same manifest hash; reported compatibility/upstream flags remain attributed claims. Actual adoption stays false in every case. No strategy invalidity/alpha proof, orders, broker/platform changes, schedule or executable target follows.
