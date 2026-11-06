# Paper Allocation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recover allocation logic as a configurable, auditable Paper-only workflow.
**Architecture:** Pure Decimal policy, strict private execution specification, durable account/run guards and journal, optional IBKR port and CLI. Existing runners retain their behavior.
**Tech Stack:** Python 3.12, stdlib, optional ib-insync, pytest/Ruff.
**Spec:** `docs/superpowers/specs/2026-11-06-paper-allocation-design.md`

## Global Constraints

- Only US stock/USD with optional SGD funding; account valuation SGD.
- Default CLI is offline planning. No broker order is authorized by this implementation task.
- Real Paper lifecycle verification is required before merging execution-chain changes.
- Credentials and generated artifacts remain outside source; preserve recovered originals.

## Review Focus

- Numeric and timestamp non-finite/bool/naive values must fail closed (Task 1/2).
- Different run IDs must not bypass unresolved account mutations (Task 2).
- Lost submission responses and partial FX must never trigger stock submission (Task 2/3).
- Broker observations require account/contract/execution identity, not just status (Task 3).
- Changed positions/cash/quotes/STOP during what-if must block submission (Task 2/3).

### Task 1: Pure allocation policy

**Files:** Create `src/packages/execution_policies/paper_allocation.py`, `tests/execution/test_paper_allocation_policy.py`.
**Interfaces:** `AllocationPolicy`, `Quote`, `Snapshot`, `AllocationPlan`, `compute_allocation(policy, snapshot, now)`; Decimal values with explicit currency contract.
- [ ] Write tests for hand-calculated cash funding, variable ticks/weights, existing USD, spreads, freshness, invalid numerics and bounds.
- [ ] Run pytest on the new file: expect missing-module failure.
- [ ] Implement pure validated types and calculation; no broker imports.
- [ ] Run policy tests: expect all pass; commit.

### Task 2: Specification, durable state and orchestration

**Files:** Create `src/apps/execution_runner/paper_spec.py`, `paper_state.py`, `paper_allocation.py`, `tests/execution/test_paper_allocation_workflow.py`.
**Interfaces:** Strict `AllocationSpec.from_dict`, `PaperAllocationRunner(spec, root, broker, clock)`, `run(submit=False)`, `reconcile()`; port snapshot/qualification/what-if/execute/reconcile methods. Limit command wraps existing `OrderIntent`. Reuse EventJournal and project storage aliases.
- [ ] Write workflow tests: offline default, confirmed funding, partial/unknown stop, final rechecks, no retry, account-wide unresolved state, concurrent guards, replay/dedup/reconciliation.
- [ ] Run new tests: expect missing-module failure.
- [ ] Implement strict parsing, guards, event persistence and orchestrator with a narrow injected port.
- [ ] Run workflow and existing execution/adapters/audit tests: expect all pass; commit.

### Task 3: IBKR adapter and CLI

**Files:** Create `src/adapters/ibkr/paper_allocation.py`, `src/competition_tools/run_paper_allocation.py`, `tests/adapters/test_paper_allocation.py`, `tests/competition_tools/test_paper_allocation_cli.py`.
**Interfaces:** `IBKRPaperAllocationBroker` implements Task 2 port with bounded qualification/snapshot/what-if/submit/reconcile; CLI plan/submit/reconcile with explicit spec and private root.
- [ ] Write fake-client tests for exact account/contracts/session/ticks/IOC references, timeouts and read-only reconciliation; CLI offline exit behavior.
- [ ] Run new files: expect missing-module failure.
- [ ] Implement optional adapter and CLI, retaining existing IBKR behavior.
- [ ] Run new and relevant tests: expect all pass; commit.

### Task 4: Operations, provenance and verification

**Files:** Create `docs/operations/paper-allocation.md`, `.zh-CN.md`; link from operations/architecture docs as appropriate.
**Interfaces:** Document schema/example, commands, finite timeouts, status/reconciliation and bounded real Paper verification procedure.
- [ ] Document recovery mapping and current verification limits without private parameters.
- [ ] Run full pytest, Ruff, compileall and workflow boundaries; inspect all failures.
- [ ] Review entire branch independently, fix important findings with reproducing tests.
- [ ] Preserve private recovery hashes/retention records, push and open PR. Leave unmerged pending required real Paper checks if unavailable.
