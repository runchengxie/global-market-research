# Cash-backed Paper allocation

[简体中文](paper-allocation.zh-CN.md) · [Documentation](../README.md)

The new allocation CLI defaults to an offline calculation. It supports one US equity/ETF in USD, optional SGD-to-USD funding and SGD account valuation. It does not accept a research `targets.json` as authorization. A separate private, versioned specification binds the account, qualified contract, current time window and risk policy.

**Broker readiness is unverified.** Unit tests use synthetic inputs and a fake client. No new Paper order, Gateway login or scheduled task was performed during recovery. The execution-chain PR must remain unmerged until the repository's real Paper lifecycle checks pass.

## Specification and calculation

Create private specifications outside source under the deployment configuration directory. `AllocationSpec.to_dict()` in `apps.execution_runner.paper_spec` produces the exact `paper-allocation.v1` structure. Required top-level fields are `schema`, `run_id`, `account`, `symbol`, `con_id`, `primary_exchange`, `window_start`, `window_end`, `policy`, `allowed_positions` and `settings`. Unknown or duplicate fields are rejected. Run IDs use 1–24 ASCII letters, digits, underscores or hyphens. The account must be an explicitly configured `DU` account and the endpoint must be a configured Paper port (4002 or 7497); the adapter also checks the actual managed account. Symbols use the canonical `.US` suffix. Windows must be timezone-aware, at most 30 minutes and within one qualified liquid session.

The policy requires target gross weight (0 < weight ≤ 1), SGD target cap, maximum integer shares, prior reference close/date and qualified stock/FX ticks. Decimal values are JSON strings; `max_shares` is an integer. The remaining policy fields are explicit in the serialized specification: stock spread `.005`, FX spread `.003`, stock slippage `.002`, FX slippage `.0005`, cash buffer `.005` and reference band `.015` are library defaults. They are tolerances, not a recommended allocation. Every tolerance is bounded to at most `.05`. Choose current account-appropriate limits; the old 55%, USMV and October reference price are not carried forward.

An offline snapshot contains decimal strings `nav_sgd`, `gross_sgd`, `sgd_cash`, `usd_cash`, `sgd_settled`, `usd_settled`, plus `stock` and `fx` quotes. Each quote contains decimal-string `bid`/`ask`, an aware ISO `at`, and boolean `live`. Quotes must be real-time and between one second in the future and 15 seconds old at calculation. Use freshly prepared synthetic inputs for a demo; a stale saved quote correctly fails. The calculator rounds limits upward to ticks, quantities downward and funds purchases from settled balances only.

```bash
python -m competition_tools.run_paper_allocation \
  --spec "$CONFIG_ROOT/deployments/global-market-research/allocation.json" \
  --snapshot "$DATA_ROOT/global-market-research/paper-demo/snapshot.json"
```

Planning does not connect, reserve a run or create result directories. The output has `status=offline_plan` and `submitted=false`.

## Explicit execution and recovery

After separately authorizing a concrete current Paper attempt, use `--mode submit --execute-paper --data-root "$DATA_ROOT"` with the same `--spec`. The CLI chooses the canonical/legacy project root using the existing storage contract, then uses its fixed `paper-allocation` namespace for all account guards. Do not invent a separate data root to bypass a claim. `settings.dry_run` is used by other runners; this CLI requires its own explicit submission mode and flag and does not submit from planning.

The workflow preserves existing `OrderIntent` identity inside typed IOC limit commands. Its journal records requests separately from broker outcomes and execution IDs. It never sends a market order. A filled FX order is not enough to proceed: settled USD, positions, open orders, quotes, time, STOP and what-if must pass again. Partial FX stops before stock. Any unconfirmed mutation blocks every new run ID for that account. Timeout requests cancellation, then records any remaining uncertainty; it never automatically retries.

Create `STOP` under the selected project's `paper-allocation` directory to block further submissions. It does not retroactively cancel an order already at the broker. Connection/request and what-if timeouts are 8 seconds, quote acquisition is bounded to 8 seconds, order observation is 45 seconds and cancellation observation is 10 seconds. An externally supplied `KillSwitch` can also be used by Python callers.

```bash
python -m competition_tools.run_paper_allocation --mode reconcile \
  --spec "$CONFIG_ROOT/deployments/global-market-research/allocation.json" \
  --data-root "$DATA_ROOT"
```

Reconciliation is read-only at the broker. It requires the unchanged specification, completed-order identity, executions, positions and no open orders. Missing broker history remains unknown; absence never establishes rejection. Account/run claims survive restart and root aliases. Reconciliation never resumes stock after an interrupted FX stage. Inspect the append-only journal and rebuild its projection using `EventJournal.rebuild_projection()`. Preserve claims and uncertainty markers; do not remove them to retry. The account lock is an OS process-lifetime lock, released on process death; its on-disk file is not itself an active lease. Durable run claims and account uncertainty remain after process death, and only verified reconciliation can clear uncertainty.

Exit codes: 0 offline plan/reconciled, 2 blocked, 3 partial, 4 unknown. A reconciled run can still have a terminal cancelled order or no stock order after an interrupted FX stage; inspect order facts, not only the run status.

## Recovery provenance and real Paper verification

The recovered calculator maps to `packages/execution_policies/paper_allocation.py`; the old one-off runner's responsibilities map to `apps/execution_runner/paper_*` and `adapters/ibkr/paper_allocation.py`. The original five source/test/plan files remain retained, with private hashes and disposition in the project's retention inventory. No original recovery file or historical result was removed.

Before merge, prepare a supervised, bounded Paper-only test specifying the account, contract, session, quantity, price/cash cap, any FX leg and cancellation procedure. Obtain current execution authorization for those exact mutations. Record Paper connection, qualification, what-if, submission, cancellation, fills, restart recovery and reconciliation separately. Include a deliberately interrupted/uncertain attempt and demonstrate that a different run ID is blocked and read-only reconciliation sends no order. Use the stable reviewed source revision; a temporary worktree must not host a scheduled deployment. If any required lifecycle evidence is absent, keep the PR open and label it unverified.
