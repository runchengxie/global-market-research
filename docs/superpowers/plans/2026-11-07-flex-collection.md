# Flex collection implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline, with one whole-branch final review.

**Goal:** Collect private account reporting via explicitly supplied Flex configuration and make its coverage inspectable.
**Architecture:** Three focused stdlib modules beside existing private-review code; no changes to execution core or the registered strategy.
**Tech Stack:** Python3.12 urllib/XML/Decimal, existing external path/hash/seal helpers.
**Spec:** docs/superpowers/specs/2026-11-07-flex-collection-design.md

## Global constraints
Private explicit config only; no token/query/account values in public code or logs; no broker login, orders, template/token/scheduler edits. Unknown coverage is not zero. No derived official eligibility or executable targets.

## Review focus
Redirect/response-URL credential leakage; XML entity expansion/oversize; wrong linked account; SUMMARY/LOT duplication; missing section or date coverage mistaken for complete history.

### Task1: Client and parser
- [x] Write failing tests for placeholder/no network, bounded polling, rejected redirect/host, sanitized errors, exact account binding, dates and position units.
- [x] Implement config/client and bounded XML report inspection; verify relevant tests.

### Task2: CLI and delivery
- [x] Test collect/inspect sealed external artifacts and overlap/no-overwrite; implement CLI and EN/zh-CN guide.
- [x] Preserve local placeholder and first-run status; write private holding and corporate-action review using primary sources.
- [ ] Run root tests/lint/import boundaries; whole-branch review and regression fixes; PR/exact-head CI/authorized merge/main deployment verification/retention/task-only cleanup.

## Execution updates

User filled the local credential placeholder and authorized collection. Read-only acquisition succeeded and yielded source data for offline inspection; no private statistics are included here. Explicit dash aggregate placeholders are not accounts/positions. NAV-in-base may establish observed base currency without AccountInformation. Discovery retains no unbound raw report. Independent review required conid-aware execution grouping and statement-period checks; regressions also cover XML-encoded credential echoes. Official ratios and registration/model linkage remain unverified.
