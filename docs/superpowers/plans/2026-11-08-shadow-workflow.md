# Prospective shadow workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline.

**Goal:** Save prospective drafts/decisions, evaluate later paired outcomes and reconcile reported NAV components offline.
**Architecture:** Compose strategy_case and immutable evidence helpers in shadow.py/CLI. Independent nav_change.py owns broker-reported component arithmetic; no execution/research imports.
**Tech Stack:** Python stdlib and existing locked root test environment.
**Spec:** docs/superpowers/specs/2026-11-08-shadow-workflow-design.md

## Global Constraints

No orders, broker login, scheduler or public account data. Preserve missing strategy parameters as null. Real prospective entries use current UTC, no CLI backdating. Outputs external, fresh and sealed. English and zh-CN guides aligned. No claim of full price/FX attribution or model efficacy.

## Review Focus

- Blocked or tampered historical entries cannot become actionable strategy performance.
- Later observations bind exact decision, account, currency and causal interval.
- Unknown NAV fields and mixed profit modes cannot silently disappear.
- Preserve component overlap/FX limitations and reject malformed numeric values.
- Keep observed holdings separate from an approved risk budget and research lanes separate.

### Task 1: Prospective draft, diary and later observation evaluation

Files: create competition_review/shadow.py and shadow_cli.py; tests/competition_tools/test_shadow_workflow.py.
Interfaces: prepare(case_file, output, now=None), record(case_file, output, now=None), evaluate(entry_root, outcome_file, output, now=None). Injectable clock is Python-only for deterministic tests; CLI always current UTC.
- [ ] Write failing draft/record/evaluation tests and observe RED.
- [ ] Implement using build_case, verify_seal, new_output, digest, Decimal, full return-key/causal bindings.
- [ ] Verify GREEN, static checks and commit.

### Task 2: Reported NAV bridge and operations

Files: create competition_review/nav_change.py; extend same CLI with nav --snapshot --output; tests/competition_tools/test_nav_change.py; EN/zh-CN docs/operations/prospective-strategy.md, link competition-review docs.
Interfaces: explain_nav(raw, expected_account, base_currency) -> dict; explain_bundle(snapshot_root, output) -> dict. Compare latest period-endingNAV to recomputed snapshot.
- [ ] Write failing component/overlap/identity/mode/tamper tests; observe RED.
- [ ] Implement conservative report arithmetic and bilingual guides; run actual retained report and save private draft/entry/NAV outputs.
- [ ] Final full root tests, fresh whole-branch review and exact-head PR checks; integrate under standing authorization, verify main/Pages, retain artifacts/runtime and remove only task Git assets.
