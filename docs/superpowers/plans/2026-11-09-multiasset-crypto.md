# Multi-asset crypto research plan

Goal: run a bounded offline diagnostic using existing accounting and retain reproducible private evidence.
Architecture: external task scripts validate public inputs and invoke the independently installed equity-lab static allocation CLI. No root-to-leaf source imports or broker calls.
Tech stack: Python, existing equity-lab wheel, exchange_calendars, public chart history.

- [x] Inspect source, worktrees, dataset contracts and account/competition boundaries.
- [x] Freeze universe, periods, allocation formulas, scenarios and acquisition budgets before new data.
- [x] Acquire bounded public inputs, preserve raw bytes and validate exact common sessions.
- [x] Run all available frozen cases and independently verify accounting and estimation clocks.
- [x] Write private interpretation and retention records. Synchronize English and Chinese public reproduction docs.
- [ ] Validate relevant tests, review documentation against code, open PR, verify required checks and merge under standing authorization.
