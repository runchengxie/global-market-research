# Concrete candidate cycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline.

**Goal:** Replace empty-only planning with specific research candidates, a bounded material review and a dated first observation cycle.
**Architecture:** One small proposal module/CLI composes existing verified snapshot, calendar and immutable-output helpers. Bilingual docs explain candidate choices; actual material search stays private.
**Tech Stack:** Python stdlib, existing daily-data exchange_calendars.
**Spec:** docs/superpowers/specs/2026-11-08-candidate-cycle-design.md

## Global Constraints

Research hypotheses only, no approved account parameters/orders/schedules/provider changes. No external messages or private source copied to Git. Preserve future observations as missing. Source paths/identities/research outputs stay external. English and zh-CN align.

## Review Focus

- No historical session or expired review cutoff can become a prospective cycle.
- Missing trend history must remain blocked, never cash by default.
- Reference weights are normalized research controls, not literal multi-currency account performance.
- A local Ranker implementation is distinct from declaration/checkpoint/score binding.
- Calendar details do not establish contest or broker-session eligibility.

### Task 1: Concrete proposal and dated calendar

Files: create src/competition_tools/competition_review/research_cycle.py and tests/competition_tools/test_research_cycle.py.
Interface: propose(snapshot_root, output, core_conid, first_session, material_deadline, now=None) -> dict.
- [ ] Write failing tests for exact arm parameters, future calendar/holiday handling, expired dates/cutoff, invalid core, tamper and immutable output.
- [ ] Implement snapshot-bound research arms and schedule, no returns/targets; observe GREEN.
- [ ] Add bilingual docs/operations/research-candidates.md and .zh-CN.md, link prospective-strategy guides.

### Task 2: Bounded material/data review and delivery

- [ ] Preserve read-only tracked-source inventory of six related repos with revisions, byte hashes, scope/exclusions and classified Ranker/PIT hits; no claims of global absence or team acknowledgement.
- [ ] Generate real proposal with explicit core, first session2026-11-09 and proposed material cutoff2026-11-13T10:00Z; retain missing signal/history/binding evidence.
- [ ] Final full root/static validation and fresh whole-branch review; PR/exact checks, integrate under standing authorization, verify main/Pages, retain independent runtime/source/logs/ledgers and clean only task Git assets.
