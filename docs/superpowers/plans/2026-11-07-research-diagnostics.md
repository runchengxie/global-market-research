# Research diagnostics implementation plan

> **For agentic workers:** Use superpowers:executing-plans for native continuous implementation and independent final review. User has opted out of repeated design/execution confirmations.

**Goal:** Explain flat predictions, add causal fair controls, deliver a private offline browser and evidence/protocol/maintenance reports.
**Architecture:** equity-lab reuses frozen runs; root tools own governance and informational code inventory; no broker or public real-data path.
**Tech stack:** existing Python3.12/pandas/NumPy/optional PyTorch, stdlib root tools, static HTML/JS, pinned cloc2.10.
**Spec:** ../specs/2026-11-07-research-diagnostics-design.md and Chinese companion.

## Global constraints and review focus

Keep sealed parents immutable; validate input/parent hashes before and after. No threshold/exposure/risk target reads test labels. Weights [0,1], same complete cohort/calendar/fees. Real results private; future protocol remains draft/blocked. Preserve binary accounting behavior and unrelated Paper work. Check out-of-range allocations, missing prices/cohort, zero validation variance, one-class labels, no-JS/script injection, mutated parents, explicit interruption and optional dependency profiles.

## Task 1: Fractional controls and score diagnostics

Files: sequence/account.py, new sequence/controls.py and tests/test_sequence_controls.py.
Interfaces: replay_allocations(rows,fee_bps) with allocation column; replay_sequence stays binary. score_diagnostics(y,p) and control_allocations(snapshot,validation,test) use only known rows.
- [ ] Write failing tests for binary parity, fractional fees/cash, invalid weights, validation-only controls and no future close influence.
- [ ] Run focused tests, implement minimal behavior, rerun green and existing account suite.
- [ ] Commit and record exact verification in ledger.

## Task 2: Frozen-run diagnostic CLI

Files: sequence/diagnostics.py, extend sequence/cli.py; tests/test_sequence_diagnostics.py.
Interfaces: diagnose_run(snapshot,parent,output,seconds=1800). Rebuild fit/validation/test probabilities for primitives/linear/ensembles/neural, verify saved test scores, then output score distributions, router summaries, five fixed threshold candidates and six controls at four costs for the four predeclared model families.
- [ ] Test synthetic installed bundle, original immutability, test-label mutation not affecting selected threshold/allocations, missing checkpoint and interrupted status.
- [ ] Implement exclusive diagnostic artifact with references and actual availability cutoffs; no retraining.
- [ ] Verify parent and snapshot at completion, full leaf tests; commit.

## Task 3: Offline result browser

Files: sequence/viewer.py and packaged templates/catalogs; leaf browser tests, site/tests/sequence-local.spec.mjs and narrow Pages allowlist addition.
Interface: write_viewer(summary,path) validates diagnostic projection and emits fully offline HTML with EN/ZH catalogs, filters, tables, equity/exposure chart and provenance.
- [ ] Test escaping, malformed records and installed wheel assets, then implement template/generator.
- [ ] Browser checks: both languages, filters, selected curve, mobile bounds, blocked network and no-JS tables. Real report stays outside source.
- [ ] Update bilingual diagnostic docs and existing research links; commit.

## Task 4: Evidence crosswalk and future protocol draft

Files: root evaluation/sequence_governance.py; tests/competition_tools/test_sequence_governance.py; bilingual docs.
Interfaces: build_protocol(evidence,start,end,now) and CLI consume existing evidence-gap report; outputs retain draft/blocked flags, future range, candidate/cost/feature/label/stopping definitions and required independent records.
- [ ] Test past/inverted dates, caller attempted promotion, unsupported evidence schema and exclusive output.
- [ ] Implement stdlib-only consumer; invoke existing owner evidence CLI on retained snapshot read-only, create private draft/crosswalk.
- [ ] Root boundary/tests; commit. No scheduling, reservation, acquisition or acceptance edits.

## Task 5: cloc and module maintenance

Files: root code_size.py, source_inventory.py, workflow-boundary rule/tests, .github/workflows/code-size.yml and pytest duration flags.
Interfaces: Git-tracked file inventory -> pinned cloc by-file JSON -> grouped report; AST import/entrypoint and duplicate-byte inventory -> informational JSON.
- [ ] Test tracked-only grouping, exclusions, tests/data separation, duplicate and CLI classifications, forbidden model edges.
- [ ] Implement scripts without vendoring cloc. CI verifies official2.10 SHA256, writes artifacts/job summary; existing pytest jobs print slowest15.
- [ ] Run actual counts and read-only inventory on task tree; maintain no line-count gate. Commit.

## Task 6: Real exploration and delivery

- [ ] Complete full root/leaf tests, Ruff, static boundary, installed smoke, browser suite and applicable Pages checks.
- [ ] Run diagnostic replay on sealed350-config parent within30minutes; record completed/partial/invalid and actual findings; generate private browser and governance draft.
- [ ] Independent whole-branch review, fix actionable issues with regressions.
- [ ] Verify destination/identity, push PR, validate latest target combined result, integrate under standing authorization after all checks; verify main/Pages.
- [ ] Retain results and source/validation records; remove only this task's remote/local branch and worktree. Report missing external evidence and pending future validation explicitly.
