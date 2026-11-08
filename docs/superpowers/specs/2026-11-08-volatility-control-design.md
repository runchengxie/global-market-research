# Fixed exposure versus volatility-control diagnostic

The owner authorized exploring whether simple risk control improves on fixed allocation. Routine research choices are delegated; actual holdings, risk budgets, orders and the existing future cycle remain untouched.

## Approach and boundaries

Selected: a narrowly scoped root offline diagnostic using retained USMV adjusted-price bytes and a zero-return USD residual. This isolates sizing from FX, Japanese marks and stock selection. It is a historical adjusted-unit proxy, not an accepted cashflow/broker replay. Reuse the sealed input/receipt/parser contract; never import leaf research Python or weaken the standalone real-ledger gate. Alternative full accounting needs independently accepted action/availability/FX data; a multiaset experiment adds confounders before sizing is understood.

Freeze an external sealed protocol before current calculations, binding manifest hash, calibration/evaluation dates, trailing-return count, annualization, unlevered cap, annual volatility target, fixed reference, fees and buffer sensitivity. All historical bytes were already acquired; this is current retrospective experiment freezing, not historical preregistration or unseen out-of-sample evidence. No parameter sweep or best-result selection. Parameters stay private and cannot become account policy.

At each evaluation opening mark, use only previous completed adjusted closes; estimate sample SD of trailing simple returns, annualize, and size target_vol/estimated_vol capped without leverage. Zero/invalid vol or missing sessions blocks. Monthly scheduled changes use previous close+30minutes and the next opening proxy. Between changes hold units. A nonzero buffer is a separately labeled sensitivity; the primary comparison has zero buffer and identical monthly cadence.

Comparators: fixed reference, fixed exposure calibrated only from the earlier calibration period, volatility-controlled allocation, and an explicitly hindsight/nontradable fixed exposure numerically matched to the volatility arm's mean actual pre-interval stock weight. Match only the primary no-buffer arm; retain match residual/tolerance and fail rather than claim a false match. Compare return, CAGR, sample realized volatility, anchored max drawdown, average exposure, turnover and costs; do not claim alpha/statistical superiority from one asset/time range.

Start every arm with wealth1 cash, apply self-financed fees to actual stock value changes, allocate target weights on post-fee wealth, and liquidate at the final proxy mark with the same fee. Cash earns zero in all arms; no financing, spread, tax or actual interest model. Daily return metrics combine entry fee into the first interval and terminal fee into the last; drawdown includes pre-entry wealth1. Report all paths/transactions and causality clocks, all fee/buffer cases and calibration identity.

The source adapter validates seals/hash/receipt/identity, exact XNYS labels and daily-open chart event timestamps, complete calibration/evaluation/warmup coverage, and protocol chronology. All outputs external/immutable/bilingual. No acquisition, credentials, scheduler, target handoff, platform/broker changes or orders.

Related literature: Moreira and Muir, Volatility-Managed Portfolios, https://www.nber.org/papers/w22208. The paper motivates studying time-varying risk, but this capped inverse-volatility experiment is not its inverse-variance factor-portfolio replication or evidence for this ETF.
