# Volatility-control diagnostic implementation plan

> Execute inline with superpowers:executing-plans and one fresh whole-branch review.

**Goal:** Test fixed versus volatility-based sizing with exposure-matched controls and explicit retrospective limits.
**Architecture:** volatility_math.py owns narrow pure sizing/fee/proxy-book/matching arithmetic; volatility_study.py owns sealed protocol/data validation and private reports, reusing existing chart inputs. No leaf imports or actual accounting gate changes.
**Tech:** Existing locked Python root daily-data profile, stdlib math/statistics, no new dependency.
**Spec:** ../specs/2026-11-08-volatility-control-design.md

## Global constraints

Protocol/settings/results external, no actual account policy or order. Same USD source and zero cash across arms; all costs including entry/exit. Causal previous closes only, exact calendar/no filling. Hindsight matched arm must be labeled nontradable. All cases retained, no parameter optimization.

## Review focus

Lookahead in return window; insufficient/zero vol; first-fee and first-loss drawdown; fee-funded target identity with no borrowing; drift/hold units and buffers; exposure-matching residual; altered/missing source and protocol/overlapping periods.

### Task1: Pure math and proxy path

- [ ] RED tests for trailing-only targets/future perturbation, zero/invalid vol, target cap, self-financing buy/sell, initial/exit fees, hold units/month cadence/buffer, matching residual and invalid clocks/prices/weights.
- [ ] Implement target_from_closes(prices,lookback,target,cap,annualization), rebalance(stock,cash,weight,bps), simulate(points,bps,*,fixed_weight=None,buffer=0), match_fixed(points,bps,mean_exposure). Inputs are typed validated numeric points with opening at and causal signal_at; no I/O.
- [ ] GREEN tests with independent hand-calculated funding/path cases.

### Task2: Sealed protocol/data runner and actual experiment

- [ ] Freeze private protocol before evaluating outcomes.
- [ ] RED adapter tests for invalid protocol dates/weights/hash/future freeze and exact coverage; synthesize source/calendar data to verify all arms and no missing marks.
- [ ] Implement offline CLI --manifest --protocol --output; calendar-adjusted source points, calibration-only control, three fee scenarios and separate buffer arm; preserve all paths/metrics and warnings in sealed bilingual report.
- [ ] Generate real retained-data experiment, interpret exposure-controlled results without adoption claims, keep failures and limitations. Add generic bilingual operations docs.
- [ ] Full/static tests, fresh review, exact-head CI, standing-authorized merge/deployment verification, retained installed wheel/runtime and task-only cleanup.
