# Crypto Evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver verified intraday crypto inputs, a bounded sentiment screen, prospective receipts, monitoring and richer measured Pages.
**Architecture:** Root stdlib acquisition/receipts and independent crypto offline research exchange immutable versioned files; Pages consumes explicit aggregate projection only.
**Tech Stack:** Python3.12, existing crypto package plus locked optional NumPy/scikit-learn, Astro/TypeScript/ECharts, pytest/Playwright.
**Spec:** docs/superpowers/specs/2026-11-07-crypto-evidence-design.md

## Global Constraints
- Preserve root/leaf isolation and existing snapshots; all runtime data/environments external.
- Exact acquisition112reads/32MiB transfer/64MiB expanded/8MiB ZIP/600sec; exact study24fits capped36/600sec/one thread.
- Only BTC/ETH spot USDT; no private API, broker, Java app, neural fits, shared publication pointer or scheduler activation.
- Historical availability is unknown; proxy results cannot become point-in-time accepted evidence.
- EN default plus zh-CN catalogs/docs; new TS modules strict checked; retain complete no-JS facts.

## Review Focus
- Interrupted request/model work must remain partial with charged/unknown spend; test before real runs.
- Malicious archive/path or extra source files must fail before output mutation; exercise checksum/member/containment.
- Proxy sentiment must never be mistaken for verified timely data; pin public labels and all prospective dates.
- Cash-start drawdown/cost accounting must include first entry, last exit and initialNAV; numerical tests.
- Changed/duplicated/racing observation input must preserve old receipt; exclusive-write and mutation tests.

### Task1: Verified hourly acquisition
**Files:** create datasets/binance_intraday.py, intraday_transport.py, crypto_evidence.py and tests/competition_tools/test_crypto_evidence.py (paths under src/competition_tools).
**Interfaces:** freeze_intraday_plan(output:Path,now:datetime)->dict; acquire_intraday(plan:Path,output:Path,transport)->dict; verify_intraday(path:Path)->dict. Manifest contains files, coverage, source/units, budget ledger and accepted_research=false.
- [ ] Test checksum/unit/close/grid/ZIP attacks and budget/containment/same-plan repeated-run claims with synthetic archives, run RED.
- [ ] Implement strict plan/worker/parser/receipt and4h aggregation; GREEN and commit.
- [ ] Freeze real plan at a clean revision, acquire bounded monthly inputs once, retain complete/partial receipt.

### Task2: Bounded independent sentiment screen
**Files:** create crypto_mm/intraday/{inputs,features,study,cli}.py and corresponding tests; optional predictive extra/lock.
**Interfaces:** run_screen(manifest:Path,sentiment:Path,sentiment_sha256:str,output:Path)->dict; verified summary/scores/models/account artifacts. Four-arm fixed24fit schedule and explicit blocked verified arm.
- [ ] Test causal execution/purging, proxy delays/common dates, one-bar versus24/168h windows, plan-bound fit claims, fit-only scales, budget interrupts and initial/terminal accounting RED.
- [ ] Implement fixed Ridge/prior/trend/holding/cash, metrics and paired block uncertainty; GREEN/commit.
- [ ] Run the complete screen on verified real inputs at clean source; reconstruct scores and seal output.

### Task3: Prospective receipts and local monitor
**Files:** create evaluation/crypto_observation.py, crypto_monitor.py and focused root tests.
**Interfaces:** freeze_observation(output:Path,inputs:dict,now:datetime)->dict; capture_observation(protocol:Path,output:Path,transport,now:datetime)->dict; monitor(paths:list[Path],as_of:datetime)->dict. CLI clocks real UTC, APIs injectable for tests.
- [ ] Test freeze/cutoff/first-seen/warmup, frozen coefficient forecasts committed before entry, separate observed/forecast/scored counts, no premature scoring, stale factor source, revisions, exclusive receipt/containment, corrupt/unknown monitor statuses RED.
- [ ] Implement manual bounded public capture and read-only local report; GREEN/commit.
- [ ] Freeze real protocol and capture first receipt; report eligible future count truthfully, retain stable runtime instructions.

### Task4: Measured public evidence
**Files:** create scripts/crypto_public_projection.py, crypto-evidence.v1.json, CryptoEvidence.astro, EN/ZH catalogs, strict TS validator/controller/chart and browser tests; update Pages allowlist/sequence wrapper/current guides.
**Interfaces:** aggregate projection verifies input seals and closed schema, includes sample,24fit trials/fold/cost summaries, availability/observation/monitor status and source revision/hash.
- [ ] Test extra keys/private paths/raw arrays/invalid counts/source hashes and obsolete synthetic-only wording RED.
- [ ] Implement bilingual static tables and lazy chart with existing theme/mobile/noJS patterns; GREEN, publish actual verified aggregates and commit.

### Task5: Review, integration and retention
- [ ] Run root+crypto affected/full tests, locked lint/import boundaries, strict TS/build/Playwright and sealed-source verification.
- [ ] Independent final whole-branch review; fix Important issues with regression tests.
- [ ] Push user's task branch/open PR, validate latest combined main and all current-head checks, merge under standing authorization.
- [ ] Verify merged main and actual live EN/ZH Pages; retain source archives/locks/wheels/results/logs/receipts/private ledger.
- [ ] Remove only completed task branch/worktree, preserve unrelated locked Paper worktree, report facts and remaining evidence gaps.
