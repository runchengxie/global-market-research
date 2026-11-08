# ETF retrospective rehearsal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline.

**Goal:** Produce actual diagnostic calculations from retained price/FX bytes and trace Ranker artifacts without changing execution or evidence gates.
**Architecture:** Extract shared plain interval arithmetic from shadow.py; new etf_rehearsal.py handles strict public-chart normalization/as-of marks and fixed historical cases. Existing diary and standalone accounting gates remain intact.
**Tech Stack:** Python stdlib and locked exchange_calendars daily-data profile.
**Spec:** docs/superpowers/specs/2026-11-08-etf-rehearsal-design.md

## Global Constraints

Real historical bytes are diagnostic, never synthetic fixtures or accepted backtests. No orders, login, paid requests, schedules, model fits or sibling-source imports. No changed standalone real-source gate. All sources/results external, immutable, hash-bound and private; EN/zh-CN docs align.

## Review Focus

- Public FX response can append a current point outside requested range; exclude visibly.
- Adjusted-price units must not receive dividends a second time or be called executable prices.
- Reference includes Japan; as-of/FX gaps must block rather than delete the asset.
- Current holdings and acquired-after-period data are hindsight, not sample-out evidence.
- No fabricated Ranker/availability metadata to unblock live or standalone ledgers.

### Task 1: Shared arithmetic and strict rehearsal

Files: modify competition_review/shadow.py; create competition_review/etf_rehearsal.py; tests/competition_tools/test_etf_rehearsal.py.
Interfaces: interval_arithmetic(current,target,returns,non_stock_return,benchmark_return,cost_bps)->dict; run(manifest_file,snapshot_root,output)->dict.
- [ ] Add failing arithmetic/normalization/as-of/SMA/tamper tests, observe RED.
- [ ] Extract arithmetic preserving existing daily-review behavior; implement strict source parsing, modeled marks and27fixed cases using the helper.
- [ ] Run new/related tests, verify source/output flags and no future or missing-asset substitution.

### Task 2: Actual data/material evidence and closeout

- [ ] Preserve bounded local discovery, legacyFX/source comparison, four public raw receipts and download scripts. Freeze a source manifest; no overwrite/copy of authoritative datasets.
- [ ] Run real historical rehearsal; report all arms/fees and blockers for first prospective cycle. Trace Ranker labels/training/model artifact expectations and bounded filename audit privately.
- [ ] Add bilingual docs/operations/etf-rehearsal.md and links; final full root/static checks and fresh review.
- [ ] Exact-head PR/main/deployment verification under standing integration authorization; retain source/lock/wheel/runtime/results/ledger, clean only task Git assets.
