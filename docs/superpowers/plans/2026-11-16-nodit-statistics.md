# Nodit Statistics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collect and verify two Nodit Ethereum daily statistics with conservative local budgets.

**Architecture:** A narrow transport handles credentials and fixed-host bounded requests. A collector freezes a plan, records attempted spend and creates private raw/normalized evidence; its CLI also verifies retained bundles offline.

**Tech Stack:** Python 3.12 stdlib, pytest, Ruff; no new dependencies.

**Spec:** `docs/superpowers/specs/2026-11-16-nodit-statistics-design.md`

## Global Constraints

- Ethereum mainnet daily active accounts and transaction counts only; inclusive window <=100 completed UTC days with 00:30 publication delay.
- Maximum/default four attempts, 600 estimated CU, 1 MiB per response and a cooperative 120-second time budget; no retries or automatic collection. Blocking DNS/TLS/header/chunk operations can overrun; stop when control returns. This is not a hard process deadline.
- Private external credentials and evidence, no key/error-body disclosure, no broker or research promotion.
- User delegates implementation choices and asks to proceed with the existing competition grant despite unknown quota; execute inline without further approval requests.

## Review Focus

- Redirects or JSON-escaped key echoes must never disclose the key.
- Partial writes, failed calls and unknown spend must remain explicit, without automatic resume.
- Incomplete/duplicate/out-of-window data must not publish normalized success.
- Paths inside source trees, symlink ancestors and permissive credentials must fail before requests.
- Re-running a command must not overwrite data; budget counters are local to each invocation.

### Task 1: Safe transport and private evidence collector

**Files:** Create `src/competition_tools/datasets/nodit_transport.py`, `src/competition_tools/datasets/nodit.py`, `tests/competition_tools/datasets/test_nodit.py`.

**Interfaces:** `NoditTransport(credential_file).fetch(metric, start, end, *, timeout, max_bytes) -> bytes`; `collect(start, end, output, *, transport, max_requests=4, max_cu=600, max_seconds=120, now=None) -> dict`; `verify(output) -> dict`.

- [ ] Write tests for valid two-series CSV and offline verification, charged failed calls, budget rejection before I/O, bad dates/counts, tamper detection, existing output, insecure credential/path, fixed-header requests and secret/error handling.
- [ ] Run `python -m pytest -q tests/competition_tools/datasets/test_nodit.py`; confirm missing implementation failures.
- [ ] Implement fixed HTTPS transport, bounded collector and strict verifier; avoid generic provider abstractions.
- [ ] Run focused tests and root suite with Ruff and workflow-boundary check; expect all checks pass.
- [ ] Commit implementation and tests using the user's public noreply identity.

### Task 2: CLI delivery, documentation and bounded live acceptance

**Files:** CLI in `nodit.py`; create `docs/operations/nodit.md` and `nodit.zh-CN.md`; update the provider guides and `.env.example`.

**Interfaces:** `python -m competition_tools.datasets.nodit collect --credential-file ... --start ... --end ... --output ...`; `... verify --output ...`. JSON summaries and stable errors only.

- [ ] Test CLI failure/success exit behavior, then implement CLI and bilingual docs covering limits, unknown grant quota and UTC availability.
- [ ] Run full root verification and independent whole-branch review; fix important findings.
- [ ] Acquire the latest 90 eligible UTC days with two requests, verify the bundle offline and retain task inventory outside Git.
- [ ] Commit, push to the verified user repository, create PR, wait for current-head required checks, merge under standing authorization, verify main and clean only this task's branch/worktree.
