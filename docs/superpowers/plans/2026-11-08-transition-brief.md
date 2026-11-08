# Placeholder decision brief and research observations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline.

**Goal:** Record the true placeholder context and enable prospective model-free ETF diagnostics without weakening actual-strategy gates.
**Architecture:** One candidate_observation.py offline CLI reuses verified proposal calendar, strict chart parser and immutable output helpers. Context and one-page account brief stay private; public bilingual docs explain only the generic workflow/rule distinctions.
**Tech Stack:** Python stdlib and existing locked daily-data profile.
**Spec:** docs/superpowers/specs/2026-11-08-transition-brief-design.md

## Global Constraints

No strategy effectiveness claim, order, actual allocation approval, broker/login, provider query, message, platform edit or schedule. No Ranker fabrication or declared-model gate changes. Context attribution is received-now, not historical proof. Public rules distinguish cumulative days/candidacy; eligibility remains unverified. Preserve all original artifacts.

## Review Focus

- New user explanation cannot silently rewrite historical evidence or declaration.
- Research-only observation must not weaken actual-policy/model gating.
- Future, missed or stale price receipts cannot produce a prospective signal.
- Null/invalid evidence must not become zero exposure or a hold instruction.
- Frozen calendar/proposal and outputs remain hash-bound and immutable.

### Task 1: Research-only prospective recorder

Files: create competition_review/candidate_observation.py; tests/competition_tools/test_candidate_observation.py.
Interface: record(proposal_root,output,session_date,price_file=None,now=None)->dict; CLI --proposal --session-date --price-file(optional) --output, no --as-of.
- [ ] Write failing status/causal/source/proposal/immutability tests; observe RED.
- [ ] Implement strict schedule and receipt checks; reuse existing parser and SMA; observe GREEN and existing diary regression checks.
- [ ] Add bilingual docs/operations/candidate-observations.md and links to prospective-strategy.

### Task 2: Actual brief and rule/source evidence

- [ ] Capture user explanation privately with timestamp and attribution, retain original mistaken belief alongside verified official correction.
- [ ] Verify existing declaration/Flex/proposal/preflight seals; contextualize recovered code without asserting execution/actor origin; write one-page bilingual decision brief with concrete priorities and unknown actual risk budget.
- [ ] Generate current not-due research record, no fabricated future signal.
- [ ] Full root/static/fresh review, exact-head checks and standing authorized integration/Pages; retain private inputs/results/source/runtime/ledger and clean only this task Git assets.
