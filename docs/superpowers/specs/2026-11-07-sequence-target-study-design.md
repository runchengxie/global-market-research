# Sequence target comparison and forward-readiness design

[简体中文](2026-11-07-sequence-target-study-design.zh-CN.md)

The next experiment asks whether the existing causal features contain useful information under a different supervised target, before increasing MoE capacity. User authorization covers all three follow-ups and opts out of repeated confirmation. This design precedes implementation; it does not authorize broker access, new acquisition or research acceptance.

## Frozen exploratory comparison

Keep the existing split-adjusted fixed-current ten-stock snapshot, relative10-v1 features, lookback20, next-open to following-open holding period, and seven purged/embargoed rolling folds. Reuse existing sample/audit and account contracts unchanged. All dates are previously exposed. Compare the existing binary target `forward_return > .002` with raw forward-return regression. Preserve the original binary label in audit files; store target_value, score_kind and score separately.

Models: fitted prior, linear (LogisticRegression for classification / Ridge alpha1 for regression), parameter-matched single LSTM, fixed-equal experts, and sparse top2 LSTM. Deterministic linear models fit once per objective/fold at seed11. Neural models use seeds11/23/37, identical architectures/budgets across targets, maximum30epochs, patience5, batch128, Adam lr.001, two CPU threads. No hyperparameter search. There are126 neural plus14 linear fits =140, under hard preflight maximum180fits and21600seconds. Three seeds constitute bounded screening, not confirmation. Cash, holding and causal10% volatility are unfitted common controls, evaluated once per fold.

Regression labels are centered/scaled using fit-segment mean/std only (floor1e-6); model output is transformed back to return units. Use MSE for regression and BCE-with-logits for classification; sparse balance coefficient.01 remains the same across tasks. Early stopping uses the corresponding validation task loss. Save safe checkpoints with objective/normalization metadata, linear coefficients, scalers, feature order, validation/test scores, training history and routing summaries. Verify score reconstruction before completing each case.

Allocation policies: fixed probability cutoff.5, or return hurdle.001 (approximate two-sided5bps cost); keep the same hurdle at every cost scenario for sensitivity. Validation-only alternatives use classifier grid[.35,.425,.5,.575,.65] or return grid[0,.0005,.001,.002,.004], maximizing validation mean net daily return at5bps; ties nearest the fixed hurdle then larger. Report every candidate and reused-validation caveat. Also replay a constant exposure frozen from the fixed model's validation allocations. Fractional long-only account/cash-funded costs0/5/20/40bps remain identical. Report actual exposure/volatility gaps; no hindsight exact test matching.

Comparable predictive reports: daily cross-sectional Spearman against the same future return for either score kind; regression MSE/MAE/skill against fit-period mean; classification AUC/Brier/skill against fit-period prior. Undefined/constant ranks are explicit. No conversion of regression scores into uncalibrated probabilities. Analyze paired daily account returns and squared-error improvements with20-session blocks,2000draws, same-date seed averaging, independent fold boundaries; no stitched fold NAV and no multiplicity-adjusted claim.

## MoE continuation rule

Freeze the rule before fitting. For each objective, sparse fixed-policy account must exceed linear, matched and equal at5bps with positive lower exploratory paired95% intervals, positive mean differences at20bps, at least5of7 positive fold differences, and positive paired prediction-loss improvement versus fitted prior. Require improvement over its validation-exposure control at5bps as an exposure check. Report risks/gaps and failures individually. Passing means only promising_retrospective; expansion remains deferred until independently accepted forward evidence. Missing/partial cases mean insufficient evidence, never pass. Actual dispatch/active parameters and fit/inference timings remain visible. No automatic production adoption or model deletion.

## Evidence and forward preparation

Root tools remain stdlib/file based; do not import leaf packages. Reuse the exact blocked-only owner audit. Build a packet that binds manifest/receipt/allowed source metadata hashes and maps candidate records to the six requirements without promoting them. Do not read credentials or infer historical truth from today's metadata. Record source documentation, inspection findings and missing independent records. Existing relevant provider/acquisition receipts may be inventoried read-only; no new broker calls.

Freeze an immutable preparation protocol for2026-11-09..2027-02-05 signal dates, including the new candidate/objective IDs, sample contract, selection, budgets, source revision and exposure history. The equity leaf exports modeled future XNYS sessions and the next two opens after the final signal; label this a calendar model, not observed availability. Root validates and hashes that file. Status remains frozen_preparation_blocked, accepted_research=false,execution_authorized=false,registered_holdout=false. It is not an authoritative reservation. No collection/scheduler/current-pointer update. Reverify owner input bytes and calendar bindings at packet finalization.

## Delivery

New study CLI and tests in the equity leaf; root packet/evidence CLI consumes versioned JSON only. English/Chinese user guides and a concise private local report (actual metrics, comparisons, rule outcomes) accompany saved CSV/JSON. Existing interactive diagnostic browser remains on its probability-specific schema; do not silently reinterpret regression outputs. Keep raw inputs/results external; public code PR may include owner-authorized aggregate findings, never raw prices/private paths. Use task-specific external environment/results, exact source archive, independent review, all applicable local/CI checks, PR merge/deployment verification and task-only cleanup. Preserve the locked Paper worktree.
