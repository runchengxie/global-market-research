[English](2026-11-07-research-diagnostics-design.md) | [简体中文](2026-11-07-research-diagnostics-design.zh-CN.md)

# Research diagnostics and maintenance

The user authorized all five follow-ups and requested continuous execution without repeated confirmation. Work from main 0a51b47 in a task worktree; preserve the unrelated Paper worktree and all sealed experiments. This task does not connect to brokers, acquire paid data, publish real research series or promote research acceptance.

## Chosen approach

Reuse sealed predictions/checkpoints and existing dataset evidence checks. Add a versioned diagnostic bundle and an offline HTML browser, rather than another hosted application/database. Fit no new neural networks. Diagnostics belong in equity-lab; root governance consumes file contracts and imports no leaf Python. CI maintenance remains stdlib plus a pinned official cloc executable.

## Scientific contract

Analyze all existing score distributions and base rates. Reconstruct validation probabilities with saved feature order/scaler/checkpoint; verify reconstructed test probabilities against saved predictions within 1e-6 before using a model. Report 10-bin reliability, Brier/log loss/AUC, score quantiles and fraction above 0.5, separated into fit-label prior, validation and test. Router diagnostics distinguish actual mixture weights from an unused router in equal/single-expert controls.

For matched/equal/dense/sparse models, compare original positions with daily-rebalanced 25%/50% allocations, validation-frozen exposure allocations, validation-frozen volatility allocations, and a causal 10%-annual-volatility allocation based on 20 historical portfolio close returns. All weights are in [0,1], no leverage, cash has zero interest. Validation-derived targets use no test labels or future test exposure; realized test exposure/volatility gaps remain visible, never labeled exact risk matching. Same symbols, dates, opening/terminal fees and 0/5/20/40 bps apply to every account. Fractional replay preserves the original binary API and arithmetic.

Explore thresholds [0.35,0.425,0.5,0.575,0.65], selected only by validation net mean return at 5 bps; ties prefer proximity to 0.5 then the larger threshold. Report every candidate, decision cutoff and selection count. This is an additional retrospective model-selection exercise on exposed history, not a fresh holdout. Do not pick a test-period winner or alter the parent run. Validation is also used by original early stopping; diagnostics must disclose that limitation. No calibrator is fitted in this stage; reliability diagnostics explain whether one is warranted.

Full real diagnostic replay is capped at 30 minutes, writing partial/interrupted/invalid status if necessary. Every output is exclusive, outside repositories/input trees, bound to parent checksums, source/input hashes and actual model references; reverify inputs and parent at completion. Do not rewrite old sealed results. Reuse current costs and synthetic split-adjusted price units, with no dividend/real-execution claim.

## Offline browser

A self-contained local HTML file embeds only the diagnostic projection, escaped for HTML/script contexts. It makes no network requests and offers model/fold/seed/cost filters, equity and exposure paths, score/calibration tables, routing loads and source/configuration/status details. English is default, Chinese uses packaged catalogs, selection persists when storage is available. Numeric tables and evidence status remain readable without JS; no local server or credentials are needed. Public Pages links to documentation, never private bundles. Package template/assets so installed wheel execution works.

## Data evidence and future protocol

Reuse `audit_daily_research_evidence` and its blocked-only six-gap contract. Produce a crosswalk for universe/security identity, corporate actions/dividends, historical availability, provenance and holdout governance. Existing flags or self-written assertions do not verify missing owner evidence. Draft a proposed future signal-date range 2026-11-09 through 2027-02-05, subject to owner/calendar/data review. Bind candidate IDs, costs, horizon, feature version, stopping rules and required owner records. Status is always draft/blocked, accepted_research=false and execution_authorized=false. No reservation, frozen-holdout claim, scheduled acquisition or current/latest update is created.

## Engineering maintenance

Pin official standalone cloc 2.10 and its SHA256; do not vendor its large source into Git. Count Git-tracked program implementations/tests separately from prose/config/data; exclude lockfiles, dependencies and generated files. Retain per-module counts, exact duplicate-file groups and Python entrypoint/import inventory as informational maintenance evidence. Duplicate copies and externally invoked modules are review candidates, not proof of dead code. CI uploads a JSON report and a job summary, with no arbitrary line-count limit. Extend existing import-direction checks to neural models and prevent pure data/portfolio/evaluation layers importing models; add real edge regressions. Add pytest duration reporting without introducing an unmeasured performance gate.

## Delivery

TDD synthetic regressions, installed-package smoke and full root/leaf/site checks as applicable; independent review; PR against user main; validate current combined result before standing-authorized integration; verify main/Pages; retire only this task's branches/worktree. Keep private artifacts and retention records. Full Transformer/selector research remains separate from this diagnostic task.
